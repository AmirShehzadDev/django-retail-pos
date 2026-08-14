from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.catalog.models import Product
from apps.core.audit import record
from apps.core.models import AuditEvent
from apps.core.sequences import allocate_return_number
from apps.inventory.services import apply_return_movement, apply_void_movement

from .models import Order, OrderItem, OrderVoid, Payment, SalesReturn, SalesReturnItem
from .policies import MANAGER_ROLES, POS_ROLES

COMPLETED_ORDER_STATUSES = (
    Order.Status.COMPLETED,
    Order.Status.PARTIALLY_RETURNED,
    Order.Status.RETURNED,
    Order.Status.VOIDED,
)


@dataclass(frozen=True)
class CorrectionResult:
    correction: object
    payment: Payment
    already_processed: bool = False


def _lock_actor(actor, *, managers_only=False):
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        raise PermissionDenied("An active user is required.")
    roles = MANAGER_ROLES if managers_only else POS_ROLES
    try:
        locked = (
            get_user_model()
            .objects.select_for_update()
            .select_related("shop")
            .get(pk=actor_id, is_active=True, role__in=roles, shop__is_active=True)
        )
    except get_user_model().DoesNotExist as exc:
        raise PermissionDenied("You cannot process this correction.") from exc
    return locked


def _reason(value, *, required):
    normalized = str(value or "").strip()
    if required and not normalized:
        raise ValidationError({"reason": "Enter a reason."})
    if len(normalized) > 500:
        raise ValidationError({"reason": "Ensure this value has at most 500 characters."})
    return normalized


def _token(value):
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("A valid submission token is required.") from exc


def _validate_receipt(order):
    try:
        payment = Payment.objects.select_for_update().get(order=order)
    except Payment.DoesNotExist as exc:
        raise ValidationError("The original sale payment is missing.") from exc
    if (
        payment.shop_id != order.shop_id
        or payment.direction != Payment.Direction.RECEIPT
        or payment.amount != order.final_total
        or payment.cash_received is None
        or payment.change_given != payment.cash_received - payment.amount
    ):
        raise ValidationError("The original sale payment is inconsistent.")
    return payment


def _locked_items(order):
    items = list(
        OrderItem.objects.select_for_update()
        .select_related("product", "order")
        .filter(order=order)
        .order_by("pk")
    )
    if not items:
        raise ValidationError("The original order has no items.")
    for item in items:
        if (
            item.line_total != item.unit_price * item.quantity
            or item.product.shop_id != order.shop_id
        ):
            raise ValidationError("The original order items are inconsistent.")
    return items


def returnable_items(order):
    rows = list(
        order.items.annotate(returned_quantity=Coalesce(Sum("return_items__quantity"), 0))
        .select_related("product")
        .order_by("id")
    )
    for row in rows:
        row.remaining_quantity = row.quantity - row.returned_quantity
    return rows


@transaction.atomic
def complete_return(*, actor, order_id, request_token, reason, selections):
    actor = _lock_actor(actor)
    token = _token(request_token)
    order = Order.objects.select_for_update().select_related("shop").get(pk=order_id)
    if order.shop_id != actor.shop_id:
        raise PermissionDenied("You cannot return this order.")

    existing = (
        SalesReturn.objects.select_for_update().filter(shop=order.shop, request_token=token).first()
    )
    if existing:
        if existing.order_id != order.pk:
            raise ValidationError("This submission token was already used.")
        return CorrectionResult(existing, existing.refund_payment, True)

    if order.status not in {Order.Status.COMPLETED, Order.Status.PARTIALLY_RETURNED}:
        raise ValidationError("This order is no longer returnable.")
    if OrderVoid.objects.select_for_update().filter(order=order).exists():
        raise ValidationError("A voided order cannot be returned.")
    _validate_receipt(order)
    reason = _reason(reason, required=False)
    items = _locked_items(order)
    item_map = {item.pk: item for item in items}
    prior = {}
    for prior_item in (
        SalesReturnItem.objects.select_for_update().filter(sales_return__order=order).order_by("pk")
    ):
        prior[prior_item.order_item_id] = (
            prior.get(prior_item.order_item_id, 0) + prior_item.quantity
        )
    normalized = []
    seen = set()
    for selection in selections or ():
        try:
            item_id = int(selection["order_item_id"])
            quantity = int(selection["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Return selections are invalid.") from exc
        if (
            item_id in seen
            or item_id not in item_map
            or isinstance(selection.get("quantity"), bool)
        ):
            raise ValidationError("Return selections are invalid.")
        seen.add(item_id)
        if quantity <= 0:
            continue
        item = item_map[item_id]
        remaining = item.quantity - prior.get(item_id, 0)
        if quantity > remaining:
            raise ValidationError("A return quantity exceeds the remaining quantity.")
        disposition = selection.get("disposition")
        if disposition not in SalesReturnItem.Disposition.values:
            raise ValidationError("Choose a disposition for every returned item.")
        normalized.append((item, quantity, disposition))
    if not normalized:
        raise ValidationError("Return at least one item.")

    products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=sorted({item.product_id for item, _, _ in normalized}))
        .order_by("pk")
    }
    total_refund = sum(
        (item.unit_price * quantity for item, quantity, _ in normalized), Decimal("0.00")
    )
    return_number = allocate_return_number(order.shop_id)
    sales_return = SalesReturn.objects.create(
        shop=order.shop,
        return_number=return_number,
        order=order,
        processed_by=actor,
        reason=reason,
        total_refund=total_refund,
        request_token=token,
    )
    created_items = []
    for item, quantity, disposition in normalized:
        return_item = SalesReturnItem.objects.create(
            sales_return=sales_return,
            order_item=item,
            quantity=quantity,
            disposition=disposition,
            unit_refund=item.unit_price,
            line_refund=item.unit_price * quantity,
        )
        created_items.append(return_item)
        if disposition == SalesReturnItem.Disposition.RESTOCK:
            apply_return_movement(
                actor=actor,
                product=products[item.product_id],
                return_item=return_item,
                return_number=return_number,
            )
    payment = Payment.objects.create(
        shop=order.shop,
        sales_return=sales_return,
        direction=Payment.Direction.REFUND,
        method=Payment.Method.CASH,
        amount=total_refund,
        processed_by=actor,
    )
    newly_returned = {item_id: prior.get(item_id, 0) for item_id in item_map}
    for item, quantity, _ in normalized:
        newly_returned[item.pk] += quantity
    order.status = (
        Order.Status.RETURNED
        if all(newly_returned[item.pk] == item.quantity for item in items)
        else Order.Status.PARTIALLY_RETURNED
    )
    order.save(update_fields=["status", "updated_at"])
    record(
        shop=order.shop,
        actor=actor,
        action=AuditEvent.Action.ORDER_RETURNED,
        target_type=AuditEvent.TargetType.ORDER,
        target_identifier=order.order_number,
        after_values={
            "return_number": return_number,
            "refund": str(total_refund),
            "items": [
                {
                    "order_item_id": row.order_item_id,
                    "quantity": row.quantity,
                    "disposition": row.disposition,
                }
                for row in created_items
            ],
            "status": order.status,
            "reason": reason,
        },
    )
    return CorrectionResult(sales_return, payment)


@transaction.atomic
def void_order(*, actor, order_id, request_token, reason):
    actor = _lock_actor(actor, managers_only=True)
    token = _token(request_token)
    order = Order.objects.select_for_update().select_related("shop").get(pk=order_id)
    if order.shop_id != actor.shop_id:
        raise PermissionDenied("You cannot void this order.")
    existing_token = (
        OrderVoid.objects.select_for_update().filter(shop=order.shop, request_token=token).first()
    )
    if existing_token:
        if existing_token.order_id != order.pk:
            raise ValidationError("This submission token was already used.")
        return CorrectionResult(existing_token, existing_token.refund_payment, True)
    if (
        order.status != Order.Status.COMPLETED
        or SalesReturn.objects.select_for_update().filter(order=order).exists()
    ):
        raise ValidationError("This order is no longer eligible for voiding.")
    if OrderVoid.objects.select_for_update().filter(order=order).exists():
        raise ValidationError("This order was already voided.")
    receipt = _validate_receipt(order)
    reason = _reason(reason, required=True)
    items = _locked_items(order)
    products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=sorted({item.product_id for item in items}))
        .order_by("pk")
    }
    correction = OrderVoid.objects.create(
        shop=order.shop, order=order, processed_by=actor, reason=reason, request_token=token
    )
    payment = Payment.objects.create(
        shop=order.shop,
        order_void=correction,
        direction=Payment.Direction.REFUND,
        method=Payment.Method.CASH,
        amount=receipt.amount,
        processed_by=actor,
    )
    for item in items:
        apply_void_movement(
            actor=actor,
            product=products[item.product_id],
            order_void=correction,
            order_item=item,
            order_number=order.order_number,
        )
    order.status = Order.Status.VOIDED
    order.save(update_fields=["status", "updated_at"])
    record(
        shop=order.shop,
        actor=actor,
        action=AuditEvent.Action.ORDER_VOIDED,
        target_type=AuditEvent.TargetType.ORDER,
        target_identifier=order.order_number,
        after_values={"refund": str(receipt.amount), "reason": reason, "status": order.status},
    )
    return CorrectionResult(correction, payment)
