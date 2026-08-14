from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, DecimalException, Inexact, Rounded, localcontext
from enum import StrEnum

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import DecimalValidator
from django.db import IntegrityError, transaction

from apps.catalog.models import Product
from apps.core.audit import record
from apps.core.models import AuditEvent

from .exceptions import (
    BarcodeNowKnown,
    DraftLimitReached,
    DraftTakeoverRequired,
    DraftVersionConflict,
)
from .models import Order, OrderItem
from .policies import can_create_draft, can_edit_draft, can_take_over_draft, can_use_pos
from .terminals import resolve_pos_terminal

POSTGRESQL_POSITIVE_BIGINT_MAX = 9_223_372_036_854_775_807
DECIMAL_CALCULATION_PRECISION = 50
ZERO_MONEY = Decimal("0.00")


class ScanStatus(StrEnum):
    ADDED = "ADDED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ScanOutcome:
    status: ScanStatus
    draft_id: int
    version: int
    barcode: str
    order: Order | None = None

    @property
    def is_unknown(self):
        return self.status == ScanStatus.UNKNOWN


def normalize_barcode(value):
    if value is None or isinstance(value, bool):
        normalized = ""
    else:
        normalized = str(value).strip()
    if not normalized:
        raise ValidationError({"barcode": "Scan or enter a barcode."})
    if len(normalized) > 64:
        raise ValidationError({"barcode": "Ensure this value has at most 64 characters."})
    return normalized


def _positive_bigint(value, *, field):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError({field: "Enter a whole number."})
    if value <= 0:
        raise ValidationError({field: "Enter a whole number greater than zero."})
    if value > POSTGRESQL_POSITIVE_BIGINT_MAX:
        raise ValidationError({field: "This value is too large."})
    return value


def _expected_version(value):
    return _positive_bigint(value, field="expected_version")


def _lock_active_actor(actor):
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        raise PermissionDenied("An active sales user is required.")
    user_model = get_user_model()
    try:
        locked = (
            user_model.objects.select_for_update(of=("self",))
            .select_related("shop")
            .get(pk=actor_id, is_active=True)
        )
    except user_model.DoesNotExist as exc:
        raise PermissionDenied("An active sales user is required.") from exc
    if not can_use_pos(locked):
        raise PermissionDenied("You cannot use the POS.")
    return locked


def _lock_draft(actor, terminal, draft_id, expected_version):
    try:
        draft = (
            Order.objects.select_for_update(of=("self",))
            .select_related("shop", "terminal", "created_by", "current_cashier")
            .get(pk=draft_id, shop_id=actor.shop_id, terminal_id=terminal.pk)
        )
    except (TypeError, ValueError) as exc:
        raise Order.DoesNotExist from exc
    if (
        draft.shop_id != terminal.shop_id
        or draft.created_by.shop_id != actor.shop_id
        or draft.current_cashier.shop_id != actor.shop_id
    ):
        raise ValidationError("This order has an invalid shop assignment.")
    if draft.status != Order.Status.DRAFT or draft.slot not in {1, 2, 3}:
        raise ValidationError("This order is no longer active.")
    expected_version = _expected_version(expected_version)
    if draft.version != expected_version:
        raise DraftVersionConflict(draft.pk, expected_version, draft.version)
    return draft


def _require_editable(actor, draft, terminal):
    if not can_edit_draft(actor, draft, terminal):
        raise DraftTakeoverRequired(draft.pk, draft.current_cashier_id)


def _next_version(draft):
    if draft.version >= POSTGRESQL_POSITIVE_BIGINT_MAX:
        raise ValidationError("This order cannot accept another change.")
    return draft.version + 1


def _save_material_change(draft, *, subtotal=None, update_fields=()):
    if subtotal is not None:
        draft.subtotal = subtotal
    draft.version = _next_version(draft)
    fields = list(update_fields)
    if subtotal is not None:
        fields.append("subtotal")
    fields.extend(["version", "updated_at"])
    draft.save(update_fields=list(dict.fromkeys(fields)))
    return draft


def _create_order(actor, terminal, slot):
    try:
        with transaction.atomic():
            return Order.objects.create(
                shop=actor.shop,
                terminal=terminal,
                slot=slot,
                status=Order.Status.DRAFT,
                created_by=actor,
                current_cashier=actor,
                subtotal=ZERO_MONEY,
                version=1,
            )
    except IntegrityError as exc:
        raise DraftLimitReached("No additional order tab is available.") from exc


def _lowest_free_slot(terminal):
    occupied = set(
        Order.objects.filter(terminal=terminal, status=Order.Status.DRAFT).values_list(
            "slot", flat=True
        )
    )
    return next((slot for slot in (1, 2, 3) if slot not in occupied), None)


@transaction.atomic
def start_workspace(actor):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    if not can_create_draft(actor, terminal):
        raise PermissionDenied("You cannot create an order on this terminal.")
    existing = (
        Order.objects.filter(terminal=terminal, shop=actor.shop, status=Order.Status.DRAFT)
        .order_by("slot")
        .first()
    )
    if existing:
        return existing
    return _create_order(actor, terminal, 1)


@transaction.atomic
def create_draft(actor):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    if not can_create_draft(actor, terminal):
        raise PermissionDenied("You cannot create an order on this terminal.")
    slot = _lowest_free_slot(terminal)
    if slot is None:
        raise DraftLimitReached("All three order tabs are already in use.")
    return _create_order(actor, terminal, slot)


def _lock_product(actor, product_id):
    try:
        return Product.objects.select_for_update().get(pk=product_id, shop_id=actor.shop_id)
    except (TypeError, ValueError) as exc:
        raise Product.DoesNotExist from exc


@contextmanager
def _money_context():
    with localcontext() as context:
        context.prec = max(context.prec, DECIMAL_CALCULATION_PRECISION)
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        yield context


def _validate_money(value, *, max_digits, decimal_places, field):
    try:
        DecimalValidator(max_digits, decimal_places)(value)
    except ValidationError as exc:
        raise ValidationError({field: "This amount is outside the supported range."}) from exc
    return value


def _calculate_line_total(unit_price, quantity):
    try:
        with _money_context():
            total = unit_price * Decimal(quantity)
    except DecimalException as exc:
        raise ValidationError("The line total is outside the supported range.") from exc
    return _validate_money(total, max_digits=38, decimal_places=2, field="line_total")


def _recalculate_subtotal(order, *, items=None):
    line_totals = (
        [item.line_total for item in items]
        if items is not None
        else OrderItem.objects.filter(order=order)
        .order_by("id")
        .values_list("line_total", flat=True)
    )
    try:
        with _money_context():
            subtotal = sum(line_totals, ZERO_MONEY)
    except DecimalException as exc:
        raise ValidationError("The order total is outside the supported range.") from exc
    return _validate_money(subtotal, max_digits=38, decimal_places=2, field="subtotal")


def _require_active_product(product):
    if not product.is_active:
        raise ValidationError("This product is unavailable in the POS.")


def _add_locked_product(draft, product):
    _require_active_product(product)
    try:
        item = OrderItem.objects.select_for_update().get(order=draft, product=product)
    except OrderItem.DoesNotExist:
        item = OrderItem(
            order=draft,
            product=product,
            product_name=product.name,
            product_barcode=product.barcode,
            unit_price=product.selling_price,
            quantity=1,
            line_total=_calculate_line_total(product.selling_price, 1),
        )
        item.save()
    else:
        quantity = _positive_bigint(item.quantity + 1, field="quantity")
        item.quantity = quantity
        item.line_total = _calculate_line_total(item.unit_price, quantity)
        item.save(update_fields=["quantity", "line_total", "updated_at"])
    subtotal = _recalculate_subtotal(draft)
    return _save_material_change(draft, subtotal=subtotal)


@transaction.atomic
def add_product(actor, draft_id, expected_version, product_id):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    draft = _lock_draft(actor, terminal, draft_id, expected_version)
    _require_editable(actor, draft, terminal)
    product = _lock_product(actor, product_id)
    return _add_locked_product(draft, product)


@transaction.atomic
def set_item_quantity(actor, draft_id, expected_version, item_id, quantity):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    draft = _lock_draft(actor, terminal, draft_id, expected_version)
    _require_editable(actor, draft, terminal)
    quantity = _positive_bigint(quantity, field="quantity")

    try:
        discovered = (
            OrderItem.objects.filter(order=draft, pk=item_id)
            .values("id", "product_id", "quantity")
            .get()
        )
    except (OrderItem.DoesNotExist, TypeError, ValueError) as exc:
        raise OrderItem.DoesNotExist from exc
    product = _lock_product(actor, discovered["product_id"])
    try:
        item = OrderItem.objects.select_for_update().get(
            pk=discovered["id"], order=draft, product=product
        )
    except OrderItem.DoesNotExist:
        raise
    if item.quantity != discovered["quantity"]:
        raise ValidationError("The order line changed while it was being edited.")
    if quantity == item.quantity:
        return draft
    if quantity > item.quantity:
        _require_active_product(product)
    item.quantity = quantity
    item.line_total = _calculate_line_total(item.unit_price, quantity)
    item.save(update_fields=["quantity", "line_total", "updated_at"])
    subtotal = _recalculate_subtotal(draft)
    return _save_material_change(draft, subtotal=subtotal)


@transaction.atomic
def remove_item(actor, draft_id, expected_version, item_id):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    draft = _lock_draft(actor, terminal, draft_id, expected_version)
    _require_editable(actor, draft, terminal)
    try:
        item = OrderItem.objects.select_for_update().get(pk=item_id, order=draft)
    except (TypeError, ValueError) as exc:
        raise OrderItem.DoesNotExist from exc
    item.delete()
    subtotal = _recalculate_subtotal(draft)
    return _save_material_change(draft, subtotal=subtotal)


@transaction.atomic
def scan_barcode(actor, draft_id, expected_version, barcode):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    draft = _lock_draft(actor, terminal, draft_id, expected_version)
    _require_editable(actor, draft, terminal)
    normalized = normalize_barcode(barcode)
    try:
        product = Product.objects.select_for_update().get(shop_id=actor.shop_id, barcode=normalized)
    except Product.DoesNotExist:
        return ScanOutcome(
            status=ScanStatus.UNKNOWN,
            draft_id=draft.pk,
            version=draft.version,
            barcode=normalized,
        )
    _require_active_product(product)
    draft = _add_locked_product(draft, product)
    return ScanOutcome(
        status=ScanStatus.ADDED,
        draft_id=draft.pk,
        version=draft.version,
        barcode=normalized,
        order=draft,
    )


def _quick_create_price(value):
    if value is None or isinstance(value, bool):
        raise ValidationError({"selling_price": "Enter a valid selling price."})
    try:
        price = Product._meta.get_field("selling_price").to_python(value)
    except (TypeError, ValueError, DecimalException, ValidationError) as exc:
        raise ValidationError({"selling_price": "Enter a valid selling price."}) from exc
    if not price.is_finite() or price < ZERO_MONEY:
        raise ValidationError({"selling_price": "Selling price cannot be negative."})
    if price.as_tuple().exponent < -2:
        raise ValidationError({"selling_price": "Use at most two decimal places."})
    _validate_money(price, max_digits=12, decimal_places=2, field="selling_price")
    try:
        with _money_context():
            return price.quantize(Decimal("0.01"))
    except DecimalException as exc:
        raise ValidationError({"selling_price": "Enter a valid selling price."}) from exc


@transaction.atomic
def quick_create_and_add(actor, draft_id, expected_version, barcode, name, selling_price):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    draft = _lock_draft(actor, terminal, draft_id, expected_version)
    _require_editable(actor, draft, terminal)
    normalized_barcode = normalize_barcode(barcode)

    known = (
        Product.objects.select_for_update()
        .filter(shop_id=actor.shop_id, barcode=normalized_barcode)
        .first()
    )
    if known:
        raise BarcodeNowKnown(known.pk, known.is_active)

    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValidationError({"name": "Product name is required."})
    if len(normalized_name) > 200:
        raise ValidationError({"name": "Ensure this value has at most 200 characters."})
    price = _quick_create_price(selling_price)

    product = Product(
        shop=actor.shop,
        barcode=normalized_barcode,
        sku=None,
        name=normalized_name,
        selling_price=price,
        cost_price=None,
        stock_on_hand=0,
        created_by=actor,
        creation_source=Product.CreationSource.POS_QUICK_CREATE,
        needs_review=True,
        is_active=True,
    )
    try:
        with transaction.atomic():
            product.save(force_insert=True)
    except IntegrityError as exc:
        winner = Product.objects.filter(shop_id=actor.shop_id, barcode=normalized_barcode).first()
        if winner:
            raise BarcodeNowKnown(winner.pk, winner.is_active) from exc
        raise ValidationError("The product conflicts with another catalog record.") from exc

    record(
        shop=actor.shop,
        actor=actor,
        action=AuditEvent.Action.PRODUCT_QUICK_CREATED,
        target_type=AuditEvent.TargetType.PRODUCT,
        target_identifier=product.pk,
        after_values={
            "product_id": product.pk,
            "barcode": product.barcode,
            "name": product.name,
            "selling_price": format(product.selling_price, ".2f"),
            "creation_source": product.creation_source,
            "needs_review": product.needs_review,
            "draft_id": draft.pk,
        },
    )
    draft = _add_locked_product(draft, product)
    return product, draft


@transaction.atomic
def take_over_draft(actor, draft_id, expected_version):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    draft = _lock_draft(actor, terminal, draft_id, expected_version)
    if not can_take_over_draft(actor, draft, terminal):
        if draft.current_cashier_id == actor.pk:
            raise ValidationError("You are already handling this order.")
        raise PermissionDenied("You cannot resume this order.")

    previous_cashier_id = draft.current_cashier_id
    item_count = OrderItem.objects.filter(order=draft).count()
    draft.current_cashier = actor
    _save_material_change(draft, update_fields=("current_cashier",))
    record(
        shop=actor.shop,
        actor=actor,
        action=AuditEvent.Action.DRAFT_TAKEN_OVER,
        target_type=AuditEvent.TargetType.ORDER,
        target_identifier=draft.pk,
        before_values={"current_cashier_id": previous_cashier_id},
        after_values={
            "creator_id": draft.created_by_id,
            "current_cashier_id": actor.pk,
            "slot": draft.slot,
            "item_count": item_count,
            "subtotal": format(draft.subtotal, ".2f"),
        },
    )
    return draft


@transaction.atomic
def clear_draft(actor, draft_id, expected_version):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    draft = _lock_draft(actor, terminal, draft_id, expected_version)
    _require_editable(actor, draft, terminal)
    items = list(OrderItem.objects.select_for_update().filter(order=draft).order_by("id"))
    if not items:
        raise ValidationError("This order is already empty.")

    OrderItem.objects.filter(pk__in=[item.pk for item in items]).delete()
    return _save_material_change(draft, subtotal=ZERO_MONEY)


@transaction.atomic
def close_empty_draft(actor, draft_id, expected_version):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    drafts = list(
        Order.objects.select_for_update(of=("self",))
        .filter(shop_id=actor.shop_id, terminal_id=terminal.pk, status=Order.Status.DRAFT)
        .select_related("shop", "terminal", "created_by", "current_cashier")
        .order_by("slot", "id")
    )
    try:
        normalized_id = int(draft_id)
        draft = next(candidate for candidate in drafts if candidate.pk == normalized_id)
    except (TypeError, ValueError, StopIteration) as exc:
        raise Order.DoesNotExist from exc

    if draft.created_by.shop_id != actor.shop_id or draft.current_cashier.shop_id != actor.shop_id:
        raise ValidationError("This order has an invalid shop assignment.")
    submitted_version = _expected_version(expected_version)
    if draft.version != submitted_version:
        raise DraftVersionConflict(draft.pk, submitted_version, draft.version)
    _require_editable(actor, draft, terminal)

    items = list(OrderItem.objects.select_for_update().filter(order=draft).order_by("id"))
    if items or draft.subtotal != ZERO_MONEY:
        raise ValidationError("Clear the order before closing this tab.")

    remaining = [candidate for candidate in drafts if candidate.pk != draft.pk]
    if not remaining:
        raise ValidationError("The only active order tab cannot be closed.")
    selected = next(
        (candidate for candidate in remaining if candidate.slot > draft.slot),
        None,
    )
    if selected is None:
        selected = max(
            (candidate for candidate in remaining if candidate.slot < draft.slot),
            key=lambda candidate: candidate.slot,
        )
    draft.delete()
    return selected
