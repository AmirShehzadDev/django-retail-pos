from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import CASCADE, PROTECT, ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import Shop, Terminal
from apps.sales.models import Order, OrderItem


class OrderModelTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till 1")
        self.cashier = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )

    def order(self, **overrides):
        values = {
            "shop": self.shop,
            "terminal": self.terminal,
            "slot": 1,
            "created_by": self.cashier,
            "current_cashier": self.cashier,
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def assert_order_rejected(self, **overrides):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.order(**overrides)

    def test_exact_fields_defaults_and_distinct_user_reverse_accessors(self):
        order = self.order()

        self.assertEqual(order.status, Order.Status.DRAFT)
        self.assertEqual(order.subtotal, Decimal("0.00"))
        self.assertEqual(order.version, 1)
        self.assertEqual(order.discard_reason, "")
        self.assertFalse(order.discard_was_empty)
        self.assertIsNone(order.discarded_by)
        self.assertIsNone(order.discarded_at)
        self.assertEqual(self.cashier.created_orders.get(), order)
        self.assertEqual(self.cashier.current_orders.get(), order)
        self.assertFalse(self.cashier.discarded_orders.exists())

        expected = {
            "created_by": "created_orders",
            "current_cashier": "current_orders",
            "discarded_by": "discarded_orders",
        }
        for field_name, related_name in expected.items():
            with self.subTest(field=field_name):
                field = Order._meta.get_field(field_name)
                self.assertEqual(field.remote_field.related_name, related_name)
                self.assertIs(field.remote_field.on_delete, PROTECT)

    def test_only_slots_one_through_three_are_valid(self):
        for slot in (0, 4):
            with self.subTest(slot=slot):
                self.assert_order_rejected(slot=slot)

        for slot in (1, 2, 3):
            self.order(slot=slot)

        self.assertEqual(Order.objects.count(), 3)

    def test_active_slot_uniqueness_makes_a_fourth_draft_impossible(self):
        for slot in (1, 2, 3):
            self.order(slot=slot)

        for slot in (1, 2, 3):
            with self.subTest(slot=slot):
                self.assert_order_rejected(slot=slot)

    def test_discarded_slots_can_repeat_and_do_not_block_active_reuse(self):
        discarded_at = timezone.now()
        for _ in range(3):
            self.order(
                status=Order.Status.DISCARDED,
                discarded_by=self.cashier,
                discarded_at=discarded_at,
                discard_was_empty=True,
            )

        active = self.order()

        self.assertEqual(active.slot, 1)
        self.assertEqual(Order.objects.filter(slot=1).count(), 4)

    def test_database_rejects_invalid_status_subtotal_and_version(self):
        invalid_rows = (
            {"status": "COMPLETED"},
            {"subtotal": Decimal("-0.01")},
            {"version": 0},
        )
        for overrides in invalid_rows:
            with self.subTest(overrides=overrides):
                self.assert_order_rejected(**overrides)

    def test_all_three_discard_truth_table_branches_are_valid(self):
        discarded_at = timezone.now()
        draft = self.order(slot=1, subtotal=Decimal("9.99"))
        empty = self.order(
            slot=2,
            status=Order.Status.DISCARDED,
            discarded_by=self.cashier,
            discarded_at=discarded_at,
            discard_was_empty=True,
            subtotal=Decimal("0.00"),
        )
        non_empty_zero_price = self.order(
            slot=3,
            status=Order.Status.DISCARDED,
            discarded_by=self.cashier,
            discarded_at=discarded_at,
            discard_was_empty=False,
            discard_reason="Customer changed their mind",
            subtotal=Decimal("0.00"),
        )

        self.assertEqual(
            {draft.status, empty.status, non_empty_zero_price.status},
            {Order.Status.DRAFT, Order.Status.DISCARDED},
        )

    def test_database_rejects_every_partial_or_contradictory_discard_state(self):
        discarded_at = timezone.now()
        invalid_rows = (
            {"discarded_by": self.cashier},
            {"discarded_at": discarded_at},
            {"discard_was_empty": True},
            {"discard_reason": "Not permitted on a draft"},
            {"status": Order.Status.DISCARDED},
            {"status": Order.Status.DISCARDED, "discarded_by": self.cashier},
            {"status": Order.Status.DISCARDED, "discarded_at": discarded_at},
            {
                "status": Order.Status.DISCARDED,
                "discarded_by": self.cashier,
                "discarded_at": discarded_at,
                "discard_was_empty": True,
                "discard_reason": "Empty closes cannot have a reason",
            },
            {
                "status": Order.Status.DISCARDED,
                "discarded_by": self.cashier,
                "discarded_at": discarded_at,
                "discard_was_empty": True,
                "subtotal": Decimal("0.01"),
            },
            {
                "status": Order.Status.DISCARDED,
                "discarded_by": self.cashier,
                "discarded_at": discarded_at,
                "discard_was_empty": False,
                "discard_reason": "",
            },
        )
        for overrides in invalid_rows:
            with self.subTest(overrides=overrides):
                self.assert_order_rejected(**overrides)

    def test_order_foreign_keys_are_protected(self):
        order = self.order()

        for field_name in ("shop", "terminal", "created_by", "current_cashier", "discarded_by"):
            with self.subTest(field=field_name):
                self.assertIs(Order._meta.get_field(field_name).remote_field.on_delete, PROTECT)

        with self.assertRaises(ProtectedError):
            self.cashier.delete()
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_order_schema_has_milestone_four_checkout_fields_and_payment(self):
        fields = {field.name for field in Order._meta.get_fields()}
        checkout_fields = {
            "order_number",
            "completed_by",
            "completed_at",
            "rounding_adjustment",
            "final_total",
            "shortage_acknowledged",
        }

        self.assertTrue(checkout_fields.issubset(fields))
        model_names = {model.__name__ for model in Order._meta.apps.get_models()}
        self.assertIn("Payment", model_names)
        self.assertTrue(model_names.isdisjoint({"Return", "Void"}))


class OrderItemModelTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till 1")
        self.cashier = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            created_by=self.cashier,
            name="Tea",
            barcode="0012345",
            selling_price=Decimal("250.00"),
        )
        self.order = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=1,
            created_by=self.cashier,
            current_cashier=self.cashier,
        )

    def item(self, **overrides):
        values = {
            "order": self.order,
            "product": self.product,
            "product_name": "Tea",
            "product_barcode": "0012345",
            "unit_price": Decimal("250.00"),
            "quantity": 2,
            "line_total": Decimal("500.00"),
        }
        values.update(overrides)
        return OrderItem.objects.create(**values)

    def assert_item_rejected(self, **overrides):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.item(**overrides)

    def test_exact_snapshot_fields_and_delete_behaviors(self):
        item = self.item()

        self.assertEqual(item.product_name, "Tea")
        self.assertEqual(item.product_barcode, "0012345")
        self.assertEqual(item.unit_price, Decimal("250.00"))
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.line_total, Decimal("500.00"))
        self.assertIs(OrderItem._meta.get_field("order").remote_field.on_delete, CASCADE)
        self.assertIs(OrderItem._meta.get_field("product").remote_field.on_delete, PROTECT)

    def test_one_product_has_at_most_one_line_per_order(self):
        self.item()

        self.assert_item_rejected()

    def test_database_rejects_invalid_quantity_price_total_and_snapshots(self):
        invalid_rows = (
            {"quantity": 0, "line_total": Decimal("0.00")},
            {"unit_price": Decimal("-0.01"), "line_total": Decimal("-0.02")},
            {"line_total": Decimal("-0.01")},
            {"line_total": Decimal("499.99")},
            {"product_name": ""},
            {"product_barcode": ""},
        )
        for overrides in invalid_rows:
            with self.subTest(overrides=overrides):
                self.assert_item_rejected(**overrides)

    def test_nullable_barcode_zero_price_and_large_exact_total_are_valid(self):
        self.item(product_barcode=None)

        second = Product.objects.create(
            shop=self.shop,
            created_by=self.cashier,
            name="Free sample",
            selling_price=Decimal("0.00"),
        )
        free_item = self.item(
            product=second,
            product_name="Free sample",
            product_barcode=None,
            unit_price=Decimal("0.00"),
            quantity=9_223_372_036_854_775_807,
            line_total=Decimal("0.00"),
        )

        maximum_price_product = Product.objects.create(
            shop=self.shop,
            created_by=self.cashier,
            name="Maximum price product",
            selling_price=Decimal("9999999999.99"),
        )
        maximum_item = self.item(
            product=maximum_price_product,
            product_name="Maximum price product",
            product_barcode=None,
            unit_price=Decimal("9999999999.99"),
            quantity=9_223_372_036_854_775_807,
            line_total=Decimal("92233720368455524349631452241.93"),
        )

        self.assertEqual(free_item.quantity, 9_223_372_036_854_775_807)
        self.assertEqual(
            maximum_item.line_total,
            Decimal("92233720368455524349631452241.93"),
        )

    def test_product_reference_is_protected_and_order_cascades_items(self):
        item = self.item()

        with self.assertRaises(ProtectedError):
            self.product.delete()

        self.order.delete()
        self.assertFalse(OrderItem.objects.filter(pk=item.pk).exists())

    def test_postgresql_exact_total_constraint_uses_multiplication_expression(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname = 'sales_item_line_total_exact'
                """
            )
            definition = cursor.fetchone()[0]

        self.assertIn("line_total", definition)
        self.assertIn("unit_price", definition)
        self.assertIn("quantity", definition)
        self.assertIn("*", definition)

    def test_auto_timestamps_are_present(self):
        before = timezone.now() - timedelta(seconds=1)
        item = self.item()

        self.assertGreater(item.created_at, before)
        self.assertGreater(item.updated_at, before)
