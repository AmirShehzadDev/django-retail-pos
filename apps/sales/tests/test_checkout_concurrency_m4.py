from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import DocumentSequence, Shop, Terminal
from apps.inventory.models import InventoryMovement
from apps.sales.checkout import complete_cash_checkout
from apps.sales.models import Order, OrderItem, Payment


@override_settings(POS_TERMINAL_CODE="TILL-1")
class CheckoutConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.shop = Shop.objects.create(name="Checkout concurrency shop")
        DocumentSequence.objects.create(shop=self.shop, document_type="ORDER")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")
        self.first_cashier = self.user("first")
        self.second_cashier = self.user("second")
        self.product = Product.objects.create(
            shop=self.shop,
            name="Rice",
            barcode="700",
            selling_price=Decimal("10.00"),
            stock_on_hand=3,
            created_by=self.first_cashier,
        )

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def user(self, username):
        return User.objects.create_user(
            username=username,
            password=None,
            shop=self.shop,
            role=User.Role.CASHIER,
        )

    def draft(self, actor, slot):
        order = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=slot,
            created_by=actor,
            current_cashier=actor,
            subtotal=Decimal("20.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name="Rice",
            product_barcode="700",
            unit_price=Decimal("10.00"),
            quantity=2,
            line_total=Decimal("20.00"),
        )
        return order

    def race(self, *operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as executor:
            futures = [executor.submit(run, operation) for operation in operations]
            return [future.result(timeout=30) for future in futures]

    def test_same_draft_concurrent_submit_creates_one_aggregate(self):
        draft = self.draft(self.first_cashier, 1)

        def checkout():
            actor = User.objects.get(pk=self.first_cashier.pk)
            result = complete_cash_checkout(
                actor,
                draft.pk,
                draft.version,
                Decimal("20.00"),
            )
            return result.order.order_number, result.already_completed

        outcomes = self.race(checkout, checkout)

        self.assertEqual({number for number, _ in outcomes}, {"ORD-000001"})
        self.assertCountEqual([repeated for _, repeated in outcomes], [False, True])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="SALE").count(), 1)
        self.assertEqual(Order.objects.filter(status=Order.Status.COMPLETED).count(), 1)
        self.assertEqual(Order.objects.filter(status=Order.Status.DRAFT).count(), 1)

    def test_same_product_checkouts_serialize_and_record_emerging_shortage(self):
        first = self.draft(self.first_cashier, 1)
        second = self.draft(self.second_cashier, 2)

        def checkout(actor_id, draft_id):
            actor = User.objects.get(pk=actor_id)
            result = complete_cash_checkout(actor, draft_id, 1, Decimal("20.00"))
            return draft_id, result.order.order_number

        outcomes = self.race(
            lambda: checkout(self.first_cashier.pk, first.pk),
            lambda: checkout(self.second_cashier.pk, second.pk),
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, -1)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="SALE").count(), 2)
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(
            set(Order.objects.filter(status="COMPLETED").values_list("order_number", flat=True)),
            {"ORD-000001", "ORD-000002"},
        )
