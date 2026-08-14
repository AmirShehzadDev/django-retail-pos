from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, Shop
from apps.inventory.models import InventoryMovement


class CashierReadOnlyCatalogTests(TestCase):
    password = "StrongPass!2026"

    def setUp(self):
        self.shop = Shop.objects.create(name="Cashier Catalogue Shop")
        self.owner = self._user("sensitive-creator", User.Role.OWNER)
        self.admin = self._user("catalog-admin", User.Role.ADMIN)
        self.cashier = self._user("catalog-cashier", User.Role.CASHIER)
        self.product = Product.objects.create(
            shop=self.shop,
            name="Leading Zero Tea",
            barcode="0012345",
            sku="TEA-SAFE",
            selling_price=Decimal("125.25"),
            cost_price=Decimal("73.41"),
            stock_on_hand=-3,
            created_by=self.owner,
            creation_source=Product.CreationSource.POS_QUICK_CREATE,
            needs_review=True,
        )
        self.movement = InventoryMovement.objects.create(
            shop=self.shop,
            product=self.product,
            movement_type=InventoryMovement.MovementType.ADJUSTMENT,
            quantity_change=-3,
            balance_after=-3,
            actor=self.admin,
            reason="SENSITIVE-MOVEMENT-REASON",
        )
        self.other_shop = Shop.objects.create(name="Foreign Catalogue Shop")
        self.other_owner = self._user("foreign-owner", User.Role.OWNER, shop=self.other_shop)
        self.foreign_product = Product.objects.create(
            shop=self.other_shop,
            name="FOREIGN-SENTINEL-PRODUCT",
            barcode="0099999",
            selling_price=Decimal("999.00"),
            created_by=self.other_owner,
        )
        self.client.force_login(self.cashier)

    def _user(self, username, role, *, shop=None, active=True):
        return User.objects.create_user(
            username=username,
            password=self.password,
            shop=shop or self.shop,
            role=role,
            is_active=active,
        )

    def _state_snapshot(self):
        return {
            "products": list(
                Product.objects.order_by("pk").values(
                    "pk",
                    "name",
                    "barcode",
                    "sku",
                    "selling_price",
                    "cost_price",
                    "stock_on_hand",
                    "is_active",
                    "needs_review",
                )
            ),
            "movements": list(
                InventoryMovement.objects.order_by("pk").values(
                    "pk", "product_id", "quantity_change", "balance_after", "reason"
                )
            ),
            "audits": list(AuditEvent.objects.order_by("pk").values()),
        }

    def test_cashier_list_has_safe_fields_filters_and_no_manager_review_surface(self):
        response = self.client.get(
            reverse("catalog:product_list"),
            {
                "q": "0012345",
                "status": "active",
                "negative": "on",
                "needs_review": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(response.context["products"], [self.product])
        self.assertFalse(response.context["is_catalog_manager"])
        self.assertFalse(response.context["needs_review"])
        self.assertNotIn("needs_review", response.context["query_string"])
        for visible in (
            self.product.name,
            self.product.barcode,
            self.product.sku,
            "PKR 125.25",
            "-3",
            "Active",
            "Stock is informational",
            "View",
        ):
            with self.subTest(visible=visible):
                self.assertContains(response, visible)
        for hidden in (
            "Create product",
            "Needs review",
            "73.41",
            self.owner.username,
            "SENSITIVE-MOVEMENT-REASON",
            reverse("catalog:product_create"),
            reverse("inventory:scan"),
        ):
            with self.subTest(hidden=hidden):
                self.assertNotContains(response, hidden)

    def test_cashier_searches_name_barcode_and_sku_and_filters_inactive(self):
        inactive = Product.objects.create(
            shop=self.shop,
            name="Inactive Flour",
            barcode=None,
            sku=None,
            selling_price=Decimal("80.00"),
            stock_on_hand=2,
            is_active=False,
            created_by=self.admin,
        )

        for query in ("leading zero", "0012345", "tea-safe"):
            with self.subTest(query=query):
                response = self.client.get(reverse("catalog:product_list"), {"q": query})
                self.assertQuerySetEqual(response.context["products"], [self.product])

        inactive_response = self.client.get(
            reverse("catalog:product_list"),
            {"status": "inactive"},
        )
        self.assertQuerySetEqual(inactive_response.context["products"], [inactive])
        self.assertContains(inactive_response, "No barcode")
        self.assertContains(inactive_response, "Inactive")

        invalid_filter = self.client.get(
            reverse("catalog:product_list"),
            {"q": "no product has this value", "status": "crafted-status"},
        )
        self.assertEqual(invalid_filter.status_code, 200)
        self.assertFalse(invalid_filter.context["products"])
        self.assertContains(invalid_filter, "No products match these filters.")

    def test_cashier_pagination_preserves_only_permitted_filters(self):
        for index in range(51):
            Product.objects.create(
                shop=self.shop,
                name=f"Paged Product {index:02d}",
                barcode=f"8{index:05d}",
                selling_price=Decimal("1.00"),
                created_by=self.admin,
            )

        response = self.client.get(
            reverse("catalog:product_list"),
            {"q": "Paged", "status": "active", "needs_review": "on"},
        )

        self.assertEqual(response.context["page_obj"].paginator.per_page, 50)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertContains(response, "q=Paged&amp;status=active&amp;page=2")
        self.assertNotContains(response, "needs_review=on")

    def test_cashier_detail_is_safe_and_inactive_guidance_is_present(self):
        response = self.client.get(reverse("catalog:product_detail", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalog/product_detail_readonly.html")
        for visible in (
            self.product.name,
            self.product.barcode,
            self.product.sku,
            "PKR 125.25",
            "-3",
            "Stock is informational and may change before checkout.",
        ):
            with self.subTest(visible=visible):
                self.assertContains(response, visible)
        for hidden in (
            "Cost price",
            "73.41",
            self.owner.username,
            "POS quick create",
            "Needs review",
            "Created",
            "Last updated",
            "Recent stock movements",
            "SENSITIVE-MOVEMENT-REASON",
            reverse("catalog:product_edit", args=[self.product.pk]),
            reverse("catalog:product_status", args=[self.product.pk]),
            reverse("catalog:product_review", args=[self.product.pk]),
            reverse("inventory:receive", args=[self.product.pk]),
            reverse("inventory:adjust", args=[self.product.pk]),
            reverse("inventory:movement_list"),
        ):
            with self.subTest(hidden=hidden):
                self.assertNotContains(response, hidden)

        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        inactive = self.client.get(reverse("catalog:product_detail", args=[self.product.pk]))
        self.assertContains(inactive, "This product cannot be added to a new order.")

    def test_foreign_and_missing_product_details_share_not_found_boundary(self):
        foreign = self.client.get(reverse("catalog:product_detail", args=[self.foreign_product.pk]))
        missing = self.client.get(
            reverse("catalog:product_detail", args=[self.foreign_product.pk + 10000])
        )

        self.assertEqual((foreign.status_code, missing.status_code), (404, 404))
        self.assertNotContains(foreign, self.foreign_product.name, status_code=404)

    def test_inactive_cashier_cannot_open_catalogue(self):
        inactive = self._user("inactive-cashier", User.Role.CASHIER, active=False)
        self.client.force_login(inactive)

        response = self.client.get(reverse("catalog:product_list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_cashier_catalog_and_inventory_mutations_are_denied_without_side_effects(self):
        before = self._state_snapshot()
        requests = (
            ("get", reverse("catalog:product_create"), None, 403),
            ("post", reverse("catalog:product_create"), {"name": "Forbidden"}, 403),
            ("get", reverse("catalog:product_edit", args=[self.product.pk]), None, 403),
            ("post", reverse("catalog:product_edit", args=[self.product.pk]), {}, 403),
            ("get", reverse("catalog:product_status", args=[self.product.pk]), None, 403),
            ("post", reverse("catalog:product_status", args=[self.product.pk]), {}, 403),
            ("get", reverse("catalog:product_review", args=[self.product.pk]), None, 405),
            ("post", reverse("catalog:product_review", args=[self.product.pk]), {}, 403),
            ("get", reverse("inventory:scan"), None, 403),
            ("get", reverse("inventory:receive", args=[self.product.pk]), None, 403),
            ("post", reverse("inventory:receive", args=[self.product.pk]), {}, 403),
            ("get", reverse("inventory:adjust", args=[self.product.pk]), None, 403),
            ("post", reverse("inventory:adjust", args=[self.product.pk]), {}, 403),
            ("get", reverse("inventory:movement_list"), None, 403),
        )

        for method, url, data, expected in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data or {})
                self.assertEqual(response.status_code, expected)
                self.assertEqual(self._state_snapshot(), before)

    def test_owner_and_admin_keep_manager_catalog_detail(self):
        for actor in (self.owner, self.admin):
            with self.subTest(role=actor.role):
                self.client.force_login(actor)
                list_response = self.client.get(reverse("catalog:product_list"))
                detail = self.client.get(reverse("catalog:product_detail", args=[self.product.pk]))
                self.assertTrue(list_response.context["is_catalog_manager"])
                self.assertContains(list_response, "Create product")
                self.assertContains(list_response, "Needs review")
                self.assertTemplateUsed(detail, "catalog/product_detail.html")
                self.assertContains(detail, "Cost price")
                self.assertContains(detail, "73.41")
                self.assertContains(detail, "Recent stock movements")
                self.assertContains(detail, "SENSITIVE-MOVEMENT-REASON")
