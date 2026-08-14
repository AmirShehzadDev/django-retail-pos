from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.catalog.models import Product
from apps.catalog.policies import can_manage_catalog
from apps.core.audit import record
from apps.core.models import AuditEvent

from .models import InventoryMovement

DEFAULT_RECEIPT_REASON = "Manual stock receipt"


def _lock_active_actor(actor):
    user_model = get_user_model()
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        raise PermissionDenied("An active inventory manager is required.")
    try:
        return user_model.objects.select_for_update().get(pk=actor_id, is_active=True)
    except user_model.DoesNotExist as exc:
        raise PermissionDenied("An active inventory manager is required.") from exc


def _lock_product(product_id):
    return Product.objects.select_for_update().select_related("shop").get(pk=product_id)


def _require_integer(value, *, field, nonzero=False, positive=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError({field: "Enter a whole number."})
    if positive and value <= 0:
        raise ValidationError({field: "Enter a whole number greater than zero."})
    if nonzero and value == 0:
        raise ValidationError({field: "Enter a non-zero whole number."})
    return value


def _require_stock_permission(actor, product):
    if not can_manage_catalog(actor) or actor.shop_id != product.shop_id:
        raise PermissionDenied("You cannot change stock for this product.")
    if not product.is_active:
        raise ValidationError("Reactivate this product before changing its stock.")


def _apply_movement(*, actor, product, movement_type, quantity_change, reason):
    if movement_type not in {
        InventoryMovement.MovementType.RECEIPT,
        InventoryMovement.MovementType.ADJUSTMENT,
    }:
        raise ValidationError("This movement type is not available in inventory management.")

    balance_after = product.stock_on_hand + quantity_change
    product.stock_on_hand = balance_after
    product.save(update_fields=["stock_on_hand", "updated_at"])
    movement = InventoryMovement(
        shop=product.shop,
        product=product,
        movement_type=movement_type,
        quantity_change=quantity_change,
        balance_after=balance_after,
        actor=actor,
        reason=reason,
    )
    movement.full_clean()
    movement.save()
    return movement


def apply_sale_movement(*, actor, product, order_item, order_number):
    """Apply a sale to an already locked product inside the checkout transaction."""
    quantity = _require_integer(order_item.quantity, field="quantity", positive=True)
    if (
        product.pk != order_item.product_id
        or product.shop_id != actor.shop_id
        or order_item.order.shop_id != actor.shop_id
    ):
        raise ValidationError("The sale movement has an invalid shop or product source.")
    quantity_change = -quantity
    balance_after = product.stock_on_hand + quantity_change
    product.stock_on_hand = balance_after
    product.save(update_fields=["stock_on_hand", "updated_at"])
    movement = InventoryMovement(
        shop=product.shop,
        product=product,
        movement_type=InventoryMovement.MovementType.SALE,
        quantity_change=quantity_change,
        balance_after=balance_after,
        actor=actor,
        reason=f"Sale {order_number}",
        order_item=order_item,
    )
    movement.full_clean()
    movement.save()
    return movement


def apply_return_movement(*, actor, product, return_item, return_number):
    """Restock one immutable return line inside the correction transaction."""
    quantity = _require_integer(return_item.quantity, field="quantity", positive=True)
    if (
        product.pk != return_item.order_item.product_id
        or product.shop_id != actor.shop_id
        or return_item.sales_return.shop_id != actor.shop_id
    ):
        raise ValidationError("The return movement has an invalid shop or product source.")
    balance_after = product.stock_on_hand + quantity
    product.stock_on_hand = balance_after
    product.save(update_fields=["stock_on_hand", "updated_at"])
    movement = InventoryMovement(
        shop=product.shop,
        product=product,
        movement_type=InventoryMovement.MovementType.RETURN,
        quantity_change=quantity,
        balance_after=balance_after,
        actor=actor,
        reason=f"Return {return_number}",
        return_item=return_item,
    )
    movement.full_clean()
    movement.save()
    return movement


def apply_void_movement(*, actor, product, order_void, order_item, order_number):
    """Reverse one immutable sale line inside the void transaction."""
    quantity = _require_integer(order_item.quantity, field="quantity", positive=True)
    if (
        product.pk != order_item.product_id
        or product.shop_id != actor.shop_id
        or order_void.shop_id != actor.shop_id
        or order_void.order_id != order_item.order_id
    ):
        raise ValidationError("The void movement has an invalid shop or product source.")
    balance_after = product.stock_on_hand + quantity
    product.stock_on_hand = balance_after
    product.save(update_fields=["stock_on_hand", "updated_at"])
    movement = InventoryMovement(
        shop=product.shop,
        product=product,
        movement_type=InventoryMovement.MovementType.VOID,
        quantity_change=quantity,
        balance_after=balance_after,
        actor=actor,
        reason=f"Void {order_number}",
        order_void=order_void,
        voided_order_item=order_item,
    )
    movement.full_clean()
    movement.save()
    return movement


@transaction.atomic
def receive_stock(*, actor, product_id, quantity, note=""):
    actor = _lock_active_actor(actor)
    product = _lock_product(product_id)
    _require_stock_permission(actor, product)
    quantity = _require_integer(quantity, field="quantity", positive=True)

    reason = (note or "").strip() or DEFAULT_RECEIPT_REASON
    if len(reason) > 500:
        raise ValidationError({"note": "Ensure this value has at most 500 characters."})

    movement = _apply_movement(
        actor=actor,
        product=product,
        movement_type=InventoryMovement.MovementType.RECEIPT,
        quantity_change=quantity,
        reason=reason,
    )
    return product, movement


@transaction.atomic
def adjust_stock(*, actor, product_id, quantity_change, reason):
    actor = _lock_active_actor(actor)
    product = _lock_product(product_id)
    _require_stock_permission(actor, product)
    quantity_change = _require_integer(
        quantity_change,
        field="quantity_change",
        nonzero=True,
    )

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "Explain why this stock correction is needed."})
    if len(reason) > 500:
        raise ValidationError({"reason": "Ensure this value has at most 500 characters."})

    balance_before = product.stock_on_hand
    movement = _apply_movement(
        actor=actor,
        product=product,
        movement_type=InventoryMovement.MovementType.ADJUSTMENT,
        quantity_change=quantity_change,
        reason=reason,
    )
    record(
        shop=product.shop,
        actor=actor,
        action=AuditEvent.Action.INVENTORY_ADJUSTED,
        target_type=AuditEvent.TargetType.PRODUCT,
        target_identifier=product.pk,
        after_values={
            "movement_id": movement.pk,
            "quantity_change": quantity_change,
            "reason": reason,
            "balance_before": balance_before,
            "balance_after": product.stock_on_hand,
        },
    )
    return product, movement
