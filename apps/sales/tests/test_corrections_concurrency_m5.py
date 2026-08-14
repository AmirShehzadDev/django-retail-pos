import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, DocumentSequence, Shop, Terminal
from apps.inventory.models import InventoryMovement
from apps.sales.corrections import complete_return, void_order
from apps.sales.models import Order, OrderItem, OrderVoid, Payment, SalesReturn, SalesReturnItem


class CorrectionConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.shop = Shop.objects.create(name="Correction concurrency shop")
        DocumentSequence.objects.create(shop=self.shop, document_type="RETURN")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")
        self.owner = User.objects.create_user(
            username="correction-owner", shop=self.shop, role=User.Role.OWNER
        )
        self.cashier = User.objects.create_user(
            username="correction-cashier", shop=self.shop, role=User.Role.CASHIER
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Rice",
            barcode="700",
            selling_price=Decimal("10.00"),
            stock_on_hand=8,
            created_by=self.owner,
        )
        self.order = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=1,
            status=Order.Status.COMPLETED,
            created_by=self.cashier,
            current_cashier=self.cashier,
            completed_by=self.cashier,
            completed_at=timezone.now(),
            subtotal=Decimal("20.00"),
            final_total=Decimal("20.00"),
            order_number="ORD-000001",
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name="Rice",
            product_barcode="700",
            unit_price=Decimal("10.00"),
            quantity=2,
            line_total=Decimal("20.00"),
        )
        Payment.objects.create(
            shop=self.shop,
            order=self.order,
            amount=Decimal("20.00"),
            cash_received=Decimal("20.00"),
            change_given=Decimal("0.00"),
            processed_by=self.cashier,
        )

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def race(self, *operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    operation()
                    return "committed"
                except ValidationError:
                    return "rejected"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as executor:
            futures = [executor.submit(run, operation) for operation in operations]
            return [future.result(timeout=30) for future in futures]

    def return_operation(self):
        actor = User.objects.get(pk=self.cashier.pk)
        complete_return(
            actor=actor,
            order_id=self.order.pk,
            request_token=uuid.uuid4(),
            reason="Concurrent return",
            selections=[
                {
                    "order_item_id": self.item.pk,
                    "quantity": 2,
                    "disposition": SalesReturnItem.Disposition.RESTOCK,
                }
            ],
        )

    def test_competing_full_returns_commit_once(self):
        outcomes = self.race(self.return_operation, self.return_operation)

        self.assertCountEqual(outcomes, ["committed", "rejected"])
        self.assertEqual(SalesReturn.objects.count(), 1)
        self.assertEqual(Payment.objects.filter(direction="REFUND").count(), 1)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="RETURN").count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="ORDER_RETURNED").count(), 1)

    def test_return_and_void_are_mutually_exclusive_under_race(self):
        def void_operation():
            actor = User.objects.get(pk=self.owner.pk)
            void_order(
                actor=actor,
                order_id=self.order.pk,
                request_token=uuid.uuid4(),
                reason="Concurrent void",
            )

        outcomes = self.race(self.return_operation, void_operation)

        self.assertCountEqual(outcomes, ["committed", "rejected"])
        self.assertEqual(SalesReturn.objects.count() + OrderVoid.objects.count(), 1)
        self.assertEqual(Payment.objects.filter(direction="REFUND").count(), 1)
        self.assertEqual(
            InventoryMovement.objects.filter(movement_type__in=["RETURN", "VOID"]).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(action__in=["ORDER_RETURNED", "ORDER_VOIDED"]).count(),
            1,
        )
