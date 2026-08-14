import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, DocumentSequence, Shop, Terminal
from apps.inventory.models import InventoryMovement
from apps.sales.corrections import complete_return, returnable_items, void_order
from apps.sales.models import Order, OrderItem, OrderVoid, Payment, SalesReturn, SalesReturnItem


class CorrectionFixture(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Returns shop")
        DocumentSequence.objects.create(
            shop=self.shop, document_type=DocumentSequence.DocumentType.ORDER
        )
        DocumentSequence.objects.create(
            shop=self.shop, document_type=DocumentSequence.DocumentType.RETURN
        )
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Main checkout")
        self.owner = User.objects.create_user(
            username="return-owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )
        self.cashier = User.objects.create_user(
            username="return-cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.product_a = Product.objects.create(
            shop=self.shop,
            barcode="001",
            name="Tea",
            selling_price=Decimal("30.00"),
            stock_on_hand=8,
            created_by=self.owner,
        )
        self.product_b = Product.objects.create(
            shop=self.shop,
            barcode="002",
            name="Biscuits",
            selling_price=Decimal("20.00"),
            stock_on_hand=3,
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
            subtotal=Decimal("100.00"),
            final_total=Decimal("100.00"),
            order_number="ORD-000001",
        )
        self.item_a = OrderItem.objects.create(
            order=self.order,
            product=self.product_a,
            product_name="Tea old",
            product_barcode="001",
            unit_price=Decimal("30.00"),
            quantity=2,
            line_total=Decimal("60.00"),
        )
        self.item_b = OrderItem.objects.create(
            order=self.order,
            product=self.product_b,
            product_name="Biscuits",
            product_barcode="002",
            unit_price=Decimal("20.00"),
            quantity=2,
            line_total=Decimal("40.00"),
        )
        self.receipt = Payment.objects.create(
            shop=self.shop,
            order=self.order,
            direction=Payment.Direction.RECEIPT,
            amount=Decimal("100.00"),
            cash_received=Decimal("101.00"),
            change_given=Decimal("1.00"),
            processed_by=self.cashier,
        )

    def selections(self, *rows):
        return [
            {"order_item_id": item.pk, "quantity": quantity, "disposition": disposition}
            for item, quantity, disposition in rows
        ]


class ReturnServiceTests(CorrectionFixture):
    def test_blank_reason_is_allowed_and_refund_follows_returned_quantities(self):
        result = complete_return(
            actor=self.cashier,
            order_id=self.order.pk,
            request_token=uuid.uuid4(),
            reason="   ",
            selections=self.selections(
                (self.item_a, 2, SalesReturnItem.Disposition.RESTOCK),
                (self.item_b, 1, SalesReturnItem.Disposition.DAMAGED),
            ),
        )

        self.assertEqual(result.correction.reason, "")
        self.assertEqual(result.correction.total_refund, Decimal("80.00"))
        self.assertEqual(result.payment.amount, Decimal("80.00"))
        self.assertEqual(
            list(
                result.correction.items.order_by("order_item_id").values_list(
                    "quantity", "unit_refund", "line_refund"
                )
            ),
            [
                (2, Decimal("30.00"), Decimal("60.00")),
                (1, Decimal("20.00"), Decimal("20.00")),
            ],
        )

    def test_partial_return_uses_snapshots_and_only_restock_changes_stock(self):
        self.product_a.selling_price = Decimal("99.00")
        self.product_a.save(update_fields=["selling_price", "updated_at"])
        result = complete_return(
            actor=self.cashier,
            order_id=self.order.pk,
            request_token=uuid.uuid4(),
            reason="Customer return",
            selections=self.selections(
                (self.item_a, 1, SalesReturnItem.Disposition.RESTOCK),
                (self.item_b, 1, SalesReturnItem.Disposition.DAMAGED),
            ),
        )
        self.order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(result.correction.return_number, "RET-000001")
        self.assertEqual(result.payment.direction, Payment.Direction.REFUND)
        self.assertEqual(result.payment.amount, Decimal("50.00"))
        self.assertIsNone(result.payment.cash_received)
        self.assertEqual(self.order.status, Order.Status.PARTIALLY_RETURNED)
        self.assertEqual(self.product_a.stock_on_hand, 9)
        self.assertEqual(self.product_b.stock_on_hand, 3)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="RETURN").count(), 1)
        self.assertEqual(AuditEvent.objects.get().action, AuditEvent.Action.ORDER_RETURNED)

    def test_second_return_can_return_all_remaining_and_status_is_returned(self):
        complete_return(
            actor=self.cashier,
            order_id=self.order.pk,
            request_token=uuid.uuid4(),
            reason="First",
            selections=self.selections((self.item_a, 1, SalesReturnItem.Disposition.DAMAGED)),
        )
        complete_return(
            actor=self.owner,
            order_id=self.order.pk,
            request_token=uuid.uuid4(),
            reason="Everything else",
            selections=self.selections(
                (self.item_a, 1, SalesReturnItem.Disposition.RESTOCK),
                (self.item_b, 2, SalesReturnItem.Disposition.RESTOCK),
            ),
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.RETURNED)
        self.assertEqual([row.remaining_quantity for row in returnable_items(self.order)], [0, 0])
        self.assertEqual(SalesReturn.objects.count(), 2)

    def test_quantity_above_remaining_and_blank_selection_roll_back(self):
        before = (
            SalesReturn.objects.count(),
            Payment.objects.count(),
            self.product_a.stock_on_hand,
        )
        with self.assertRaises(ValidationError):
            complete_return(
                actor=self.cashier,
                order_id=self.order.pk,
                request_token=uuid.uuid4(),
                reason="Too many",
                selections=self.selections((self.item_a, 3, SalesReturnItem.Disposition.RESTOCK)),
            )
        self.product_a.refresh_from_db()
        self.assertEqual(
            before,
            (SalesReturn.objects.count(), Payment.objects.count(), self.product_a.stock_on_hand),
        )

    def test_same_request_token_is_idempotent_and_does_not_consume_number(self):
        token = uuid.uuid4()
        values = dict(
            actor=self.cashier,
            order_id=self.order.pk,
            request_token=token,
            reason="Retry",
            selections=self.selections((self.item_a, 1, SalesReturnItem.Disposition.RESTOCK)),
        )
        first = complete_return(**values)
        second = complete_return(**values)
        self.assertTrue(second.already_processed)
        self.assertEqual(first.correction.pk, second.correction.pk)
        self.assertEqual(SalesReturn.objects.count(), 1)
        self.assertEqual(
            DocumentSequence.objects.get(shop=self.shop, document_type="RETURN").next_number, 2
        )

    def test_return_records_are_immutable(self):
        result = complete_return(
            actor=self.cashier,
            order_id=self.order.pk,
            request_token=uuid.uuid4(),
            reason="Immutable",
            selections=self.selections((self.item_a, 1, SalesReturnItem.Disposition.DAMAGED)),
        )
        with self.assertRaises(ValidationError):
            SalesReturn.objects.filter(pk=result.correction.pk).update(reason="Changed")
        with self.assertRaises(ValidationError):
            result.payment.delete()


class VoidServiceTests(CorrectionFixture):
    def test_blank_void_reason_remains_invalid(self):
        with self.assertRaises(ValidationError):
            void_order(
                actor=self.owner,
                order_id=self.order.pk,
                request_token=uuid.uuid4(),
                reason="   ",
            )

        self.assertFalse(OrderVoid.objects.exists())

    def test_owner_void_refunds_sale_amount_and_reverses_every_line(self):
        result = void_order(
            actor=self.owner,
            order_id=self.order.pk,
            request_token=uuid.uuid4(),
            reason="Entered twice",
        )
        self.order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.VOIDED)
        self.assertEqual(result.payment.amount, Decimal("100.00"))
        self.assertEqual(self.product_a.stock_on_hand, 10)
        self.assertEqual(self.product_b.stock_on_hand, 5)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="VOID").count(), 2)
        self.assertEqual(AuditEvent.objects.get().action, AuditEvent.Action.ORDER_VOIDED)

    def test_cashier_cannot_void_and_return_prevents_void(self):
        with self.assertRaises(PermissionDenied):
            void_order(
                actor=self.cashier, order_id=self.order.pk, request_token=uuid.uuid4(), reason="No"
            )
        complete_return(
            actor=self.cashier,
            order_id=self.order.pk,
            request_token=uuid.uuid4(),
            reason="Returned",
            selections=self.selections((self.item_a, 1, SalesReturnItem.Disposition.DAMAGED)),
        )
        with self.assertRaises(ValidationError):
            void_order(
                actor=self.owner, order_id=self.order.pk, request_token=uuid.uuid4(), reason="No"
            )
        self.assertFalse(OrderVoid.objects.exists())

    def test_same_void_token_is_idempotent(self):
        token = uuid.uuid4()
        first = void_order(
            actor=self.owner, order_id=self.order.pk, request_token=token, reason="Retry"
        )
        second = void_order(
            actor=self.owner, order_id=self.order.pk, request_token=token, reason="Retry"
        )
        self.assertTrue(second.already_processed)
        self.assertEqual(first.correction.pk, second.correction.pk)
        self.assertEqual(OrderVoid.objects.count(), 1)


class CorrectionViewTests(CorrectionFixture):
    def test_cashier_return_fallback_and_manager_void_boundary(self):
        self.client.force_login(self.cashier)
        return_url = reverse("order_history:return", args=[self.order.order_number])
        get_response = self.client.get(return_url)
        self.assertContains(get_response, "Return all remaining")
        self.assertContains(get_response, "Return reason (optional)")
        self.assertContains(get_response, 'data-unit-minor="3000"')
        self.assertContains(get_response, 'data-unit-minor="2000"')
        self.assertNotContains(get_response, "Select disposition")
        self.assertContains(
            get_response,
            '<option value="RESTOCK" selected>Restock</option>',
            count=2,
            html=True,
        )
        token = get_response.context["form"].initial["request_token"]
        response = self.client.post(
            return_url,
            {
                "request_token": token,
                "reason": "",
                f"item-{self.item_a.pk}-order_item_id": self.item_a.pk,
                f"item-{self.item_a.pk}-quantity": 1,
                f"item-{self.item_a.pk}-disposition": "RESTOCK",
                f"item-{self.item_b.pk}-order_item_id": self.item_b.pk,
                f"item-{self.item_b.pk}-quantity": 0,
                f"item-{self.item_b.pk}-disposition": "",
            },
        )
        self.assertRedirects(
            response, reverse("order_history:detail", args=[self.order.order_number])
        )
        self.assertEqual(SalesReturn.objects.get().reason, "")
        detail = self.client.get(reverse("order_history:detail", args=[self.order.order_number]))
        self.assertNotContains(detail, "<strong>Reason:</strong>", html=True)
        self.assertEqual(
            self.client.get(
                reverse("order_history:void", args=[self.order.order_number])
            ).status_code,
            403,
        )

    def test_enhanced_dialog_and_order_detail_show_corrections(self):
        self.client.force_login(self.owner)
        url = reverse("order_history:void", args=[self.order.order_number])
        get_response = self.client.get(url, headers={"X-Order-Correction": "modal"})
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("dialog_html", get_response.json())
        token = VoidFormToken.from_html(get_response.json()["dialog_html"])
        response = self.client.post(
            url,
            {"request_token": token, "reason": "Duplicate sale"},
            headers={"X-Order-Correction": "modal"},
        )
        self.assertEqual(response.status_code, 200)
        detail = self.client.get(reverse("order_history:detail", args=[self.order.order_number]))
        self.assertContains(detail, "Order voided")
        self.assertContains(detail, "Duplicate sale")

    def test_order_filters_include_status_cashier_and_product_snapshot(self):
        self.client.force_login(self.cashier)
        for parameters in (
            {"q": "Tea old"},
            {"q": "001"},
            {"q": "100.00"},
            {"cashier": str(self.cashier.pk)},
            {"status": Order.Status.COMPLETED},
            {
                "date_from": timezone.localdate().isoformat(),
                "date_to": timezone.localdate().isoformat(),
            },
        ):
            with self.subTest(parameters=parameters):
                response = self.client.get(reverse("order_history:list"), parameters)
                self.assertContains(response, self.order.order_number)


class VoidFormToken:
    @staticmethod
    def from_html(html):
        marker = 'name="request_token" value="'
        return html.split(marker, 1)[1].split('"', 1)[0]
