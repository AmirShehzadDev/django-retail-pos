from django.conf import settings
from django.core.exceptions import PermissionDenied

from apps.core.models import Terminal

from .exceptions import TerminalUnavailable
from .policies import can_use_pos


def normalize_configured_terminal_code(value):
    code = str(value).strip().upper()
    if not code or len(code) > 32:
        raise TerminalUnavailable("The configured POS terminal is unavailable.")
    return code


def resolve_pos_terminal(actor, *, for_update=False):
    if not can_use_pos(actor):
        raise PermissionDenied("An active sales user is required.")

    code = normalize_configured_terminal_code(settings.POS_TERMINAL_CODE)
    terminals = Terminal.objects
    if for_update:
        terminals = terminals.select_for_update(of=("self",))
    try:
        return terminals.get(
            shop_id=actor.shop_id,
            shop__is_active=True,
            code=code,
            is_active=True,
        )
    except (Terminal.DoesNotExist, Terminal.MultipleObjectsReturned) as exc:
        raise TerminalUnavailable("The configured POS terminal is unavailable.") from exc
