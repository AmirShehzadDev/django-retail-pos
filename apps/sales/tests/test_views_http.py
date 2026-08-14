from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, Shop, Terminal
from apps.sales.models import Order, OrderItem

TEST_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "sales/pos_workspace.html": (
                            "{% csrf_token %}workspace {{ selected_draft_id }} "
                            "{{ selected_version }}"
                        ),
                        "sales/quick_create.html": (
                            "{% csrf_token %}quick-create {{ barcode }} {{ form.errors }}"
                        ),
                        "sales/takeover_confirm.html": (
                            "{% csrf_token %}takeover {{ draft.id }} {{ form.errors }}"
                        ),
                        "sales/clear_confirm.html": (
                            "{% csrf_token %}clear {{ draft.id }} {{ draft.item_count }} "
                            "{{ form.errors }}"
                        ),
                        "sales/terminal_unavailable.html": (
                            "unavailable {{ terminal_error_message }}"
                        ),
                        "sales/partials/draft_tabs.html": "tabs {{ selected_draft_id }}",
                        "sales/partials/draft_panel.html": (
                            "panel {{ selected_draft_id }} {{ selected_version }}"
                        ),
                    },
                )
            ],
        },
    }
]


@override_settings(TEMPLATES=TEST_TEMPLATES, POS_TERMINAL_CODE="TILL-1")
class PosViewTests(TestCase):
    password = "StrongPass!2026"

    def setUp(self):
        self.shop = Shop.objects.create(name="POS Shop")
        self.terminal = Terminal.objects.create(
            shop=self.shop,
            code="TILL-1",
            name="Main checkout",
        )
        self.owner = self._user("owner", User.Role.OWNER)
        self.cashier = self._user("cashier", User.Role.CASHIER)
        self.product = Product.objects.create(
            shop=self.shop,
            barcode="0012345",
            sku="RICE-1",
            name="Rice",
            selling_price=Decimal("125.00"),
            created_by=self.owner,
        )
        self.client.force_login(self.owner)

    def _user(self, username, role, *, shop=None):
        return User.objects.create_user(
            username=username,
            password=self.password,
            shop=shop or self.shop,
            role=role,
        )

    def _draft(self, *, current_cashier=None, slot=1, shop=None, terminal=None):
        shop = shop or self.shop
        return Order.objects.create(
            shop=shop,
            terminal=terminal or self.terminal,
            slot=slot,
            created_by=self.owner,
            current_cashier=current_cashier or self.owner,
        )

    def _item(self, draft, *, quantity=1):
        return OrderItem.objects.create(
            order=draft,
            product=self.product,
            product_name=self.product.name,
            product_barcode=self.product.barcode,
            unit_price=self.product.selling_price,
            quantity=quantity,
            line_total=self.product.selling_price * quantity,
        )

    def test_routes_match_the_reviewed_surface(self):
        draft = self._draft()
        item = self._item(draft)
        expected = {
            "workspace": "/pos/",
            "start_workspace": "/pos/start/",
            "draft_create": "/pos/drafts/new/",
            "draft_scan": f"/pos/drafts/{draft.pk}/scan/",
            "draft_add_product": f"/pos/drafts/{draft.pk}/products/add/",
            "quick_create": f"/pos/drafts/{draft.pk}/quick-create/",
            "item_quantity": f"/pos/drafts/{draft.pk}/items/{item.pk}/quantity/",
            "item_remove": f"/pos/drafts/{draft.pk}/items/{item.pk}/remove/",
            "draft_takeover": f"/pos/drafts/{draft.pk}/takeover/",
            "draft_clear": f"/pos/drafts/{draft.pk}/clear/",
            "draft_close": f"/pos/drafts/{draft.pk}/close/",
            "checkout": f"/pos/drafts/{draft.pk}/checkout/",
        }
        for name, path in expected.items():
            kwargs = {"draft_id": draft.pk}
            if name.startswith("item_"):
                kwargs["item_id"] = item.pk
            if name in {"workspace", "start_workspace", "draft_create"}:
                kwargs = {}
            with self.subTest(name=name):
                self.assertEqual(reverse(f"sales:{name}", kwargs=kwargs), path)
        for name in ("draft_discard", "payment", "history", "return", "void"):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(f"sales:{name}")

    def test_anonymous_redirects_and_mutations_are_csrf_protected(self):
        self.client.logout()
        url = reverse("sales:workspace")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        response = csrf_client.post(reverse("sales:start_workspace"))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Order.objects.exists())

    def test_workspace_get_is_read_only_no_store_and_exposes_start_context(self):
        before = (Order.objects.count(), Product.objects.count(), AuditEvent.objects.count())

        response = self.client.get(reverse("sales:workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            before, (Order.objects.count(), Product.objects.count(), AuditEvent.objects.count())
        )
        self.assertTrue(response.context["needs_initial_draft"])
        self.assertEqual(response.context["drafts"], ())
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_start_is_post_only_and_idempotent(self):
        url = reverse("sales:start_workspace")
        self.assertEqual(self.client.get(url).status_code, 405)

        first = self.client.post(url)
        second = self.client.post(url)

        draft = Order.objects.get()
        self.assertRedirects(first, f"{reverse('sales:workspace')}?draft={draft.pk}")
        self.assertRedirects(second, f"{reverse('sales:workspace')}?draft={draft.pk}")
        self.assertEqual(draft.slot, 1)

    def test_mutation_only_routes_reject_get(self):
        draft = self._draft()
        item = self._item(draft)
        urls = (
            reverse("sales:start_workspace"),
            reverse("sales:draft_create"),
            reverse("sales:draft_scan", args=[draft.pk]),
            reverse("sales:draft_add_product", args=[draft.pk]),
            reverse("sales:item_quantity", args=[draft.pk, item.pk]),
            reverse("sales:item_remove", args=[draft.pk, item.pk]),
            reverse("sales:draft_close", args=[draft.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    @override_settings(POS_TERMINAL_CODE="MISSING")
    def test_terminal_failure_is_safe_503_and_creates_nothing(self):
        normal = self.client.get(reverse("sales:workspace"))
        enhanced = self.client.post(
            reverse("sales:start_workspace"),
            HTTP_X_POS_ENHANCED="1",
        )

        self.assertEqual(normal.status_code, 503)
        self.assertContains(normal, "configured POS terminal is unavailable", status_code=503)
        self.assertEqual(enhanced.status_code, 503)
        self.assertEqual(enhanced.json()["result"], "unavailable")
        self.assertFalse(Order.objects.exists())

    def test_new_draft_uses_lowest_slot_and_enhanced_limit_is_409(self):
        first = self._draft(slot=1)
        third = self._draft(slot=3)
        response = self.client.post(reverse("sales:draft_create"))
        second = Order.objects.get(slot=2)
        self.assertRedirects(response, f"{reverse('sales:workspace')}?draft={second.pk}")

        response = self.client.post(
            reverse("sales:draft_create"),
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["result"], "draft_limit")
        self.assertEqual(
            set(Order.objects.values_list("pk", flat=True)),
            {first.pk, second.pk, third.pk},
        )

    def test_known_scan_uses_prg_and_enhanced_ids_are_decimal_strings(self):
        draft = self._draft()
        url = reverse("sales:draft_scan", args=[draft.pk])
        response = self.client.post(
            url,
            {"barcode": self.product.barcode, "expected_version": str(draft.version)},
        )
        draft.refresh_from_db()
        self.assertRedirects(response, f"{reverse('sales:workspace')}?draft={draft.pk}")

        response = self.client.post(
            url,
            {"barcode": self.product.barcode, "expected_version": str(draft.version)},
            HTTP_X_POS_ENHANCED="1",
        )
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["draft_id"], str(draft.pk))
        self.assertIsInstance(payload["draft_id"], str)
        self.assertIsInstance(payload["version"], str)
        self.assertIn("tabs_html", payload)
        self.assertIn("draft_panel_html", payload)

    def test_unknown_scan_redirects_to_session_bound_quick_create(self):
        draft = self._draft()
        scan_url = reverse("sales:draft_scan", args=[draft.pk])
        response = self.client.post(
            scan_url,
            {"barcode": "009999", "expected_version": "1"},
        )

        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response.url)
        token = parse_qs(parsed.query)["context"][0]
        self.assertEqual(parsed.path, reverse("sales:quick_create", args=[draft.pk]))
        self.assertNotIn(self.client.session.session_key, token)
        get_response = self.client.get(response.url)
        self.assertContains(get_response, "009999")
        self.assertEqual(Product.objects.count(), 1)

    def test_enhanced_unknown_scan_returns_queue_boundary_next_url(self):
        draft = self._draft()
        response = self.client.post(
            reverse("sales:draft_scan", args=[draft.pk]),
            {"barcode": "009999", "expected_version": "1"},
            HTTP_X_POS_ENHANCED="1",
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["result"], "quick_create_required")
        self.assertEqual(payload["draft_id"], str(draft.pk))
        self.assertEqual(payload["version"], "1")
        self.assertIn("context=", payload["next_url"])
        self.assertNotIn("tabs_html", payload)

    def test_quick_create_post_uses_signed_barcode_and_ignores_crafted_metadata(self):
        draft = self._draft()
        scan_response = self.client.post(
            reverse("sales:draft_scan", args=[draft.pk]),
            {"barcode": "000777", "expected_version": "1"},
        )
        token = parse_qs(urlparse(scan_response.url).query)["context"][0]

        response = self.client.post(
            reverse("sales:quick_create", args=[draft.pk]),
            {
                "context": token,
                "name": "  Walk-in product  ",
                "selling_price": "10.00",
                "barcode": "crafted",
                "stock_on_hand": "999",
                "shop": "999",
                "needs_review": "false",
            },
        )

        created = Product.objects.get(barcode="000777")
        self.assertRedirects(response, f"{reverse('sales:workspace')}?draft={draft.pk}")
        self.assertEqual(created.name, "Walk-in product")
        self.assertEqual(created.stock_on_hand, 0)
        self.assertEqual(created.shop, self.shop)
        self.assertTrue(created.needs_review)
        self.assertEqual(created.order_items.get().order, draft)
        self.assertEqual(AuditEvent.objects.get().action, AuditEvent.Action.PRODUCT_QUICK_CREATED)

    def test_quick_create_context_is_invalid_after_session_change(self):
        draft = self._draft()
        scan_response = self.client.post(
            reverse("sales:draft_scan", args=[draft.pk]),
            {"barcode": "000777", "expected_version": "1"},
        )
        self.client.logout()
        self.client.force_login(self.owner)

        response = self.client.get(scan_response.url)

        self.assertRedirects(response, f"{reverse('sales:workspace')}?draft={draft.pk}")
        self.assertFalse(Product.objects.filter(barcode="000777").exists())

    def test_barcode_now_known_maps_to_enhanced_409_guidance(self):
        draft = self._draft()
        scan_response = self.client.post(
            reverse("sales:draft_scan", args=[draft.pk]),
            {"barcode": "000777", "expected_version": "1"},
        )
        token = parse_qs(urlparse(scan_response.url).query)["context"][0]
        winner = Product.objects.create(
            shop=self.shop,
            barcode="000777",
            name="Concurrent product",
            selling_price=Decimal("9.00"),
            created_by=self.owner,
        )

        response = self.client.post(
            reverse("sales:quick_create", args=[draft.pk]),
            {"context": token, "name": "Losing product", "selling_price": "10.00"},
            HTTP_X_POS_ENHANCED="1",
        )

        payload = response.json()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(payload["result"], "barcode_now_known")
        self.assertEqual(payload["known_product_id"], str(winner.pk))
        self.assertIs(payload["known_product_active"], True)
        self.assertEqual(Product.objects.filter(barcode="000777").count(), 1)
        self.assertFalse(OrderItem.objects.exists())

    def test_stale_enhanced_mutation_returns_fresh_409_fragments_without_replay(self):
        draft = self._draft()
        draft.version = 2
        draft.save(update_fields=["version"])

        response = self.client.post(
            reverse("sales:draft_add_product", args=[draft.pk]),
            {"product_id": str(self.product.pk), "expected_version": "1"},
            HTTP_X_POS_ENHANCED="1",
        )

        payload = response.json()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(payload["result"], "conflict")
        self.assertEqual(payload["draft_id"], str(draft.pk))
        self.assertEqual(payload["version"], "2")
        self.assertFalse(OrderItem.objects.exists())

    def test_invalid_quantity_is_422_and_does_not_mutate(self):
        draft = self._draft()
        item = self._item(draft)

        response = self.client.post(
            reverse("sales:item_quantity", args=[draft.pk, item.pk]),
            {"quantity": "1e2", "expected_version": "1"},
            HTTP_X_POS_ENHANCED="1",
        )

        self.assertEqual(response.status_code, 422)
        item.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(item.quantity, 1)
        self.assertEqual(draft.version, 1)

    def test_search_add_quantity_and_remove_use_only_server_values(self):
        draft = self._draft()
        original_stock = self.product.stock_on_hand

        add_response = self.client.post(
            reverse("sales:draft_add_product", args=[draft.pk]),
            {
                "product_id": str(self.product.pk),
                "expected_version": "1",
                "unit_price": "0.01",
                "subtotal": "0.01",
            },
        )
        item = OrderItem.objects.get(order=draft)
        draft.refresh_from_db()
        self.assertEqual(add_response.status_code, 302)
        self.assertEqual(item.unit_price, Decimal("125.00"))
        self.assertEqual(draft.version, 2)

        quantity_response = self.client.post(
            reverse("sales:item_quantity", args=[draft.pk, item.pk]),
            {"quantity": "3", "expected_version": "2", "line_total": "0.01"},
        )
        item.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(quantity_response.status_code, 302)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.line_total, Decimal("375.00"))
        self.assertEqual(draft.subtotal, Decimal("375.00"))
        self.assertEqual(draft.version, 3)

        remove_response = self.client.post(
            reverse("sales:item_remove", args=[draft.pk, item.pk]),
            {"expected_version": "3"},
        )
        draft.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(remove_response.status_code, 302)
        self.assertFalse(OrderItem.objects.filter(pk=item.pk).exists())
        self.assertEqual(draft.subtotal, Decimal("0.00"))
        self.assertEqual(draft.version, 4)
        self.assertEqual(self.product.stock_on_hand, original_stock)

    def test_foreign_and_nonexistent_drafts_are_indistinguishable_404(self):
        other_shop = Shop.objects.create(name="Other shop")
        other_terminal = Terminal.objects.create(
            shop=other_shop,
            code="TILL-1",
            name="Other checkout",
        )
        other_owner = self._user("other-owner", User.Role.OWNER, shop=other_shop)
        foreign = Order.objects.create(
            shop=other_shop,
            terminal=other_terminal,
            slot=1,
            created_by=other_owner,
            current_cashier=other_owner,
        )
        for draft_id in (foreign.pk, foreign.pk + 9999):
            with self.subTest(draft_id=draft_id):
                response = self.client.get(reverse("sales:draft_takeover", args=[draft_id]))
                self.assertEqual(response.status_code, 404)

    def test_takeover_get_is_safe_and_post_changes_handler_once(self):
        draft = self._draft()
        self.client.force_login(self.cashier)
        url = reverse("sales:draft_takeover", args=[draft.pk])

        get_response = self.client.get(url)
        draft.refresh_from_db()
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(draft.current_cashier, self.owner)
        self.assertEqual(AuditEvent.objects.count(), 0)

        post_response = self.client.post(url, {"expected_version": "1"})
        draft.refresh_from_db()
        self.assertRedirects(post_response, f"{reverse('sales:workspace')}?draft={draft.pk}")
        self.assertEqual(draft.current_cashier, self.cashier)
        self.assertEqual(draft.version, 2)
        self.assertEqual(AuditEvent.objects.get().action, AuditEvent.Action.DRAFT_TAKEN_OVER)

    def test_clear_get_is_safe_and_post_clears_same_draft(self):
        draft = self._draft()
        self._item(draft)
        draft.subtotal = Decimal("125.00")
        draft.save(update_fields=["subtotal"])
        url = reverse("sales:draft_clear", args=[draft.pk])

        get_response = self.client.get(url)
        draft.refresh_from_db()
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.context["draft"].pk, draft.pk)
        self.assertEqual(draft.status, Order.Status.DRAFT)

        response = self.client.post(url, {"expected_version": "1"})
        draft.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('sales:workspace')}?draft={draft.pk}")
        self.assertEqual(
            (draft.status, draft.subtotal, draft.version),
            (
                Order.Status.DRAFT,
                Decimal("0.00"),
                2,
            ),
        )
        self.assertFalse(draft.items.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertRedirects(
            self.client.get(url),
            f"{reverse('sales:workspace')}?draft={draft.pk}",
        )

    def test_close_empty_tab_selects_remaining_and_rejects_last(self):
        first = self._draft(slot=1)
        second = self._draft(slot=2)

        response = self.client.post(
            reverse("sales:draft_close", args=[second.pk]),
            {"expected_version": "1"},
        )

        self.assertRedirects(response, f"{reverse('sales:workspace')}?draft={first.pk}")
        self.assertFalse(Order.objects.filter(pk=second.pk).exists())
        self.assertFalse(AuditEvent.objects.exists())

        response = self.client.post(
            reverse("sales:draft_close", args=[first.pk]),
            {"expected_version": "1"},
        )
        self.assertRedirects(response, f"{reverse('sales:workspace')}?draft={first.pk}")
        self.assertTrue(Order.objects.filter(pk=first.pk).exists())

    def test_enhanced_clear_and_close_return_current_workspace_fragments(self):
        first = self._draft(slot=1)
        second = self._draft(slot=2)
        self._item(first)
        first.subtotal = Decimal("125.00")
        first.save(update_fields=["subtotal"])

        cleared = self.client.post(
            reverse("sales:draft_clear", args=[first.pk]),
            {"expected_version": "1"},
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["result"], "ok")
        self.assertEqual(cleared.json()["draft_id"], str(first.pk))
        self.assertIn("tabs", cleared.json()["tabs_html"])
        self.assertIn("panel", cleared.json()["draft_panel_html"])

        closed = self.client.post(
            reverse("sales:draft_close", args=[first.pk]),
            {"expected_version": "2"},
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["result"], "ok")
        self.assertEqual(closed.json()["draft_id"], str(second.pk))
        self.assertFalse(Order.objects.filter(pk=first.pk).exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_another_cashier_cannot_clear_or_close_without_takeover(self):
        draft = self._draft()
        second = self._draft(slot=2)
        self.client.force_login(self.cashier)

        clear_response = self.client.get(reverse("sales:draft_clear", args=[draft.pk]))
        close_response = self.client.post(
            reverse("sales:draft_close", args=[second.pk]),
            {"expected_version": "1"},
        )

        self.assertEqual(clear_response.status_code, 403)
        self.assertEqual(close_response.status_code, 403)
        draft.refresh_from_db()
        self.assertEqual(draft.status, Order.Status.DRAFT)
