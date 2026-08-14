from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, DocumentSequence, Shop, Terminal
from apps.inventory.models import InventoryMovement
from apps.sales.checkout import complete_cash_checkout
from apps.sales.models import Order, OrderItem, Payment


class CashCheckoutServiceTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Checkout shop")
        DocumentSequence.objects.create(shop=self.shop, document_type="ORDER")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Main checkout")
        self.cashier = User.objects.create_user(
            username="checkout-cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            barcode="10001",
            name="Milk",
            selling_price=Decimal("25.00"),
            stock_on_hand=10,
            created_by=self.cashier,
        )
        self.draft = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=1,
            created_by=self.cashier,
            current_cashier=self.cashier,
            subtotal=Decimal("50.00"),
        )
        self.item = OrderItem.objects.create(
            order=self.draft,
            product=self.product,
            product_name="Milk",
            product_barcode="10001",
            unit_price=Decimal("25.00"),
            quantity=2,
            line_total=Decimal("50.00"),
        )

    def checkout(self, **overrides):
        values = {
            "actor": self.cashier,
            "draft_id": self.draft.pk,
            "expected_version": self.draft.version,
            "cash_received": Decimal("60.00"),
        }
        values.update(overrides)
        return complete_cash_checkout(**values)

    def test_checkout_reconciles_and_creates_fresh_same_slot_draft(self):
        result = self.checkout()

        result.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(result.order.status, Order.Status.COMPLETED)
        self.assertEqual(result.order.order_number, "ORD-000001")
        self.assertEqual(result.order.final_total, Decimal("50.00"))
        self.assertEqual(result.payment.amount, Decimal("50.00"))
        self.assertEqual(result.payment.cash_received, Decimal("60.00"))
        self.assertEqual(result.payment.change_given, Decimal("10.00"))
        self.assertEqual(self.product.stock_on_hand, 8)
        self.assertEqual(InventoryMovement.objects.get(order_item=self.item).quantity_change, -2)
        self.assertEqual(result.replacement.slot, 1)
        self.assertFalse(result.replacement.items.exists())

    def test_cash_below_total_completes_with_negative_change(self):
        result = self.checkout(cash_received=Decimal("49.00"))

        self.assertEqual(result.payment.amount, Decimal("50.00"))
        self.assertEqual(result.payment.cash_received, Decimal("49.00"))
        self.assertEqual(result.payment.change_given, Decimal("-1.00"))
        self.assertEqual(result.order.rounding_adjustment, Decimal("0.00"))
        self.assertEqual(result.order.rounding_reason, "")

    def test_shortage_completes_and_records_audit_in_one_action(self):
        self.product.stock_on_hand = 1
        self.product.save(update_fields=["stock_on_hand"])

        result = self.checkout()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, -1)
        self.assertTrue(result.order.shortage_acknowledged)
        event = AuditEvent.objects.get(action=AuditEvent.Action.STOCK_SHORTAGE_ACKNOWLEDGED)
        self.assertEqual(event.after_values["shortages"][0]["balance_after"], -1)

    def test_failure_after_writes_rolls_back_every_completion_effect(self):
        self.product.stock_on_hand = 1
        self.product.save(update_fields=["stock_on_hand"])
        with patch("apps.sales.checkout.record", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.checkout()

        self.draft.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.draft.status, Order.Status.DRAFT)
        self.assertEqual(self.product.stock_on_hand, 1)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(InventoryMovement.objects.filter(movement_type="SALE").exists())
        self.assertEqual(DocumentSequence.objects.get(shop=self.shop).next_number, 1)

    def test_repeated_completion_is_idempotent(self):
        first = self.checkout()
        second = self.checkout(cash_received=Decimal("999.00"))

        self.assertTrue(second.already_completed)
        self.assertEqual(second.order.pk, first.order.pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="SALE").count(), 1)

    def test_invalid_cash_and_inactive_product_leave_draft_unchanged(self):
        with self.assertRaises(ValidationError):
            self.checkout(cash_received=Decimal("-0.01"))
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            self.checkout()
        self.assertEqual(Order.objects.get(pk=self.draft.pk).status, Order.Status.DRAFT)
        self.assertFalse(Payment.objects.exists())
