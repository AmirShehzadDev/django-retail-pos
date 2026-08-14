from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, Shop
from apps.inventory.models import InventoryMovement
from apps.inventory.services import adjust_stock, receive_stock


class InventoryServiceTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Main Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.ADMIN,
            created_by=self.owner,
        )
        self.cashier = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
            created_by=self.owner,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            barcode="0012345",
            sku="TEA-1",
            name="Tea",
            selling_price=Decimal("250.00"),
            cost_price=Decimal("200.00"),
            created_by=self.admin,
        )

    def test_receipt_updates_cached_stock_and_appends_one_movement(self):
        product, movement = receive_stock(
            actor=self.admin,
            product_id=self.product.pk,
            quantity=10,
            note="",
        )

        self.assertEqual(product.stock_on_hand, 10)
        self.assertEqual(movement.movement_type, InventoryMovement.MovementType.RECEIPT)
        self.assertEqual(movement.quantity_change, 10)
        self.assertEqual(movement.balance_after, 10)
        self.assertEqual(movement.reason, "Manual stock receipt")
        self.assertEqual(movement.actor, self.admin)
        self.assertEqual(InventoryMovement.objects.count(), 1)
        self.assertFalse(AuditEvent.objects.exists())

    def test_adjustment_can_create_negative_stock_and_records_audit(self):
        receive_stock(actor=self.owner, product_id=self.product.pk, quantity=10)

        product, movement = adjust_stock(
            actor=self.admin,
            product_id=self.product.pk,
            quantity_change=-12,
            reason="Damaged during delivery",
        )

        self.assertEqual(product.stock_on_hand, -2)
        self.assertEqual(movement.balance_after, -2)
        event = AuditEvent.objects.get(action=AuditEvent.Action.INVENTORY_ADJUSTED)
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.target_identifier, str(self.product.pk))
        self.assertEqual(event.after_values["movement_id"], movement.pk)
        self.assertEqual(event.after_values["quantity_change"], -12)
        self.assertEqual(event.after_values["balance_before"], 10)
        self.assertEqual(event.after_values["balance_after"], -2)

    def test_invalid_operations_leave_product_and_ledger_unchanged(self):
        invalid_calls = (
            lambda: receive_stock(actor=self.admin, product_id=self.product.pk, quantity=0),
            lambda: receive_stock(actor=self.admin, product_id=self.product.pk, quantity=-1),
            lambda: adjust_stock(
                actor=self.admin,
                product_id=self.product.pk,
                quantity_change=0,
                reason="Count",
            ),
            lambda: adjust_stock(
                actor=self.admin,
                product_id=self.product.pk,
                quantity_change=1,
                reason="   ",
            ),
        )

        for invalid_call in invalid_calls:
            with self.subTest(call=invalid_call):
                with self.assertRaises(ValidationError):
                    invalid_call()
                self.product.refresh_from_db()
                self.assertEqual(self.product.stock_on_hand, 0)
                self.assertFalse(InventoryMovement.objects.exists())
                self.assertFalse(AuditEvent.objects.exists())

    def test_inactive_product_rejects_stock_change(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            receive_stock(actor=self.admin, product_id=self.product.pk, quantity=2)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 0)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_cashier_and_foreign_shop_actor_are_denied(self):
        foreign_shop = Shop.objects.create(name="Other Shop")
        foreign_owner = User.objects.create_user(
            username="foreign-owner",
            password="StrongPass!2026",
            shop=foreign_shop,
            role=User.Role.OWNER,
        )

        for actor in (self.cashier, foreign_owner):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    receive_stock(actor=actor, product_id=self.product.pk, quantity=2)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 0)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_adjustment_rolls_back_when_audit_fails(self):
        with patch("apps.inventory.services.record", side_effect=ValidationError("Audit failed")):
            with self.assertRaises(ValidationError):
                adjust_stock(
                    actor=self.admin,
                    product_id=self.product.pk,
                    quantity_change=3,
                    reason="Count correction",
                )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 0)
        self.assertFalse(InventoryMovement.objects.exists())


class InventoryConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.shop = Shop.objects.create(name="Main Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Tea",
            selling_price=Decimal("250.00"),
            created_by=self.owner,
        )

    def test_concurrent_receipts_do_not_lose_stock(self):
        barrier = Barrier(2)

        def receive(quantity):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.owner.pk)
                barrier.wait(timeout=5)
                return receive_stock(
                    actor=actor,
                    product_id=self.product.pk,
                    quantity=quantity,
                )[1].balance_after
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            balances = list(executor.map(receive, (5, 7)))

        self.product.refresh_from_db()
        movements = list(InventoryMovement.objects.order_by("id"))
        self.assertEqual(self.product.stock_on_hand, 12)
        self.assertEqual(len(movements), 2)
        self.assertEqual(max(balances), 12)
        running_balance = 0
        for movement in movements:
            running_balance += movement.quantity_change
            self.assertEqual(movement.balance_after, running_balance)
