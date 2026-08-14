import decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0002_user_management_constraints"),
        ("catalog", "0001_initial"),
        ("core", "0004_m3_audit_vocabulary"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slot", models.PositiveSmallIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Draft"), ("DISCARDED", "Discarded")],
                        default="DRAFT",
                        max_length=24,
                    ),
                ),
                (
                    "subtotal",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0.00"),
                        max_digits=38,
                    ),
                ),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("discard_reason", models.CharField(blank=True, default="", max_length=500)),
                ("discard_was_empty", models.BooleanField(default=False)),
                ("discarded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "current_cashier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="current_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "discarded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="discarded_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "shop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders",
                        to="core.shop",
                    ),
                ),
                (
                    "terminal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders",
                        to="core.terminal",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["terminal", "status", "slot"],
                        name="sales_term_status_slot_idx",
                    ),
                    models.Index(
                        fields=["shop", "status", "-updated_at"],
                        name="sales_shop_status_upd_idx",
                    ),
                    models.Index(
                        fields=["current_cashier", "status"],
                        name="sales_current_status_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ["DRAFT", "DISCARDED"])),
                        name="sales_order_status_valid",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("slot__gte", 1), ("slot__lte", 3)),
                        name="sales_order_slot_1_3",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("status", "DRAFT")),
                        fields=("terminal", "slot"),
                        name="sales_active_terminal_slot_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("subtotal__gte", 0)),
                        name="sales_order_subtotal_nonneg",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("version__gte", 1)),
                        name="sales_order_version_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("discard_reason", ""),
                                ("discard_was_empty", False),
                                ("discarded_at__isnull", True),
                                ("discarded_by__isnull", True),
                                ("status", "DRAFT"),
                            ),
                            models.Q(
                                ("discarded_at__isnull", False),
                                ("discarded_by__isnull", False),
                                ("status", "DISCARDED"),
                            ),
                            _connector="OR",
                        ),
                        name="sales_order_discard_state",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("status", "DRAFT"),
                            models.Q(
                                ("discard_reason", ""),
                                ("discard_was_empty", True),
                                ("status", "DISCARDED"),
                                ("subtotal", decimal.Decimal("0.00")),
                            ),
                            models.Q(
                                ("discard_was_empty", False),
                                ("status", "DISCARDED"),
                                models.Q(("discard_reason", ""), _negated=True),
                            ),
                            _connector="OR",
                        ),
                        name="sales_order_discard_reason",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("product_name", models.CharField(max_length=200)),
                ("product_barcode", models.CharField(blank=True, max_length=64, null=True)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("quantity", models.PositiveBigIntegerField()),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=38)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="sales.order",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="order_items",
                        to="catalog.product",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("order", "product"),
                        name="sales_item_order_product_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("quantity__gt", 0)),
                        name="sales_item_quantity_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("unit_price__gte", 0)),
                        name="sales_item_unit_price_nonneg",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("line_total__gte", 0)),
                        name="sales_item_line_total_nonneg",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "line_total",
                                models.ExpressionWrapper(
                                    models.F("unit_price") * models.F("quantity"),
                                    output_field=models.DecimalField(
                                        decimal_places=2,
                                        max_digits=38,
                                    ),
                                ),
                            )
                        ),
                        name="sales_item_line_total_exact",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("product_name", ""), _negated=True),
                        name="sales_item_name_not_empty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("product_barcode__isnull", True),
                            models.Q(("product_barcode", ""), _negated=True),
                            _connector="OR",
                        ),
                        name="sales_item_barcode_not_empty",
                    ),
                ],
            },
        ),
    ]
