from decimal import Decimal
from itertools import product

from django.apps import apps
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import CASCADE, PROTECT
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import Shop, Terminal
from apps.sales.models import Order, OrderItem, Payment


class ReviewedSchemaContractTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Schema review shop")
        self.terminal = Terminal.objects.create(
            shop=self.shop,
            code="TILL-1",
            name="Till 1",
        )
        self.cashier = User.objects.create_user(
            username="schema-review-cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )

    def test_exact_m4_model_surface_and_field_metadata(self):
        self.assertEqual(
            {model.__name__ for model in apps.get_app_config("sales").get_models()},
            {"Order", "OrderItem", "Payment", "SalesReturn", "SalesReturnItem", "OrderVoid"},
        )
        self.assertEqual(
            {field.name for field in Order._meta.get_fields()},
            {
                "id",
                "items",
                "payment",
                "returns",
                "void",
                "shop",
                "terminal",
                "slot",
                "status",
                "created_by",
                "current_cashier",
                "subtotal",
                "version",
                "order_number",
                "completed_by",
                "completed_at",
                "rounding_adjustment",
                "rounding_reason",
                "rounding_by",
                "final_total",
                "shortage_acknowledged",
                "discarded_by",
                "discard_reason",
                "discard_was_empty",
                "discarded_at",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(
            {field.name for field in OrderItem._meta.get_fields()},
            {
                "id",
                "sale_movements",
                "return_items",
                "void_movement",
                "order",
                "product",
                "product_name",
                "product_barcode",
                "unit_price",
                "quantity",
                "line_total",
                "created_at",
                "updated_at",
            },
        )

        order_field_types = {
            "slot": models.PositiveSmallIntegerField,
            "status": models.CharField,
            "subtotal": models.DecimalField,
            "version": models.PositiveBigIntegerField,
            "discard_reason": models.CharField,
            "discard_was_empty": models.BooleanField,
            "discarded_at": models.DateTimeField,
            "created_at": models.DateTimeField,
            "updated_at": models.DateTimeField,
        }
        for field_name, expected_type in order_field_types.items():
            with self.subTest(model="Order", field=field_name):
                self.assertIsInstance(Order._meta.get_field(field_name), expected_type)

        item_field_types = {
            "product_name": models.CharField,
            "product_barcode": models.CharField,
            "unit_price": models.DecimalField,
            "quantity": models.PositiveBigIntegerField,
            "line_total": models.DecimalField,
            "created_at": models.DateTimeField,
            "updated_at": models.DateTimeField,
        }
        for field_name, expected_type in item_field_types.items():
            with self.subTest(model="OrderItem", field=field_name):
                self.assertIsInstance(OrderItem._meta.get_field(field_name), expected_type)

        self.assertEqual(Order._meta.get_field("status").max_length, 24)
        self.assertEqual(Order._meta.get_field("status").get_default(), Order.Status.DRAFT)
        self.assertEqual(
            [value for value, _label in Order._meta.get_field("status").choices],
            [
                Order.Status.DRAFT,
                Order.Status.DISCARDED,
                Order.Status.COMPLETED,
                Order.Status.PARTIALLY_RETURNED,
                Order.Status.RETURNED,
                Order.Status.VOIDED,
            ],
        )
        self.assertEqual(Order._meta.get_field("subtotal").max_digits, 38)
        self.assertEqual(Order._meta.get_field("subtotal").decimal_places, 2)
        self.assertEqual(Order._meta.get_field("subtotal").get_default(), Decimal("0.00"))
        self.assertEqual(Order._meta.get_field("version").get_default(), 1)
        self.assertEqual(Order._meta.get_field("discard_reason").max_length, 500)
        self.assertEqual(Order._meta.get_field("discard_reason").get_default(), "")
        self.assertTrue(Order._meta.get_field("discarded_at").blank)
        self.assertTrue(Order._meta.get_field("discarded_at").null)

        self.assertEqual(OrderItem._meta.get_field("product_name").max_length, 200)
        self.assertEqual(OrderItem._meta.get_field("product_barcode").max_length, 64)
        self.assertTrue(OrderItem._meta.get_field("product_barcode").blank)
        self.assertTrue(OrderItem._meta.get_field("product_barcode").null)
        self.assertEqual(OrderItem._meta.get_field("unit_price").max_digits, 12)
        self.assertEqual(OrderItem._meta.get_field("unit_price").decimal_places, 2)
        self.assertEqual(OrderItem._meta.get_field("line_total").max_digits, 38)
        self.assertEqual(OrderItem._meta.get_field("line_total").decimal_places, 2)

        order_relationships = {
            "shop": (PROTECT, "orders"),
            "terminal": (PROTECT, "orders"),
            "created_by": (PROTECT, "created_orders"),
            "current_cashier": (PROTECT, "current_orders"),
            "discarded_by": (PROTECT, "discarded_orders"),
            "completed_by": (PROTECT, "completed_orders"),
            "rounding_by": (PROTECT, "rounded_orders"),
        }
        for field_name, (on_delete, related_name) in order_relationships.items():
            with self.subTest(model="Order", field=field_name):
                field = Order._meta.get_field(field_name)
                self.assertIs(field.remote_field.on_delete, on_delete)
                self.assertEqual(field.remote_field.related_name, related_name)

        self.assertIs(OrderItem._meta.get_field("order").remote_field.on_delete, CASCADE)
        self.assertEqual(OrderItem._meta.get_field("order").remote_field.related_name, "items")
        self.assertIs(OrderItem._meta.get_field("product").remote_field.on_delete, PROTECT)
        self.assertEqual(
            OrderItem._meta.get_field("product").remote_field.related_name,
            "order_items",
        )

        self.assertEqual(
            {constraint.name for constraint in Order._meta.constraints},
            {
                "sales_order_status_valid",
                "sales_order_slot_1_3",
                "sales_active_terminal_slot_uq",
                "sales_order_subtotal_nonneg",
                "sales_order_version_positive",
                "sales_order_discard_state",
                "sales_order_discard_reason",
                "sales_order_shop_number_uq",
                "sales_order_completion_state",
                "sales_order_rounding_evidence",
                "sales_order_final_total_nonneg",
                "sales_order_final_total_exact",
            },
        )
        self.assertEqual(
            {constraint.name for constraint in OrderItem._meta.constraints},
            {
                "sales_item_order_product_uq",
                "sales_item_quantity_positive",
                "sales_item_unit_price_nonneg",
                "sales_item_line_total_nonneg",
                "sales_item_line_total_exact",
                "sales_item_name_not_empty",
                "sales_item_barcode_not_empty",
            },
        )
        self.assertEqual(Payment._meta.get_field("method").get_default(), Payment.Method.CASH)
        self.assertEqual(Payment._meta.get_field("order").remote_field.on_delete, PROTECT)
        self.assertEqual(
            {constraint.name for constraint in Payment._meta.constraints},
            {
                "sales_payment_cash_only",
                "sales_payment_amount_nonneg",
                "sales_payment_change_exact",
                "sales_payment_source_state",
            },
        )

    def test_database_enforces_complete_discard_truth_table(self):
        statuses = (Order.Status.DRAFT, Order.Status.DISCARDED)
        metadata_presence = (False, True)
        empty_flags = (False, True)
        reasons = ("", "Customer cancelled")
        subtotals = (Decimal("0.00"), Decimal("1.00"))

        for status, has_actor, has_time, was_empty, reason, subtotal in product(
            statuses,
            metadata_presence,
            metadata_presence,
            empty_flags,
            reasons,
            subtotals,
        ):
            expected_valid = (
                status == Order.Status.DRAFT
                and not has_actor
                and not has_time
                and not was_empty
                and reason == ""
            ) or (
                status == Order.Status.DISCARDED
                and has_actor
                and has_time
                and (
                    (was_empty and reason == "" and subtotal == Decimal("0.00"))
                    or (not was_empty and reason != "")
                )
            )
            values = {
                "shop": self.shop,
                "terminal": self.terminal,
                "slot": 1,
                "status": status,
                "created_by": self.cashier,
                "current_cashier": self.cashier,
                "subtotal": subtotal,
                "discarded_by": self.cashier if has_actor else None,
                "discarded_at": timezone.now() if has_time else None,
                "discard_was_empty": was_empty,
                "discard_reason": reason,
            }

            accepted = True
            try:
                with transaction.atomic():
                    order = Order.objects.create(**values)
            except IntegrityError:
                accepted = False
                order = None

            with self.subTest(
                status=status,
                has_actor=has_actor,
                has_time=has_time,
                was_empty=was_empty,
                reason=reason,
                subtotal=subtotal,
            ):
                self.assertEqual(accepted, expected_valid)

            if order is not None:
                order.delete()
