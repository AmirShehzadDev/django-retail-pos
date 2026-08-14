from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class ImmutableMovementQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(_("Inventory movements cannot be changed."))

    def delete(self):
        raise ValidationError(_("Inventory movements cannot be deleted."))


class InventoryMovement(models.Model):
    class MovementType(models.TextChoices):
        RECEIPT = "RECEIPT", _("Receipt")
        ADJUSTMENT = "ADJUSTMENT", _("Adjustment")
        SALE = "SALE", _("Sale")
        RETURN = "RETURN", _("Return")
        VOID = "VOID", _("Void")

    shop = models.ForeignKey(
        "core.Shop",
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="movements",
    )
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    quantity_change = models.BigIntegerField()
    balance_after = models.BigIntegerField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )
    reason = models.CharField(max_length=500)
    order_item = models.ForeignKey(
        "sales.OrderItem",
        on_delete=models.PROTECT,
        related_name="sale_movements",
        null=True,
        blank=True,
    )
    return_item = models.OneToOneField(
        "sales.SalesReturnItem",
        on_delete=models.PROTECT,
        related_name="inventory_movement",
        null=True,
        blank=True,
    )
    order_void = models.ForeignKey(
        "sales.OrderVoid",
        on_delete=models.PROTECT,
        related_name="inventory_movements",
        null=True,
        blank=True,
    )
    voided_order_item = models.OneToOneField(
        "sales.OrderItem",
        on_delete=models.PROTECT,
        related_name="void_movement",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutableMovementQuerySet)()

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_change=0),
                name="inventory_quantity_not_zero",
            ),
            models.CheckConstraint(
                condition=(~models.Q(movement_type="RECEIPT") | models.Q(quantity_change__gt=0)),
                name="inventory_receipt_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="inventory_reason_not_empty",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        movement_type="SALE",
                        order_item__isnull=False,
                        quantity_change__lt=0,
                    )
                    | (~models.Q(movement_type="SALE") & models.Q(order_item__isnull=True))
                ),
                name="inventory_sale_source_state",
            ),
            models.UniqueConstraint(
                fields=["order_item"],
                condition=models.Q(movement_type="SALE"),
                name="inventory_sale_order_item_uq",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        movement_type="RETURN",
                        return_item__isnull=False,
                        order_item__isnull=True,
                        order_void__isnull=True,
                        voided_order_item__isnull=True,
                        quantity_change__gt=0,
                    )
                    | models.Q(
                        movement_type="VOID",
                        return_item__isnull=True,
                        order_item__isnull=True,
                        order_void__isnull=False,
                        voided_order_item__isnull=False,
                        quantity_change__gt=0,
                    )
                    | (
                        models.Q(
                            movement_type="SALE",
                            order_item__isnull=False,
                            return_item__isnull=True,
                            order_void__isnull=True,
                            voided_order_item__isnull=True,
                            quantity_change__lt=0,
                        )
                    )
                    | (
                        models.Q(
                            movement_type__in=["RECEIPT", "ADJUSTMENT"],
                            order_item__isnull=True,
                            return_item__isnull=True,
                            order_void__isnull=True,
                            voided_order_item__isnull=True,
                        )
                    )
                ),
                name="inventory_movement_source_shape",
            ),
        ]
        indexes = [
            models.Index(
                fields=["shop", "-created_at"],
                name="inventory_shop_created_idx",
            ),
            models.Index(
                fields=["product", "-created_at"],
                name="inventory_product_created_idx",
            ),
            models.Index(
                fields=["shop", "movement_type", "-created_at"],
                name="inventory_shop_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.product}: {self.quantity_change:+d}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(_("Inventory movements cannot be changed."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Inventory movements cannot be deleted."))
