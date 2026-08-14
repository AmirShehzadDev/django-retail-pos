from dataclasses import dataclass
from decimal import Decimal, DecimalException

from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.core.audit import record
from apps.core.models import AuditEvent
from apps.core.sequences import allocate_order_number
from apps.inventory.services import apply_sale_movement

from .models import Order, OrderItem, Payment
from .services import (
    POSTGRESQL_POSITIVE_BIGINT_MAX,
    ZERO_MONEY,
    _calculate_line_total,
    _create_order,
    _lock_active_actor,
    _money_context,
    _recalculate_subtotal,
    _require_editable,
    _validate_money,
)
from .terminals import resolve_pos_terminal


@dataclass(frozen=True)
class StockShortage:
    product_id: int
    product_name: str
    product_barcode: str | None
    balance_before: int
    quantity: int
    balance_after: int


@dataclass(frozen=True)
class CheckoutResult:
    order: Order
    payment: Payment
    replacement: Order | None
    already_completed: bool = False


def parse_cash_received(value):
    if isinstance(value, bool) or value is None:
        raise ValidationError({"cash_received": "Enter a valid PKR amount."})
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (DecimalException, TypeError, ValueError) as exc:
        raise ValidationError({"cash_received": "Enter a valid PKR amount."}) from exc
    if not amount.is_finite():
        raise ValidationError({"cash_received": "Enter a valid PKR amount."})
    if amount.as_tuple().exponent < -2:
        raise ValidationError({"cash_received": "Use at most two decimal places."})
    if amount < ZERO_MONEY:
        raise ValidationError({"cash_received": "Cash received cannot be negative."})
    try:
        DecimalValidator(38, 2)(amount)
        with _money_context():
            return amount.quantize(Decimal("0.01"))
    except (DecimalException, ValidationError) as exc:
        raise ValidationError(
            {"cash_received": "This amount is outside the supported range."}
        ) from exc


def _change_amount(cash_received, total):
    try:
        with _money_context():
            change = cash_received - total
    except DecimalException as exc:
        raise ValidationError("The change amount is outside the supported range.") from exc
    return _validate_money(change, max_digits=38, decimal_places=2, field="change_given")


def shortage_rows(items, products):
    rows = []
    for item in sorted(items, key=lambda candidate: candidate.product_id):
        product = products[item.product_id]
        projected = product.stock_on_hand - item.quantity
        if projected < 0:
            rows.append(
                StockShortage(
                    product_id=product.pk,
                    product_name=item.product_name,
                    product_barcode=item.product_barcode,
                    balance_before=product.stock_on_hand,
                    quantity=item.quantity,
                    balance_after=projected,
                )
            )
    return tuple(rows)


@transaction.atomic
def complete_cash_checkout(actor, draft_id, expected_version, cash_received):
    actor = _lock_active_actor(actor)
    terminal = resolve_pos_terminal(actor, for_update=True)
    try:
        draft = (
            Order.objects.select_for_update(of=("self",))
            .select_related("shop", "terminal", "created_by", "current_cashier")
            .get(pk=draft_id, shop_id=actor.shop_id, terminal_id=terminal.pk)
        )
    except (TypeError, ValueError) as exc:
        raise Order.DoesNotExist from exc

    if draft.status == Order.Status.COMPLETED:
        payment = Payment.objects.get(order=draft, shop_id=actor.shop_id)
        replacement = (
            Order.objects.filter(
                terminal=terminal,
                slot=draft.slot,
                status=Order.Status.DRAFT,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        return CheckoutResult(draft, payment, replacement, already_completed=True)
    if draft.status != Order.Status.DRAFT:
        raise ValidationError("This order is no longer active.")
    try:
        parsed_version = int(expected_version)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"expected_version": "Enter a valid order version."}) from exc
    if draft.version != parsed_version:
        from .exceptions import DraftVersionConflict

        raise DraftVersionConflict(draft.pk, parsed_version, draft.version)
    _require_editable(actor, draft, terminal)

    discovered = list(
        OrderItem.objects.filter(order=draft).order_by("id").values_list("id", "product_id")
    )
    if not discovered:
        raise ValidationError("Add at least one product before checkout.")
    product_ids = sorted({product_id for _, product_id in discovered})
    products = {
        product.pk: product
        for product in Product.objects.select_for_update(of=("self",))
        .filter(shop_id=actor.shop_id, pk__in=product_ids)
        .order_by("id")
    }
    if len(products) != len(product_ids):
        raise ValidationError("One or more products are no longer available.")
    items = list(
        OrderItem.objects.select_for_update(of=("self",))
        .select_related("order")
        .filter(order=draft)
        .order_by("id")
    )
    if [(item.pk, item.product_id) for item in items] != discovered:
        raise ValidationError("The order lines changed during checkout. Try again.")
    for item in items:
        product = products[item.product_id]
        if not product.is_active:
            raise ValidationError(f"{item.product_name} is inactive and cannot be sold.")
        if item.line_total != _calculate_line_total(item.unit_price, item.quantity):
            raise ValidationError("An order line total is inconsistent. Refresh the order.")

    subtotal = _recalculate_subtotal(draft, items=items)
    received = parse_cash_received(cash_received)
    change = _change_amount(received, subtotal)
    shortages = shortage_rows(items, products)
    order_number = allocate_order_number(actor.shop_id)

    draft.status = Order.Status.COMPLETED
    draft.order_number = order_number
    draft.completed_by = actor
    draft.completed_at = timezone.now()
    draft.subtotal = subtotal
    draft.rounding_adjustment = ZERO_MONEY
    draft.rounding_reason = ""
    draft.rounding_by = None
    draft.final_total = subtotal
    draft.shortage_acknowledged = bool(shortages)
    if draft.version >= POSTGRESQL_POSITIVE_BIGINT_MAX:
        raise ValidationError("This order cannot be completed because its version is exhausted.")
    draft.version += 1
    draft.save(
        update_fields=[
            "status",
            "order_number",
            "completed_by",
            "completed_at",
            "subtotal",
            "rounding_adjustment",
            "rounding_reason",
            "rounding_by",
            "final_total",
            "shortage_acknowledged",
            "version",
            "updated_at",
        ]
    )
    payment = Payment(
        shop=actor.shop,
        order=draft,
        method=Payment.Method.CASH,
        amount=subtotal,
        cash_received=received,
        change_given=change,
        processed_by=actor,
    )
    payment.full_clean()
    payment.save()

    for item in sorted(items, key=lambda candidate: candidate.product_id):
        apply_sale_movement(
            actor=actor,
            product=products[item.product_id],
            order_item=item,
            order_number=order_number,
        )

    if shortages:
        record(
            shop=actor.shop,
            actor=actor,
            action=AuditEvent.Action.STOCK_SHORTAGE_ACKNOWLEDGED,
            target_type=AuditEvent.TargetType.ORDER,
            target_identifier=order_number,
            after_values={
                "shortages": [
                    {
                        "product_id": row.product_id,
                        "product_name": row.product_name,
                        "product_barcode": row.product_barcode,
                        "balance_before": row.balance_before,
                        "quantity": row.quantity,
                        "balance_after": row.balance_after,
                    }
                    for row in shortages
                ]
            },
        )

    replacement = _create_order(actor, terminal, draft.slot)
    return CheckoutResult(draft, payment, replacement)
