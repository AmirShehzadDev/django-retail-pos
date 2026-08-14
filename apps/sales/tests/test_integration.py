"""M3-15 cross-cutting acceptance and regression coverage.

Named traceability:

* AC 1-2: complete POS URL actor, CSRF, and shop/terminal scope matrices.
* AC 3, 5, 7, 9, 13, 16, 18: each POS role exercises the complete web surface.
* AC 4, 16-17: three drafts survive logout, a new client, and a DB reconnect.
* AC 6, 9-10, 15: session-bound quick-create is secret, single-use, and reviewable.
* AC 20: enhanced responses preserve identifiers and versions above JS safe integer.
* AC 22: production database failures are safe and M2 catalog/inventory boundaries regress cleanly.

The remaining acceptance criteria have focused coverage in the model, service, concurrency,
view, and UI modules, or are required M3-18 physical-scanner/offline checks.
"""

from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.db import DatabaseError, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, Shop, Terminal
from apps.inventory.models import InventoryMovement
from apps.sales.models import Order, OrderItem

PASSWORD = "StrongPass!2026"
JS_MAX_SAFE_INTEGER = 9_007_199_254_740_991


class PosIntegrationFixtureMixin:
    def make_scope(self, suffix, role=User.Role.OWNER, *, active=True):
        shop = Shop.objects.create(name=f"Integration shop {suffix}")
        terminal = Terminal.objects.create(
            shop=shop,
            code="TILL-1",
            name=f"Checkout {suffix}",
        )
        actor = User.objects.create_user(
            username=f"actor-{suffix}",
            password=PASSWORD,
            shop=shop,
            role=role,
            is_active=active,
        )
        product = Product.objects.create(
            shop=shop,
            barcode=f"000-{suffix}",
            sku=f"SKU-{suffix}",
            name=f"Product {suffix}",
            selling_price=Decimal("12.50"),
            stock_on_hand=-2,
            created_by=actor,
        )
        return shop, terminal, actor, product

    @staticmethod
    def make_draft(shop, terminal, actor, *, slot=1, order_id=None, version=1):
        return Order.objects.create(
            id=order_id,
            shop=shop,
            terminal=terminal,
            slot=slot,
            created_by=actor,
            current_cashier=actor,
            version=version,
        )

    @staticmethod
    def make_item(draft, product, *, quantity=1):
        line_total = product.selling_price * quantity
        draft.subtotal = line_total
        draft.save(update_fields=["subtotal"])
        return OrderItem.objects.create(
            order=draft,
            product=product,
            product_name=product.name,
            product_barcode=product.barcode,
            unit_price=product.selling_price,
            quantity=quantity,
            line_total=line_total,
        )

    @staticmethod
    def quick_create_token(client, draft, barcode):
        response = client.post(
            reverse("sales:draft_scan", args=[draft.pk]),
            {"barcode": barcode, "expected_version": str(draft.version)},
        )
        return parse_qs(urlparse(response.url).query)["context"][0], response.url


@override_settings(POS_TERMINAL_CODE="TILL-1")
class PosWebSecurityIntegrationTests(PosIntegrationFixtureMixin, TestCase):
    def setUp(self):
        self.shop, self.terminal, self.owner, self.product = self.make_scope("security")
        self.draft = self.make_draft(self.shop, self.terminal, self.owner)
        self.item = self.make_item(self.draft, self.product)

    def pos_surface(self, draft=None, item=None):
        draft = draft or self.draft
        item = item or self.item
        return (
            ("get", reverse("sales:workspace")),
            ("post", reverse("sales:start_workspace")),
            ("post", reverse("sales:draft_create")),
            ("post", reverse("sales:draft_scan", args=[draft.pk])),
            ("post", reverse("sales:draft_add_product", args=[draft.pk])),
            ("get", reverse("sales:quick_create", args=[draft.pk])),
            ("post", reverse("sales:item_quantity", args=[draft.pk, item.pk])),
            ("post", reverse("sales:item_remove", args=[draft.pk, item.pk])),
            ("get", reverse("sales:draft_takeover", args=[draft.pk])),
            ("get", reverse("sales:draft_clear", args=[draft.pk])),
            ("post", reverse("sales:draft_close", args=[draft.pk])),
        )

    def test_acceptance_01_anonymous_and_inactive_users_cannot_open_any_pos_url(self):
        anonymous = Client()
        for method, url in self.pos_surface():
            with self.subTest(actor="anonymous", method=method, url=url):
                response = getattr(anonymous, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlparse(response.url).path, reverse("accounts:login"))

        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        inactive = Client()
        inactive.force_login(self.owner)
        for method, url in self.pos_surface():
            with self.subTest(actor="inactive", method=method, url=url):
                response = getattr(inactive, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlparse(response.url).path, reverse("accounts:login"))

    def test_acceptance_01_all_mutation_urls_enforce_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        urls = (
            reverse("sales:start_workspace"),
            reverse("sales:draft_create"),
            reverse("sales:draft_scan", args=[self.draft.pk]),
            reverse("sales:draft_add_product", args=[self.draft.pk]),
            reverse("sales:quick_create", args=[self.draft.pk]),
            reverse("sales:item_quantity", args=[self.draft.pk, self.item.pk]),
            reverse("sales:item_remove", args=[self.draft.pk, self.item.pk]),
            reverse("sales:draft_takeover", args=[self.draft.pk]),
            reverse("sales:draft_clear", args=[self.draft.pk]),
            reverse("sales:draft_close", args=[self.draft.pk]),
        )

        before = (
            Order.objects.count(),
            OrderItem.objects.count(),
            Product.objects.count(),
            AuditEvent.objects.count(),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(
            before,
            (
                Order.objects.count(),
                OrderItem.objects.count(),
                Product.objects.count(),
                AuditEvent.objects.count(),
            ),
        )

    def test_acceptance_02_foreign_and_nonexistent_ids_share_the_same_404_boundary(self):
        foreign_shop, foreign_terminal, foreign_actor, foreign_product = self.make_scope("foreign")
        foreign_draft = self.make_draft(foreign_shop, foreign_terminal, foreign_actor)
        foreign_item = self.make_item(foreign_draft, foreign_product)
        client = Client()
        client.force_login(self.owner)
        token, _ = self.quick_create_token(client, self.draft, "009999")

        foreign_requests = (
            ("post", reverse("sales:draft_scan", args=[foreign_draft.pk]), {}),
            ("post", reverse("sales:draft_add_product", args=[foreign_draft.pk]), {}),
            (
                "get",
                reverse("sales:quick_create", args=[foreign_draft.pk]),
                {"context": token},
            ),
            (
                "post",
                reverse("sales:item_quantity", args=[foreign_draft.pk, foreign_item.pk]),
                {},
            ),
            (
                "post",
                reverse("sales:item_remove", args=[foreign_draft.pk, foreign_item.pk]),
                {},
            ),
            ("get", reverse("sales:draft_takeover", args=[foreign_draft.pk]), {}),
            ("get", reverse("sales:draft_clear", args=[foreign_draft.pk]), {}),
            ("post", reverse("sales:draft_close", args=[foreign_draft.pk]), {}),
        )
        missing_id = foreign_draft.pk + 1_000_000
        for method, foreign_url, data in foreign_requests:
            missing_url = foreign_url.replace(str(foreign_draft.pk), str(missing_id), 1)
            with self.subTest(method=method, url=foreign_url):
                foreign_response = getattr(client, method)(foreign_url, data)
                missing_response = getattr(client, method)(missing_url, data)
                self.assertEqual(foreign_response.status_code, 404)
                self.assertEqual(missing_response.status_code, 404)
                self.assertEqual(foreign_response.content, missing_response.content)

        cross_shop_product = client.post(
            reverse("sales:draft_add_product", args=[self.draft.pk]),
            {"product_id": foreign_product.pk, "expected_version": self.draft.version},
        )
        cross_shop_item = client.post(
            reverse("sales:item_remove", args=[self.draft.pk, foreign_item.pk]),
            {"expected_version": self.draft.version},
        )
        self.assertEqual(cross_shop_product.status_code, 404)
        self.assertEqual(cross_shop_item.status_code, 404)

    def test_acceptance_01_all_sales_roles_can_complete_every_pos_web_flow(self):
        for role in (User.Role.OWNER, User.Role.ADMIN, User.Role.CASHIER):
            suffix = role.lower()
            shop, terminal, actor, product = self.make_scope(suffix, role)
            other_cashier = User.objects.create_user(
                username=f"other-{suffix}",
                password=PASSWORD,
                shop=shop,
                role=User.Role.CASHIER,
            )
            client = Client()
            client.force_login(actor)

            with self.subTest(role=role, step="workspace/start"):
                self.assertEqual(client.get(reverse("sales:workspace")).status_code, 200)
                self.assertEqual(client.post(reverse("sales:start_workspace")).status_code, 302)
            draft = Order.objects.get(shop=shop, slot=1, status=Order.Status.DRAFT)

            with self.subTest(role=role, step="scan/search add"):
                self.assertEqual(
                    client.post(
                        reverse("sales:draft_scan", args=[draft.pk]),
                        {"barcode": product.barcode, "expected_version": "1"},
                    ).status_code,
                    302,
                )
                draft.refresh_from_db()
                self.assertEqual(
                    client.post(
                        reverse("sales:draft_add_product", args=[draft.pk]),
                        {"product_id": product.pk, "expected_version": draft.version},
                    ).status_code,
                    302,
                )
            draft.refresh_from_db()
            item = draft.items.get()

            with self.subTest(role=role, step="quantity/remove"):
                self.assertEqual(
                    client.post(
                        reverse("sales:item_quantity", args=[draft.pk, item.pk]),
                        {"quantity": "3", "expected_version": draft.version},
                    ).status_code,
                    302,
                )
                draft.refresh_from_db()
                self.assertEqual(
                    client.post(
                        reverse("sales:item_remove", args=[draft.pk, item.pk]),
                        {"expected_version": draft.version},
                    ).status_code,
                    302,
                )

            draft.refresh_from_db()
            token, quick_url = self.quick_create_token(client, draft, f"009-{suffix}")
            with self.subTest(role=role, step="quick create"):
                self.assertEqual(client.get(quick_url).status_code, 200)
                self.assertEqual(
                    client.post(
                        reverse("sales:quick_create", args=[draft.pk]),
                        {
                            "context": token,
                            "name": f"Quick {role}",
                            "selling_price": "3.25",
                        },
                    ).status_code,
                    302,
                )

            with self.subTest(role=role, step="new/takeover/clear/close"):
                self.assertEqual(client.post(reverse("sales:draft_create")).status_code, 302)
                handoff = Order.objects.get(shop=shop, slot=2, status=Order.Status.DRAFT)
                handoff.current_cashier = other_cashier
                handoff.save(update_fields=["current_cashier"])
                takeover_url = reverse("sales:draft_takeover", args=[handoff.pk])
                self.assertEqual(client.get(takeover_url).status_code, 200)
                self.assertEqual(
                    client.post(takeover_url, {"expected_version": handoff.version}).status_code,
                    302,
                )
                draft.refresh_from_db()
                clear_url = reverse("sales:draft_clear", args=[draft.pk])
                self.assertEqual(client.get(clear_url).status_code, 200)
                self.assertEqual(
                    client.post(clear_url, {"expected_version": draft.version}).status_code,
                    302,
                )
                handoff.refresh_from_db()
                self.assertEqual(
                    client.post(
                        reverse("sales:draft_close", args=[handoff.pk]),
                        {"expected_version": handoff.version},
                    ).status_code,
                    302,
                )

            self.assertFalse(
                Product.objects.filter(shop=shop).exclude(stock_on_hand__in=(-2, 0)).exists()
            )
            self.assertFalse(InventoryMovement.objects.filter(shop=shop).exists())

    def test_acceptance_06_09_10_session_token_is_secret_single_use_and_reviewable(self):
        cashier = User.objects.create_user(
            username="security-cashier",
            password=PASSWORD,
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.draft.current_cashier = cashier
        self.draft.save(update_fields=["current_cashier"])
        self.item.delete()
        self.draft.subtotal = Decimal("0.00")
        self.draft.save(update_fields=["subtotal"])

        cashier_client = Client()
        cashier_client.force_login(cashier)
        raw_session_key = cashier_client.session.session_key
        token, quick_url = self.quick_create_token(cashier_client, self.draft, "001-SECRET")
        page = cashier_client.get(quick_url)
        self.assertNotIn(raw_session_key, token)
        self.assertNotIn(raw_session_key.encode(), page.content)

        second_browser = Client()
        second_browser.force_login(cashier)
        copied = second_browser.post(
            reverse("sales:quick_create", args=[self.draft.pk]),
            {"context": token, "name": "Copied", "selling_price": "1.00"},
        )
        self.assertEqual(copied.status_code, 302)
        self.assertFalse(Product.objects.filter(barcode="001-SECRET").exists())

        success = cashier_client.post(
            reverse("sales:quick_create", args=[self.draft.pk]),
            {"context": token, "name": "Secure quick product", "selling_price": "7.00"},
        )
        self.assertEqual(success.status_code, 302)
        created = Product.objects.get(barcode="001-SECRET")
        event = AuditEvent.objects.get(action=AuditEvent.Action.PRODUCT_QUICK_CREATED)
        self.assertTrue(created.needs_review)
        self.assertEqual(created.stock_on_hand, 0)
        self.assertFalse(created.movements.exists())
        self.assertNotIn(raw_session_key, str(event.before_values) + str(event.after_values))

        replay = cashier_client.post(
            reverse("sales:quick_create", args=[self.draft.pk]),
            {"context": token, "name": "Replay", "selling_price": "8.00"},
        )
        self.assertEqual(replay.status_code, 302)
        self.assertEqual(Product.objects.filter(barcode="001-SECRET").count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action=event.action).count(), 1)

        owner_client = Client()
        owner_client.force_login(self.owner)
        review_list = owner_client.get(reverse("catalog:product_list"), {"needs_review": "on"})
        self.assertContains(review_list, created.name)
        cashier_catalog = cashier_client.get(reverse("catalog:product_list"))
        self.assertEqual(cashier_catalog.status_code, 200)
        self.assertContains(cashier_catalog, created.name)
        self.assertNotContains(cashier_catalog, "Needs review")

    def test_acceptance_20_enhanced_bigint_transport_is_exact_decimal_text(self):
        self.item.delete()
        self.draft.delete()
        huge = JS_MAX_SAFE_INTEGER + 2
        draft = self.make_draft(
            self.shop,
            self.terminal,
            self.owner,
            order_id=huge,
            version=huge,
        )
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            reverse("sales:draft_scan", args=[draft.pk]),
            {"barcode": self.product.barcode, "expected_version": str(huge)},
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["draft_id"], str(huge))
        self.assertEqual(response.json()["version"], str(huge + 1))
        self.assertIsInstance(response.json()["draft_id"], str)
        self.assertIsInstance(response.json()["version"], str)

        draft.refresh_from_db()
        token, _ = self.quick_create_token(client, draft, "BIG-ID-WINNER")
        winner = Product.objects.create(
            id=huge + 10,
            shop=self.shop,
            barcode="BIG-ID-WINNER",
            name="Large identifier winner",
            selling_price=Decimal("1.00"),
            created_by=self.owner,
        )
        conflict = client.post(
            reverse("sales:quick_create", args=[draft.pk]),
            {"context": token, "name": "Loser", "selling_price": "1.00"},
            HTTP_X_POS_ENHANCED="1",
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["known_product_id"], str(winner.pk))
        self.assertIsInstance(conflict.json()["known_product_id"], str)

    @override_settings(DEBUG=False)
    def test_acceptance_22_production_database_failure_exposes_no_traceback_or_detail(self):
        client = Client()
        client.force_login(self.owner)
        secret = "sensitive SQL detail"

        with patch("apps.sales.views.start_workspace", side_effect=DatabaseError(secret)):
            normal = client.post(reverse("sales:start_workspace"))
            enhanced = client.post(
                reverse("sales:start_workspace"),
                HTTP_X_POS_ENHANCED="1",
            )

        self.assertEqual(normal.status_code, 503)
        self.assertEqual(enhanced.status_code, 503)
        self.assertNotContains(normal, secret, status_code=503)
        self.assertNotIn(secret, enhanced.content.decode())
        self.assertNotIn("Traceback", normal.content.decode())
        self.assertNotIn("Traceback", enhanced.content.decode())


@override_settings(POS_TERMINAL_CODE="TILL-1")
class PosPersistenceIntegrationTests(PosIntegrationFixtureMixin, TransactionTestCase):
    reset_sequences = True

    def test_acceptance_04_16_17_three_drafts_survive_logout_new_client_and_reconnect(self):
        shop, terminal, owner, _ = self.make_scope("persistence")
        cashier = User.objects.create_user(
            username="persistence-cashier",
            password=PASSWORD,
            shop=shop,
            role=User.Role.CASHIER,
        )
        products = [
            Product.objects.create(
                shop=shop,
                barcode=f"PERSIST-00{slot}",
                name=f"Persistent product {slot}",
                selling_price=Decimal(f"{slot}.25"),
                created_by=owner,
            )
            for slot in (1, 2, 3)
        ]
        owner_client = Client()
        owner_client.force_login(owner)
        self.assertEqual(owner_client.post(reverse("sales:start_workspace")).status_code, 302)

        for slot, product in enumerate(products, start=1):
            if slot > 1:
                self.assertEqual(
                    owner_client.post(reverse("sales:draft_create")).status_code,
                    302,
                )
            draft = Order.objects.get(shop=shop, slot=slot, status=Order.Status.DRAFT)
            self.assertEqual(
                owner_client.post(
                    reverse("sales:draft_scan", args=[draft.pk]),
                    {"barcode": product.barcode, "expected_version": draft.version},
                ).status_code,
                302,
            )

        self.assertEqual(owner_client.post(reverse("accounts:logout")).status_code, 302)
        connection.close()

        cashier_client = Client()
        cashier_client.force_login(cashier)
        workspace = cashier_client.get(reverse("sales:workspace"))
        self.assertEqual(workspace.status_code, 200)
        self.assertEqual(len(workspace.context["drafts"]), 3)
        self.assertEqual(AuditEvent.objects.count(), 0)

        persisted = list(
            Order.objects.filter(shop=shop, status=Order.Status.DRAFT)
            .prefetch_related("items")
            .order_by("slot")
        )
        self.assertEqual([draft.slot for draft in persisted], [1, 2, 3])
        self.assertEqual(
            [draft.items.get().product_barcode for draft in persisted],
            [product.barcode for product in products],
        )
        self.assertEqual(
            [draft.subtotal for draft in persisted],
            [Decimal("1.25"), Decimal("2.25"), Decimal("3.25")],
        )
        self.assertTrue(all(draft.created_by_id == owner.pk for draft in persisted))
        self.assertTrue(all(draft.current_cashier_id == owner.pk for draft in persisted))

        selected = persisted[1]
        takeover = cashier_client.post(
            reverse("sales:draft_takeover", args=[selected.pk]),
            {"expected_version": selected.version},
        )
        self.assertEqual(takeover.status_code, 302)
        connection.close()
        selected.refresh_from_db()
        self.assertEqual(selected.created_by_id, owner.pk)
        self.assertEqual(selected.current_cashier_id, cashier.pk)
        self.assertEqual(selected.items.get().product_barcode, products[1].barcode)
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditEvent.Action.DRAFT_TAKEN_OVER).count(),
            1,
        )
        self.assertFalse(InventoryMovement.objects.filter(shop=shop).exists())
