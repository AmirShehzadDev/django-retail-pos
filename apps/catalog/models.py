from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _


class Product(models.Model):
    class CreationSource(models.TextChoices):
        CATALOG = "CATALOG", _("Catalog")
        POS_QUICK_CREATE = "POS_QUICK_CREATE", _("POS quick create")

    shop = models.ForeignKey(
        "core.Shop",
        on_delete=models.PROTECT,
        related_name="products",
    )
    barcode = models.CharField(max_length=64, null=True, blank=True)
    sku = models.CharField(max_length=64, null=True, blank=True)
    name = models.CharField(max_length=200)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_on_hand = models.BigIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_products",
    )
    creation_source = models.CharField(
        max_length=24,
        choices=CreationSource.choices,
        default=CreationSource.CATALOG,
    )
    needs_review = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "barcode"],
                condition=models.Q(barcode__isnull=False),
                name="catalog_barcode_unique",
            ),
            models.UniqueConstraint(
                "shop",
                Lower("sku"),
                condition=models.Q(sku__isnull=False),
                name="catalog_sku_ci_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(selling_price__gte=0),
                name="catalog_selling_price_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(cost_price__isnull=True) | models.Q(cost_price__gte=0),
                name="catalog_cost_price_gte_0",
            ),
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="catalog_name_not_empty",
            ),
        ]
        indexes = [
            models.Index(fields=["shop", "barcode"], name="catalog_shop_barcode_idx"),
            models.Index(
                fields=["shop", "is_active", "name"],
                name="catalog_shop_active_name_idx",
            ),
            models.Index(
                fields=["shop", "needs_review"],
                name="catalog_shop_review_idx",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self._normalize_text_fields()
        if not self.name:
            raise ValidationError({"name": _("Product name is required.")})

    def _normalize_text_fields(self):
        self.name = self.name.strip() if self.name else ""
        self.barcode = self.barcode.strip() or None if self.barcode else None
        self.sku = self.sku.strip() or None if self.sku else None
