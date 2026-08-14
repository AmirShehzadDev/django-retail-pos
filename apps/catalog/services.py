from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from apps.core.audit import record
from apps.core.models import AuditEvent

from .models import Product
from .policies import can_edit_product, can_manage_catalog


def normalize_optional_identifier(value):
    normalized = (value or "").strip()
    return normalized or None


def normalize_product_values(*, name, barcode, sku, selling_price, cost_price):
    selling_price = Product._meta.get_field("selling_price").to_python(selling_price)
    cost_price = Product._meta.get_field("cost_price").to_python(cost_price)
    return {
        "name": (name or "").strip(),
        "barcode": normalize_optional_identifier(barcode),
        "sku": normalize_optional_identifier(sku),
        "selling_price": selling_price,
        "cost_price": cost_price,
    }


def _lock_active_actor(actor):
    user_model = get_user_model()
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        raise PermissionDenied("An active catalog manager is required.")
    try:
        locked = user_model.objects.select_for_update().get(pk=actor_id, is_active=True)
    except user_model.DoesNotExist as exc:
        raise PermissionDenied("An active catalog manager is required.") from exc
    if not can_manage_catalog(locked):
        raise PermissionDenied("You cannot manage the product catalog.")
    return locked


def _lock_product(product_id):
    return Product.objects.select_for_update().get(pk=product_id)


def _identifier_conflict(error):
    message = str(error).casefold()
    if "barcode" in message:
        return ValidationError({"barcode": "A product with this barcode already exists."})
    if "sku" in message:
        return ValidationError({"sku": "A product with this SKU already exists."})
    return ValidationError("The product conflicts with another catalog record.")


def _validated_save(product):
    product.full_clean()
    try:
        # The savepoint allows an expected uniqueness race to be translated without
        # leaving the surrounding business transaction unusable.
        with transaction.atomic():
            product.save()
    except IntegrityError as error:
        raise _identifier_conflict(error) from error


def _audit_price(value):
    if value is None:
        return None
    return format(Decimal(value), ".2f")


@transaction.atomic
def create_product(*, actor, name, barcode=None, sku=None, selling_price=None, cost_price=None):
    actor = _lock_active_actor(actor)
    product = Product(
        **normalize_product_values(
            name=name,
            barcode=barcode,
            sku=sku,
            selling_price=selling_price,
            cost_price=cost_price,
        ),
        shop=actor.shop,
        created_by=actor,
        creation_source=Product.CreationSource.CATALOG,
        needs_review=False,
        is_active=True,
        stock_on_hand=0,
    )
    _validated_save(product)
    return product


@transaction.atomic
def create_product_with_optional_receipt(
    *,
    actor,
    name,
    barcode=None,
    sku=None,
    selling_price=None,
    cost_price=None,
    quantity_received_now=None,
    receipt_note="",
):
    product = create_product(
        actor=actor,
        name=name,
        barcode=barcode,
        sku=sku,
        selling_price=selling_price,
        cost_price=cost_price,
    )
    if quantity_received_now is None:
        return product, None

    # Imported locally so catalog models/services do not depend on inventory at import time.
    from apps.inventory.services import receive_stock

    product, movement = receive_stock(
        actor=actor,
        product_id=product.pk,
        quantity=quantity_received_now,
        note=receipt_note,
    )
    return product, movement


@transaction.atomic
def update_product(
    *,
    actor,
    product_id,
    name,
    barcode=None,
    sku=None,
    selling_price=None,
    cost_price=None,
):
    actor = _lock_active_actor(actor)
    product = _lock_product(product_id)
    if not can_edit_product(actor, product):
        raise PermissionDenied("You cannot edit this product.")

    values = normalize_product_values(
        name=name,
        barcode=barcode,
        sku=sku,
        selling_price=selling_price,
        cost_price=cost_price,
    )
    before_prices = {}
    after_prices = {}
    changed = False
    for field, value in values.items():
        old_value = getattr(product, field)
        if old_value != value:
            changed = True
            setattr(product, field, value)
            if field in {"selling_price", "cost_price"}:
                before_prices[field] = _audit_price(old_value)
                after_prices[field] = _audit_price(value)

    if not changed:
        return product, False

    _validated_save(product)
    if before_prices:
        record(
            shop=product.shop,
            actor=actor,
            action=AuditEvent.Action.PRODUCT_PRICE_CHANGED,
            target_type=AuditEvent.TargetType.PRODUCT,
            target_identifier=product.pk,
            before_values=before_prices,
            after_values=after_prices,
        )
    return product, True


@transaction.atomic
def set_product_active(*, actor, product_id, is_active):
    actor = _lock_active_actor(actor)
    product = _lock_product(product_id)
    if not can_edit_product(actor, product):
        raise PermissionDenied("You cannot change this product's status.")
    requested = bool(is_active)
    if product.is_active == requested:
        return product, False
    product.is_active = requested
    product.save(update_fields=["is_active", "updated_at"])
    return product, True


@transaction.atomic
def mark_product_reviewed(*, actor, product_id):
    actor = _lock_active_actor(actor)
    product = _lock_product(product_id)
    if not can_edit_product(actor, product):
        raise PermissionDenied("You cannot review this product.")
    if not product.needs_review:
        return product, False
    product.needs_review = False
    product.save(update_fields=["needs_review", "updated_at"])
    return product, True
