import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Q
from django.utils.translation import gettext_lazy as _


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        DISCARDED = "DISCARDED", _("Discarded")
        COMPLETED = "COMPLETED", _("Completed")
        PARTIALLY_RETURNED = "PARTIALLY_RETURNED", _("Partially returned")
        RETURNED = "RETURNED", _("Returned")
        VOIDED = "VOIDED", _("Voided")

    shop = models.ForeignKey(
        "core.Shop",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    terminal = models.ForeignKey(
        "core.Terminal",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    slot = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_orders",
    )
    current_cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="current_orders",
    )
    subtotal = models.DecimalField(
        max_digits=38,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    version = models.PositiveBigIntegerField(default=1)
    order_number = models.CharField(max_length=32, null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="completed_orders",
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    rounding_adjustment = models.DecimalField(
        max_digits=38,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    rounding_reason = models.CharField(max_length=500, blank=True, default="")
    rounding_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rounded_orders",
        null=True,
        blank=True,
    )
    final_total = models.DecimalField(max_digits=38, decimal_places=2, null=True, blank=True)
    shortage_acknowledged = models.BooleanField(default=False)
    discarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="discarded_orders",
        null=True,
        blank=True,
    )
    discard_reason = models.CharField(max_length=500, blank=True, default="")
    discard_was_empty = models.BooleanField(default=False)
    discarded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "DRAFT",
                        "DISCARDED",
                        "COMPLETED",
                        "PARTIALLY_RETURNED",
                        "RETURNED",
                        "VOIDED",
                    ]
                ),
                name="sales_order_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(slot__gte=1, slot__lte=3),
                name="sales_order_slot_1_3",
            ),
            models.UniqueConstraint(
                fields=["terminal", "slot"],
                condition=Q(status="DRAFT"),
                name="sales_active_terminal_slot_uq",
            ),
            models.UniqueConstraint(
                fields=["shop", "order_number"],
                condition=Q(order_number__isnull=False),
                name="sales_order_shop_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="sales_order_subtotal_nonneg",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="sales_order_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="DRAFT",
                        discarded_by__isnull=True,
                        discarded_at__isnull=True,
                        discard_was_empty=False,
                        discard_reason="",
                    )
                    | Q(
                        status="DISCARDED",
                        discarded_by__isnull=False,
                        discarded_at__isnull=False,
                    )
                    | Q(
                        status__in=["COMPLETED", "PARTIALLY_RETURNED", "RETURNED", "VOIDED"],
                        discarded_by__isnull=True,
                        discarded_at__isnull=True,
                        discard_was_empty=False,
                        discard_reason="",
                    )
                ),
                name="sales_order_discard_state",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status__in=["DRAFT", "COMPLETED", "PARTIALLY_RETURNED", "RETURNED", "VOIDED"])
                    | Q(
                        status="DISCARDED",
                        discard_was_empty=True,
                        discard_reason="",
                        subtotal=Decimal("0.00"),
                    )
                    | (Q(status="DISCARDED", discard_was_empty=False) & ~Q(discard_reason=""))
                ),
                name="sales_order_discard_reason",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=["DRAFT", "DISCARDED"],
                        order_number__isnull=True,
                        completed_by__isnull=True,
                        completed_at__isnull=True,
                        rounding_adjustment=Decimal("0.00"),
                        rounding_reason="",
                        rounding_by__isnull=True,
                        final_total__isnull=True,
                        shortage_acknowledged=False,
                    )
                    | Q(
                        status__in=["COMPLETED", "PARTIALLY_RETURNED", "RETURNED", "VOIDED"],
                        order_number__isnull=False,
                        completed_by__isnull=False,
                        completed_at__isnull=False,
                        final_total__isnull=False,
                    )
                ),
                name="sales_order_completion_state",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        rounding_adjustment=Decimal("0.00"),
                        rounding_reason="",
                        rounding_by__isnull=True,
                    )
                    | (
                        ~Q(rounding_adjustment=Decimal("0.00"))
                        & ~Q(rounding_reason="")
                        & Q(rounding_by__isnull=False)
                    )
                ),
                name="sales_order_rounding_evidence",
            ),
            models.CheckConstraint(
                condition=Q(final_total__isnull=True) | Q(final_total__gte=0),
                name="sales_order_final_total_nonneg",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status__in=["DRAFT", "DISCARDED"])
                    | Q(
                        final_total=ExpressionWrapper(
                            F("subtotal") + F("rounding_adjustment"),
                            output_field=DecimalField(max_digits=38, decimal_places=2),
                        )
                    )
                ),
                name="sales_order_final_total_exact",
            ),
        ]
        indexes = [
            models.Index(
                fields=["terminal", "status", "slot"],
                name="sales_term_status_slot_idx",
            ),
            models.Index(
                fields=["shop", "status", "-updated_at"],
                name="sales_shop_status_upd_idx",
            ),
            models.Index(
                fields=["shop", "status", "-completed_at", "-id"],
                name="sales_shop_completed_idx",
            ),
            models.Index(
                fields=["current_cashier", "status"],
                name="sales_current_status_idx",
            ),
        ]

    def __str__(self):
        return self.order_number or f"{self.terminal.code} Order {self.slot} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=200)
    product_barcode = models.CharField(max_length=64, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveBigIntegerField()
    line_total = models.DecimalField(max_digits=38, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"],
                name="sales_item_order_product_uq",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="sales_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="sales_item_unit_price_nonneg",
            ),
            models.CheckConstraint(
                condition=Q(line_total__gte=0),
                name="sales_item_line_total_nonneg",
            ),
            models.CheckConstraint(
                condition=Q(
                    line_total=ExpressionWrapper(
                        F("unit_price") * F("quantity"),
                        output_field=DecimalField(max_digits=38, decimal_places=2),
                    )
                ),
                name="sales_item_line_total_exact",
            ),
            models.CheckConstraint(
                condition=~Q(product_name=""),
                name="sales_item_name_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(product_barcode__isnull=True) | ~Q(product_barcode=""),
                name="sales_item_barcode_not_empty",
            ),
        ]

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class ImmutablePaymentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(_("Payments cannot be changed."))

    def delete(self):
        raise ValidationError(_("Payments cannot be deleted."))


class ImmutableCorrectionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(_("Sale corrections cannot be changed."))

    def delete(self):
        raise ValidationError(_("Sale corrections cannot be deleted."))


class SalesReturn(models.Model):
    shop = models.ForeignKey("core.Shop", on_delete=models.PROTECT, related_name="sales_returns")
    return_number = models.CharField(max_length=32)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="returns")
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="processed_returns"
    )
    reason = models.CharField(max_length=500, blank=True, default="")
    total_refund = models.DecimalField(max_digits=38, decimal_places=2)
    request_token = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutableCorrectionQuerySet)()

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "return_number"], name="sales_return_shop_number_uq"
            ),
            models.UniqueConstraint(
                fields=["shop", "request_token"], name="sales_return_shop_token_uq"
            ),
            models.CheckConstraint(
                condition=Q(total_refund__gte=0), name="sales_return_total_nonneg"
            ),
        ]

    def __str__(self):
        return self.return_number

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(_("Sale corrections cannot be changed."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Sale corrections cannot be deleted."))


class SalesReturnItem(models.Model):
    class Disposition(models.TextChoices):
        RESTOCK = "RESTOCK", _("Restock")
        DAMAGED = "DAMAGED", _("Damaged / do not restock")

    sales_return = models.ForeignKey(SalesReturn, on_delete=models.PROTECT, related_name="items")
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="return_items")
    quantity = models.PositiveBigIntegerField()
    disposition = models.CharField(max_length=16, choices=Disposition.choices)
    unit_refund = models.DecimalField(max_digits=12, decimal_places=2)
    line_refund = models.DecimalField(max_digits=38, decimal_places=2)

    objects = models.Manager.from_queryset(ImmutableCorrectionQuerySet)()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sales_return", "order_item"], name="sales_return_item_line_uq"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="sales_return_item_qty_positive"
            ),
            models.CheckConstraint(
                condition=Q(unit_refund__gte=0), name="sales_return_item_unit_nonneg"
            ),
            models.CheckConstraint(
                condition=Q(line_refund__gte=0), name="sales_return_item_line_nonneg"
            ),
            models.CheckConstraint(
                condition=Q(
                    line_refund=ExpressionWrapper(
                        F("unit_refund") * F("quantity"),
                        output_field=DecimalField(max_digits=38, decimal_places=2),
                    )
                ),
                name="sales_return_item_total_exact",
            ),
        ]

    def __str__(self):
        return f"{self.sales_return.return_number}: {self.order_item} x {self.quantity}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(_("Sale corrections cannot be changed."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Sale corrections cannot be deleted."))


class OrderVoid(models.Model):
    shop = models.ForeignKey("core.Shop", on_delete=models.PROTECT, related_name="order_voids")
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="void")
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="processed_voids"
    )
    reason = models.CharField(max_length=500)
    request_token = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutableCorrectionQuerySet)()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "request_token"], name="sales_void_shop_token_uq"
            ),
            models.CheckConstraint(condition=~Q(reason=""), name="sales_void_reason_not_empty"),
        ]

    def __str__(self):
        return f"Void {self.order}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(_("Sale corrections cannot be changed."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Sale corrections cannot be deleted."))


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", _("Cash")

    class Direction(models.TextChoices):
        RECEIPT = "RECEIPT", _("Receipt")
        REFUND = "REFUND", _("Refund")

    shop = models.ForeignKey(
        "core.Shop",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="payment",
        null=True,
        blank=True,
    )
    sales_return = models.OneToOneField(
        SalesReturn, on_delete=models.PROTECT, related_name="refund_payment", null=True, blank=True
    )
    order_void = models.OneToOneField(
        OrderVoid, on_delete=models.PROTECT, related_name="refund_payment", null=True, blank=True
    )
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.CASH)
    direction = models.CharField(
        max_length=16, choices=Direction.choices, default=Direction.RECEIPT
    )
    amount = models.DecimalField(max_digits=38, decimal_places=2)
    cash_received = models.DecimalField(max_digits=38, decimal_places=2, null=True, blank=True)
    change_given = models.DecimalField(max_digits=38, decimal_places=2, null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_payments",
    )
    processed_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutablePaymentQuerySet)()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(method="CASH"), name="sales_payment_cash_only"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="sales_payment_amount_nonneg"),
            models.CheckConstraint(
                condition=(
                    Q(direction="REFUND")
                    | Q(
                        direction="RECEIPT",
                        change_given=ExpressionWrapper(
                            F("cash_received") - F("amount"),
                            output_field=DecimalField(max_digits=38, decimal_places=2),
                        ),
                    )
                ),
                name="sales_payment_change_exact",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        direction="RECEIPT",
                        order__isnull=False,
                        sales_return__isnull=True,
                        order_void__isnull=True,
                        cash_received__isnull=False,
                        change_given__isnull=False,
                    )
                    | Q(
                        direction="REFUND",
                        order__isnull=True,
                        sales_return__isnull=False,
                        order_void__isnull=True,
                        cash_received__isnull=True,
                        change_given__isnull=True,
                    )
                    | Q(
                        direction="REFUND",
                        order__isnull=True,
                        sales_return__isnull=True,
                        order_void__isnull=False,
                        cash_received__isnull=True,
                        change_given__isnull=True,
                    )
                ),
                name="sales_payment_source_state",
            ),
        ]

    def __str__(self):
        source = self.order or self.sales_return or self.order_void
        return f"Cash {self.direction.lower()} for {source}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(_("Payments cannot be changed."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Payments cannot be deleted."))
