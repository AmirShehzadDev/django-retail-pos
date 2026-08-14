from django.db import models
from django.db.models.functions import Upper
from django.utils.translation import gettext_lazy as _


class Shop(models.Model):
    class Currency(models.TextChoices):
        PKR = "PKR", _("Pakistani Rupee")

    class Timezone(models.TextChoices):
        ASIA_KARACHI = "Asia/Karachi", _("Asia/Karachi")

    name = models.CharField(max_length=150)
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.PKR,
    )
    timezone = models.CharField(
        max_length=64,
        choices=Timezone.choices,
        default=Timezone.ASIA_KARACHI,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(currency="PKR"),
                name="core_shop_currency_pkr",
            ),
            models.CheckConstraint(
                condition=models.Q(timezone="Asia/Karachi"),
                name="core_shop_timezone_karachi",
            ),
        ]
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Terminal(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="terminals")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "code"],
                name="core_terminal_shop_code_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(code=Upper("code")),
                name="core_terminal_code_uppercase",
            ),
        ]
        ordering = ["shop_id", "code", "id"]

    def __str__(self):
        return f"{self.shop}: {self.code}"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class DocumentSequence(models.Model):
    class DocumentType(models.TextChoices):
        ORDER = "ORDER", _("Order")
        RETURN = "RETURN", _("Return")

    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="document_sequences")
    document_type = models.CharField(max_length=16, choices=DocumentType.choices)
    next_number = models.PositiveBigIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "document_type"],
                name="core_sequence_shop_type_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(next_number__gte=1),
                name="core_sequence_next_positive",
            ),
        ]

    def __str__(self):
        return f"{self.shop}: {self.document_type} {self.next_number}"


class AuditEvent(models.Model):
    class Action(models.TextChoices):
        USER_CREATED = "USER_CREATED", _("User created")
        USER_PROFILE_UPDATED = "USER_PROFILE_UPDATED", _("User profile updated")
        USER_ROLE_CHANGED = "USER_ROLE_CHANGED", _("User role changed")
        USER_ACTIVATED = "USER_ACTIVATED", _("User activated")
        USER_DEACTIVATED = "USER_DEACTIVATED", _("User deactivated")
        USER_PASSWORD_RESET = "USER_PASSWORD_RESET", _("User password reset")
        USER_PASSWORD_CHANGED = "USER_PASSWORD_CHANGED", _("User password changed")
        SHOP_NAME_CHANGED = "SHOP_NAME_CHANGED", _("Shop name changed")
        PRODUCT_PRICE_CHANGED = "PRODUCT_PRICE_CHANGED", _("Product price changed")
        INVENTORY_ADJUSTED = "INVENTORY_ADJUSTED", _("Inventory adjusted")
        PRODUCT_QUICK_CREATED = "PRODUCT_QUICK_CREATED", _("Product quick created")
        DRAFT_TAKEN_OVER = "DRAFT_TAKEN_OVER", _("Draft taken over")
        DRAFT_DISCARDED = "DRAFT_DISCARDED", _("Draft discarded")
        ORDER_ROUNDING_APPLIED = "ORDER_ROUNDING_APPLIED", _("Order rounding applied")
        STOCK_SHORTAGE_ACKNOWLEDGED = (
            "STOCK_SHORTAGE_ACKNOWLEDGED",
            _("Stock shortage acknowledged"),
        )
        ORDER_RETURNED = "ORDER_RETURNED", _("Order returned")
        ORDER_VOIDED = "ORDER_VOIDED", _("Order voided")

    class TargetType(models.TextChoices):
        USER = "USER", _("User")
        SHOP = "SHOP", _("Shop")
        PRODUCT = "PRODUCT", _("Product")
        ORDER = "ORDER", _("Order")

    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="audit_events")
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    action = models.CharField(max_length=64, choices=Action.choices)
    target_type = models.CharField(max_length=64, choices=TargetType.choices)
    target_identifier = models.CharField(max_length=64)
    before_values = models.JSONField(default=dict)
    after_values = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["shop", "-created_at"], name="core_audit_shop_created_idx"),
            models.Index(
                fields=["shop", "action", "-created_at"],
                name="core_audit_shop_action_idx",
            ),
            models.Index(
                fields=["target_type", "target_identifier"],
                name="core_audit_target_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action}: {self.target_type} {self.target_identifier}"
