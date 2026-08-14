from dataclasses import dataclass

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.utils.crypto import constant_time_compare, salted_hmac

from .exceptions import QuickCreateContextInvalid, TerminalUnavailable
from .models import Order
from .policies import can_edit_draft, can_quick_create_product
from .terminals import resolve_pos_terminal

QUICK_CREATE_SIGNING_SALT = "sales.pos-quick-create.v1"
SESSION_FINGERPRINT_SALT = "sales.pos-quick-create.session.v1"
QUICK_CREATE_MAX_AGE = 900


@dataclass(frozen=True)
class QuickCreateContext:
    actor_id: int
    shop_id: int
    terminal_id: int
    draft_id: int
    barcode: str
    expected_version: int


def _session_fingerprint(session_key):
    if not isinstance(session_key, str) or not session_key:
        raise QuickCreateContextInvalid("The quick-create session is unavailable.")
    return salted_hmac(SESSION_FINGERPRINT_SALT, session_key).hexdigest()


def create_quick_create_context(actor, terminal, draft, barcode, *, session_key):
    from .services import normalize_barcode

    if not can_quick_create_product(actor) or not can_edit_draft(actor, draft, terminal):
        raise QuickCreateContextInvalid("The quick-create context cannot be created.")
    normalized = normalize_barcode(barcode)
    payload = {
        "actor_id": actor.pk,
        "shop_id": actor.shop_id,
        "terminal_id": terminal.pk,
        "draft_id": draft.pk,
        "barcode": normalized,
        "expected_version": draft.version,
        "session_fingerprint": _session_fingerprint(session_key),
    }
    return signing.dumps(payload, salt=QUICK_CREATE_SIGNING_SALT, compress=True)


def read_quick_create_context(token, actor, *, session_key, max_age=QUICK_CREATE_MAX_AGE):
    try:
        payload = signing.loads(token, salt=QUICK_CREATE_SIGNING_SALT, max_age=max_age)
        expected_fingerprint = _session_fingerprint(session_key)
        supplied_fingerprint = payload["session_fingerprint"]
        context = QuickCreateContext(
            actor_id=int(payload["actor_id"]),
            shop_id=int(payload["shop_id"]),
            terminal_id=int(payload["terminal_id"]),
            draft_id=int(payload["draft_id"]),
            barcode=str(payload["barcode"]),
            expected_version=int(payload["expected_version"]),
        )
    except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
        raise QuickCreateContextInvalid("The quick-create context is invalid or expired.") from exc

    if not constant_time_compare(str(supplied_fingerprint), expected_fingerprint):
        raise QuickCreateContextInvalid("The quick-create session has changed.")
    if (
        not can_quick_create_product(actor)
        or context.actor_id != actor.pk
        or context.shop_id != actor.shop_id
        or context.expected_version < 1
    ):
        raise QuickCreateContextInvalid("The quick-create actor context has changed.")

    try:
        terminal = resolve_pos_terminal(actor)
        draft = Order.objects.select_related("shop", "terminal", "current_cashier").get(
            pk=context.draft_id,
            shop_id=actor.shop_id,
            terminal_id=terminal.pk,
            status=Order.Status.DRAFT,
        )
    except (PermissionDenied, TerminalUnavailable, Order.DoesNotExist) as exc:
        raise QuickCreateContextInvalid("The quick-create order is no longer available.") from exc

    from .services import normalize_barcode

    if (
        context.terminal_id != terminal.pk
        or draft.version != context.expected_version
        or draft.current_cashier_id != actor.pk
        or normalize_barcode(context.barcode) != context.barcode
    ):
        raise QuickCreateContextInvalid("The quick-create order context has changed.")
    return context
