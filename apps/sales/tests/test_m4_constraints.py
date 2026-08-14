from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import DocumentSequence, Shop, Terminal
from apps.inventory.models import InventoryMovement
from apps.sales.checkout import complete_cash_checkout
from apps.sales.models import Order, OrderItem, Payment


class CheckoutLedgerConstraintTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Constraint shop")
        DocumentSequence.objects.create(shop=self.shop, document_type="ORDER")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")
        self.cashier = User.objects.create_user(
            username="constraint-cashier",
            password=None,
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Bread",
            selling_price=Decimal("20.00"),
            stock_on_hand=5,
            created_by=self.cashier,
        )

    def draft(self):
        order = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=1,
            created_by=self.cashier,
            current_cashier=self.cashier,
            subtotal=Decimal("20.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name="Bread",
            unit_price=Decimal("20.00"),
            quantity=1,
            line_total=Decimal("20.00"),
        )
        return order

    def test_completed_order_rejects_inexact_total(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(
                    shop=self.shop,
                    terminal=self.terminal,
                    slot=1,
                    status=Order.Status.COMPLETED,
                    created_by=self.cashier,
                    current_cashier=self.cashier,
                    subtotal=Decimal("20.00"),
                    order_number="ORD-000099",
                    completed_by=self.cashier,
                    completed_at=timezone.now(),
                    final_total=Decimal("19.00"),
                )

    def test_payment_and_sale_movements_are_immutable_and_protect_order(self):
        draft = self.draft()
        result = complete_cash_checkout(
            self.cashier,
            draft.pk,
            draft.version,
            Decimal("20.00"),
        )

        with self.assertRaises(ValidationError):
            Payment.objects.filter(pk=result.payment.pk).update(amount=Decimal("1.00"))
        with self.assertRaises(ValidationError):
            result.payment.delete()
        movement = InventoryMovement.objects.get(order_item__order=result.order)
        with self.assertRaises(ValidationError):
            movement.delete()
        with self.assertRaises(ProtectedError):
            result.order.delete()

    def test_database_rejects_unlinked_sale_movement(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryMovement.objects.create(
                    shop=self.shop,
                    product=self.product,
                    movement_type=InventoryMovement.MovementType.SALE,
                    quantity_change=-1,
                    balance_after=4,
                    actor=self.cashier,
                    reason="Invalid unlinked sale",
                )
