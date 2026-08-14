from decimal import Decimal
from unittest.mock import patch

from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import DocumentSequence, Shop, Terminal
from apps.sales.checkout import complete_cash_checkout
from apps.sales.models import Order, OrderItem, Payment


@override_settings(POS_TERMINAL_CODE="TILL-1")
class CheckoutAndHistoryViewTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Web checkout shop")
        DocumentSequence.objects.create(shop=self.shop, document_type="ORDER")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")
        self.cashier = User.objects.create_user(
            username="web-cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            barcode="555",
            name="Tea",
            selling_price=Decimal("100.00"),
            stock_on_hand=20,
            created_by=self.cashier,
        )
        self.draft = self.create_draft(slot=1)
        self.client.force_login(self.cashier)

    def create_draft(self, *, slot):
        draft = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=slot,
            created_by=self.cashier,
            current_cashier=self.cashier,
            subtotal=Decimal("100.00"),
        )
        OrderItem.objects.create(
            order=draft,
            product=self.product,
            product_name="Captured Tea",
            product_barcode="555",
            unit_price=Decimal("100.00"),
            quantity=1,
            line_total=Decimal("100.00"),
        )
        return draft

    def checkout(self, cash_received):
        return self.client.post(
            reverse("sales:checkout", args=[self.draft.pk]),
            {"expected_version": self.draft.version, "cash_received": cash_received},
        )

    def enhanced_checkout(self, cash_received, *, expected_version=None, draft=None):
        draft = draft or self.draft
        return self.client.post(
            reverse("sales:checkout", args=[draft.pk]),
            {
                "expected_version": (
                    draft.version if expected_version is None else expected_version
                ),
                "cash_received": cash_received,
            },
            HTTP_X_POS_ENHANCED="1",
        )

    def test_checkout_is_one_post_and_detail_is_read_only(self):
        response = self.checkout("120.00")

        completed = Order.objects.get(pk=self.draft.pk)
        self.assertRedirects(
            response,
            reverse("order_history:detail", args=[completed.order_number]),
            fetch_redirect_response=False,
        )
        detail = self.client.get(response.url)
        self.assertContains(detail, "Captured Tea")
        self.assertContains(detail, "PKR 20.00")
        self.assertContains(detail, "Read-only record")
        self.assertNotContains(detail, "rounding", html=False)

    def test_cash_below_total_completes_without_confirmation(self):
        response = self.checkout("99.00")

        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, Decimal("100.00"))
        self.assertEqual(payment.cash_received, Decimal("99.00"))
        self.assertEqual(payment.change_given, Decimal("-1.00"))

    def test_enhanced_checkout_returns_fresh_workspace_and_recent_sale_without_redirect(self):
        second = self.create_draft(slot=2)

        response = self.enhanced_checkout("120.00")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        replacement = Order.objects.get(slot=1, status=Order.Status.DRAFT)
        self.assertEqual(payload["result"], "ok")
        self.assertEqual(payload["draft_id"], str(replacement.pk))
        self.assertIn(str(second.pk), payload["tabs_html"])
        self.assertIn("data-pos-recent-sales", payload["draft_panel_html"])
        self.assertIn("ORD-000001", payload["draft_panel_html"])
        self.assertIn("Stock 19", payload["draft_panel_html"])
        self.assertIn("Change PKR +20.00", payload["draft_panel_html"])
        self.assertIn("text-emerald-700", payload["draft_panel_html"])
        self.assertEqual(
            payload["completed_order"],
            {
                "order_number": "ORD-000001",
                "detail_url": reverse("order_history:detail", args=["ORD-000001"]),
                "total": "100.00",
                "cash_received": "120.00",
                "change": "20.00",
                "already_completed": False,
            },
        )
        self.assertEqual(Payment.objects.count(), 1)

    def test_enhanced_checkout_errors_are_json_and_preserve_the_draft(self):
        invalid = self.enhanced_checkout("-1.00")
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["result"], "invalid")
        self.assertIn('name="cash_received" value="-1.00"', invalid.json()["draft_panel_html"])
        self.assertIn("data-pos-checkout-dialog", invalid.json()["draft_panel_html"])
        self.assertIn('aria-invalid="true"', invalid.json()["draft_panel_html"])

        conflict = self.enhanced_checkout("100.00", expected_version=999)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["result"], "conflict")

        missing = self.client.post(
            reverse("sales:checkout", args=[999999]),
            {"expected_version": "1", "cash_received": "100.00"},
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["result"], "not_found")
        self.assertTrue(Order.objects.filter(pk=self.draft.pk, status=Order.Status.DRAFT).exists())
        self.assertFalse(Payment.objects.exists())

    def test_enhanced_checkout_database_failure_is_safe_json(self):
        with patch(
            "apps.sales.checkout_views.complete_cash_checkout",
            side_effect=DatabaseError("database unavailable"),
        ):
            response = self.enhanced_checkout("100.00")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["result"], "unavailable")
        self.assertTrue(Order.objects.filter(pk=self.draft.pk, status=Order.Status.DRAFT).exists())
        self.assertFalse(Payment.objects.exists())

    def test_enhanced_checkout_replay_is_idempotent_and_returns_current_workspace(self):
        first = self.enhanced_checkout("100.00")
        self.assertEqual(first.status_code, 200)

        replay = self.enhanced_checkout("999.00", expected_version=1)

        self.assertEqual(replay.status_code, 200)
        self.assertIs(replay.json()["completed_order"]["already_completed"], True)
        self.assertEqual(Payment.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 19)

    def test_checkout_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.cashier)
        response = csrf_client.post(
            reverse("sales:checkout", args=[self.draft.pk]),
            {"expected_version": self.draft.version, "cash_received": "100.00"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Payment.objects.exists())

    def test_history_search_change_filter_and_shop_isolation(self):
        completed = complete_cash_checkout(
            self.cashier,
            self.draft.pk,
            self.draft.version,
            Decimal("101.00"),
        ).order

        for query in (completed.order_number, "Captured Tea", "555", "100.00"):
            with self.subTest(query=query):
                response = self.client.get(reverse("order_history:list"), {"q": query})
                self.assertContains(response, completed.order_number)
        changed = self.client.get(reverse("order_history:list"), {"has_change": "on"})
        self.assertContains(changed, completed.order_number)
        self.assertContains(changed, "PKR 1.00")

        other_shop = Shop.objects.create(name="Other shop")
        other_user = User.objects.create_user(
            username="other-cashier",
            password="StrongPass!2026",
            shop=other_shop,
            role=User.Role.CASHIER,
        )
        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(
                reverse("order_history:detail", args=[completed.order_number])
            ).status_code,
            404,
        )

    def test_history_paginates_fifty_newest_first(self):
        completed = complete_cash_checkout(
            self.cashier,
            self.draft.pk,
            self.draft.version,
            Decimal("100.00"),
        ).order
        for number in range(2, 52):
            Order.objects.create(
                shop=self.shop,
                terminal=self.terminal,
                slot=1,
                status=Order.Status.COMPLETED,
                created_by=self.cashier,
                current_cashier=self.cashier,
                subtotal=Decimal("1.00"),
                order_number=f"ORD-{number:06d}",
                completed_by=self.cashier,
                completed_at=completed.completed_at,
                final_total=Decimal("1.00"),
            )
        first_page = self.client.get(reverse("order_history:list"))
        self.assertEqual(len(first_page.context["orders"]), 50)
        self.assertEqual(first_page.context["orders"][0].order_number, "ORD-000051")
        second_page = self.client.get(reverse("order_history:list"), {"page": 2})
        self.assertEqual(len(second_page.context["orders"]), 1)
        self.assertEqual(second_page.context["orders"][0].order_number, "ORD-000001")
