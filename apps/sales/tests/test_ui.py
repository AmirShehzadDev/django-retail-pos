from decimal import Decimal

from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import Shop, Terminal
from apps.sales.models import Order, OrderItem


class PosTemplateTests(TestCase):
    password = "StrongPass!2026"

    def setUp(self):
        self.shop = Shop.objects.create(name="UI Shop")
        self.terminal = Terminal.objects.create(
            shop=self.shop,
            code="TILL-1",
            name="Main Checkout",
        )
        self.owner = self._user("owner", User.Role.OWNER)
        self.admin = self._user("admin", User.Role.ADMIN)
        self.cashier = self._user("cashier", User.Role.CASHIER)
        self.product = Product.objects.create(
            shop=self.shop,
            barcode="001234",
            sku="TEA-1",
            name="Tea",
            selling_price=Decimal("1250.00"),
            stock_on_hand=0,
            created_by=self.owner,
        )
        self.client.force_login(self.owner)

    def _user(self, username, role):
        return User.objects.create_user(
            username=username,
            password=self.password,
            shop=self.shop,
            role=role,
        )

    def _draft(self, *, slot=1, cashier=None):
        return Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=slot,
            created_by=self.owner,
            current_cashier=cashier or self.owner,
        )

    def _line(self, draft, *, product=None):
        product = product or self.product
        draft.subtotal = Decimal("2500.00")
        draft.save(update_fields=["subtotal"])
        return OrderItem.objects.create(
            order=draft,
            product=product,
            product_name=product.name,
            product_barcode=product.barcode,
            unit_price=Decimal("1250.00"),
            quantity=2,
            line_total=Decimal("2500.00"),
        )

    def test_all_sales_templates_parse(self):
        names = (
            "sales/pos_workspace.html",
            "sales/partials/draft_tabs.html",
            "sales/partials/draft_panel.html",
            "sales/partials/draft_line.html",
            "sales/quick_create.html",
            "sales/takeover_confirm.html",
            "sales/clear_confirm.html",
            "sales/terminal_unavailable.html",
        )
        for name in names:
            with self.subTest(template=name):
                self.assertIsNotNone(get_template(name))

    def test_pos_navigation_and_home_card_are_visible_to_every_role(self):
        pos_url = reverse("sales:workspace")
        for user in (self.owner, self.admin, self.cashier):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("core:home"))
                self.assertContains(response, pos_url, count=2)
                self.assertContains(response, 'aria-label="Primary navigation"')
                if user.role == User.Role.CASHIER:
                    self.assertContains(response, reverse("catalog:product_list"), count=2)
                    self.assertNotContains(response, reverse("inventory:scan"))

    def test_empty_workspace_has_protected_visible_auto_start_fallback(self):
        response = self.client.get(reverse("sales:workspace"))

        self.assertContains(response, "Start Order 1")
        self.assertContains(response, "data-pos-initial-start")
        self.assertContains(response, "data-pos-new-draft")
        self.assertContains(
            response,
            'data-pos-new-draft data-pos-success="New order ready." hidden',
        )
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, "static/js/pos.js")
        self.assertContains(response, 'aria-live="assertive"')

    def test_enhanced_draft_state_reports_when_another_tab_can_be_created(self):
        start = self.client.post(
            reverse("sales:start_workspace"),
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertIs(start.json()["can_create_draft"], True)

        second = self.client.post(
            reverse("sales:draft_create"),
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertIs(second.json()["can_create_draft"], True)

        third = self.client.post(
            reverse("sales:draft_create"),
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertIs(third.json()["can_create_draft"], False)

    def test_editable_workspace_renders_tabs_scanner_search_snapshots_and_totals(self):
        draft = self._draft()
        self._line(draft)
        self._draft(slot=2)
        self._draft(slot=3)

        response = self.client.get(
            reverse("sales:workspace"),
            {"draft": str(draft.pk), "q": "tea"},
        )

        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "data-pos-shell")
        self.assertContains(response, 'aria-label="POS toolbar"')
        self.assertContains(response, 'aria-label="POS navigation"')
        self.assertNotContains(response, 'aria-label="Primary navigation"')
        self.assertContains(response, reverse("order_history:list"))
        self.assertContains(response, reverse("catalog:product_list"))
        self.assertContains(response, reverse("core:home"))
        self.assertContains(
            response,
            "lg:grid-cols-[minmax(0,13fr)_minmax(18rem,7fr)]",
        )
        self.assertContains(response, 'class="grid grid-cols-2 gap-2"')
        self.assertContains(response, "data-pos-product-tile")
        self.assertContains(response, "data-pos-cart-scroll")
        self.assertContains(response, "data-pos-catalogue-scroll")
        self.assertContains(response, "data-pos-recent-sales")
        self.assertContains(response, "mx-2 mb-2 mt-3")
        self.assertContains(response, "rounded-lg border-2 border-brand-700")
        self.assertNotContains(response, "shadow-[0_-3px_8px_rgba(15,23,42,0.10)]")
        self.assertContains(response, "bg-slate-100 px-2.5 py-2")
        self.assertContains(response, "No completed sales yet.")
        self.assertContains(response, "data-pos-checkout")
        self.assertContains(response, 'data-pos-checkout data-pos-success="Sale completed."')
        self.assertContains(response, "data-pos-checkout-trigger")
        self.assertContains(response, "data-pos-checkout-dialog")
        self.assertContains(response, "data-pos-checkout-lines")
        self.assertContains(response, "data-pos-checkout-line")
        self.assertContains(response, "data-pos-cash-received")
        self.assertContains(response, "data-pos-checkout-confirm")
        self.assertContains(response, "data-pos-checkout-cancel")
        self.assertContains(response, "Review the order and enter the cash received.")
        self.assertContains(response, "2 &times; PKR 1,250.00")
        self.assertContains(response, 'name="cash_received" value="2500.00"')
        self.assertContains(response, 'inputmode="decimal" autocomplete="off"')
        self.assertContains(response, "<noscript>", html=False)
        self.assertContains(response, "data-pos-scan-form")
        self.assertContains(response, "Search products")
        self.assertContains(response, "Tea")
        self.assertContains(response, "Barcode 001234")
        self.assertContains(response, "PKR 1,250.00")
        self.assertContains(response, "PKR 2,500.00")
        self.assertContains(response, "Stock 0")
        self.assertContains(response, "Product catalogue")
        self.assertContains(response, "Cash received")
        self.assertContains(response, "Change")
        self.assertContains(response, "Complete sale")
        self.assertContains(response, 'aria-label="Decrease quantity for Tea"')
        self.assertContains(response, 'aria-label="Increase quantity for Tea"')
        self.assertContains(response, 'name="quantity" value="1"')
        self.assertContains(response, 'name="quantity" value="3"')
        self.assertNotContains(response, ">Update<")
        self.assertNotContains(response, "text-3xl")
        self.assertContains(
            response,
            'data-pos-new-draft data-pos-success="New order ready." hidden',
        )
        for excluded in ("Round off", "Payment history", "Change due"):
            self.assertNotContains(response, excluded)

    def test_foreign_cashier_workspace_is_read_only_until_confirmed_resume(self):
        draft = self._draft(cashier=self.owner)
        self._line(draft)
        self.client.force_login(self.cashier)

        response = self.client.get(reverse("sales:workspace"), {"draft": draft.pk})

        self.assertContains(response, "Read-only order")
        self.assertContains(response, "Resume this order")
        self.assertNotContains(response, "data-pos-scan-form")
        self.assertNotContains(response, "data-pos-checkout")
        self.assertNotContains(response, 'name="cash_received"')
        self.assertNotContains(response, "Complete sale")
        self.assertNotContains(response, ">Remove<")
        self.assertNotContains(response, 'aria-label="Increase quantity for Tea"')

        confirmation = self.client.get(reverse("sales:draft_takeover", args=[draft.pk]))
        self.assertContains(confirmation, "Confirm resume")
        self.assertContains(confirmation, self.owner.username)
        self.assertContains(confirmation, "PKR 2,500.00")

    def test_inactive_retained_line_is_labelled_and_has_reduction_controls(self):
        draft = self._draft()
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        self._line(draft)

        response = self.client.get(reverse("sales:workspace"), {"draft": draft.pk})

        self.assertContains(response, "Inactive product")
        self.assertContains(response, "may only be reduced or removed")
        self.assertContains(response, 'aria-label="Decrease quantity for Tea"')
        self.assertContains(response, 'title="Increase quantity" disabled')
        self.assertNotContains(response, ">Update<")
        self.assertContains(response, ">Remove<")

    def test_quantity_one_keeps_disabled_decrease_and_enabled_increase_visible(self):
        draft = self._draft()
        item = self._line(draft)
        item.quantity = 1
        item.line_total = Decimal("1250.00")
        item.save(update_fields=["quantity", "line_total"])
        draft.subtotal = Decimal("1250.00")
        draft.save(update_fields=["subtotal"])

        response = self.client.get(reverse("sales:workspace"), {"draft": draft.pk})

        self.assertContains(response, 'title="Decrease quantity" disabled')
        self.assertContains(response, 'aria-label="Increase quantity for Tea"')
        self.assertNotContains(response, 'title="Increase quantity" disabled')

    def test_catalogue_no_result_state_remains_in_the_compact_pane(self):
        draft = self._draft()

        response = self.client.get(
            reverse("sales:workspace"),
            {"draft": draft.pk, "q": "not-a-real-product"},
        )

        self.assertContains(response, "No active products matched.")
        self.assertContains(response, "Clear")
        self.assertContains(response, "data-pos-catalogue-scroll")
        self.assertNotContains(response, "data-pos-product-tile")

    def test_populated_order_shows_clear_dialog_and_fallback_without_reason(self):
        draft = self._draft()
        self._line(draft)

        workspace = self.client.get(reverse("sales:workspace"), {"draft": draft.pk})
        fallback = self.client.get(reverse("sales:draft_clear", args=[draft.pk]))

        self.assertContains(workspace, "Clear order", count=2)
        self.assertContains(workspace, "data-pos-clear-trigger")
        self.assertContains(workspace, "data-pos-clear-dialog")
        self.assertContains(workspace, "Keep order")
        self.assertNotContains(workspace, "Discard order")
        self.assertNotContains(workspace, "Reason")
        self.assertContains(fallback, "Clear Order 1?")
        self.assertContains(fallback, "1 item - PKR 2,500.00")
        self.assertContains(fallback, "keeps the tab open")

    def test_empty_tab_close_action_requires_another_editable_tab(self):
        first = self._draft(slot=1)
        only = self.client.get(reverse("sales:workspace"), {"draft": first.pk})
        self.assertNotContains(only, "Close tab")
        self.assertNotContains(only, "Clear order")
        self.assertContains(only, "data-pos-checkout-trigger disabled")
        self.assertNotContains(only, "data-pos-checkout-dialog")
        self.assertNotContains(only, 'name="cash_received"')

        second = self._draft(slot=2)
        eligible = self.client.get(reverse("sales:workspace"), {"draft": second.pk})
        self.assertContains(eligible, "Close tab")
        self.assertContains(eligible, "data-pos-toast-success")

        second.current_cashier = self.cashier
        second.save(update_fields=["current_cashier"])
        read_only = self.client.get(reverse("sales:workspace"), {"draft": second.pk})
        self.assertNotContains(read_only, "Close tab")

    def test_enhanced_fragments_keep_the_frozen_boundaries(self):
        draft = self._draft()
        response = self.client.post(
            reverse("sales:draft_scan", args=[draft.pk]),
            {"barcode": self.product.barcode, "expected_version": "1"},
            HTTP_X_POS_ENHANCED="1",
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(payload["draft_id"], str)
        self.assertIsInstance(payload["version"], str)
        self.assertIn('id="pos-draft-tabs"', payload["tabs_html"])
        self.assertIn('id="pos-draft-panel"', payload["draft_panel_html"])
        self.assertNotIn("<script", payload["tabs_html"] + payload["draft_panel_html"])
