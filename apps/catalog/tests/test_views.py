from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, Shop
from apps.inventory.models import InventoryMovement


class CatalogViewTests(TestCase):
    password = "StrongPass!2026"

    def setUp(self):
        self.shop = Shop.objects.create(name="Test Shop")
        self.owner = self._user("owner", User.Role.OWNER)
        self.admin = self._user("admin", User.Role.ADMIN)
        self.cashier = self._user("cashier", User.Role.CASHIER)
        self.product = self._product()
        self.other_shop = Shop.objects.create(name="Other Shop")
        self.other_owner = self._user("other-owner", User.Role.OWNER, shop=self.other_shop)
        self.foreign_product = self._product(
            shop=self.other_shop,
            created_by=self.other_owner,
            name="Foreign product",
            barcode="999",
            sku="FOREIGN",
        )

    def _user(self, username, role, *, shop=None):
        return User.objects.create_user(
            username=username,
            password=self.password,
            shop=shop or self.shop,
            role=role,
        )

    def _product(self, **overrides):
        values = {
            "shop": self.shop,
            "name": "Rice",
            "barcode": "00123",
            "sku": "RICE-1",
            "selling_price": "120.00",
            "cost_price": "100.00",
            "created_by": self.owner,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_anonymous_redirects_and_cashier_can_browse_but_not_create(self):
        list_url = reverse("catalog:product_list")
        self.assertRedirects(
            self.client.get(list_url),
            f"{reverse('accounts:login')}?next={list_url}",
        )
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(list_url).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("catalog:product_detail", args=[self.product.pk])).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse("catalog:product_create")).status_code, 403)

    def test_foreign_shop_product_is_not_disclosed(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("catalog:product_detail", args=[self.foreign_product.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_list_search_filters_and_excludes_foreign_shop(self):
        negative = self._product(
            name="Damaged Rice",
            barcode="00200",
            sku="DAMAGED",
            stock_on_hand=-2,
            needs_review=True,
        )
        self._product(
            name="Inactive Rice",
            barcode="00300",
            sku="INACTIVE",
            is_active=False,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("catalog:product_list"),
            {"q": "rice", "status": "active", "negative": "on", "needs_review": "on"},
        )

        self.assertQuerySetEqual(response.context["products"], [negative])
        self.assertNotContains(response, self.foreign_product.name)

    def test_list_is_stably_sorted_and_paginated_at_fifty(self):
        for index in range(51):
            self._product(
                name=f"Product {index:02d}",
                barcode=f"8{index:04d}",
                sku=f"SKU-{index:02d}",
            )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("catalog:product_list"), {"q": "Product"})

        self.assertEqual(response.context["page_obj"].paginator.per_page, 50)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertContains(response, "q=Product&amp;page=2")

    def test_create_uses_server_controlled_metadata_and_prefill(self):
        self.client.force_login(self.admin)
        get_response = self.client.get(reverse("catalog:product_create"), {"barcode": "0012345"})
        self.assertContains(get_response, 'value="0012345"')

        response = self.client.post(
            reverse("catalog:product_create"),
            {
                "name": "Flour",
                "barcode": "0012345",
                "sku": "FL-1",
                "selling_price": "200.00",
                "cost_price": "180.00",
                "stock_on_hand": "999",
                "shop": self.other_shop.pk,
                "needs_review": "on",
                "is_active": "",
            },
        )

        created = Product.objects.get(name="Flour")
        self.assertRedirects(response, reverse("catalog:product_detail", args=[created.pk]))
        self.assertEqual(created.barcode, "0012345")
        self.assertEqual(created.shop, self.shop)
        self.assertEqual(created.created_by, self.admin)
        self.assertEqual(created.stock_on_hand, 0)
        self.assertFalse(created.needs_review)
        self.assertTrue(created.is_active)

    def test_duplicate_create_returns_field_error_without_partial_write(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("catalog:product_create"),
            {
                "name": "Duplicate",
                "barcode": self.product.barcode,
                "sku": "NEW-SKU",
                "selling_price": "10.00",
                "cost_price": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A product with this barcode already exists")
        self.assertEqual(Product.objects.filter(shop=self.shop).count(), 1)

    def test_edit_changes_price_and_writes_audit(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("catalog:product_edit", args=[self.product.pk]),
            {
                "name": "Premium rice",
                "barcode": self.product.barcode,
                "sku": self.product.sku,
                "selling_price": "150.00",
                "cost_price": "100.00",
                "stock_on_hand": "500",
            },
        )

        self.assertRedirects(response, reverse("catalog:product_detail", args=[self.product.pk]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Premium rice")
        self.assertEqual(self.product.stock_on_hand, 0)
        self.assertEqual(AuditEvent.objects.get().action, AuditEvent.Action.PRODUCT_PRICE_CHANGED)

    def test_status_requires_confirmation_and_post_without_stock_change(self):
        self.product.stock_on_hand = -2
        self.product.save(update_fields=["stock_on_hand"])
        self.client.force_login(self.admin)
        url = reverse("catalog:product_status", args=[self.product.pk])

        get_response = self.client.get(url)
        self.product.refresh_from_db()
        self.assertEqual(get_response.status_code, 200)
        self.assertTrue(self.product.is_active)

        response = self.client.post(url)
        self.assertRedirects(response, reverse("catalog:product_detail", args=[self.product.pk]))
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)
        self.assertEqual(self.product.stock_on_hand, -2)
        self.assertFalse(self.product.movements.exists())

    def test_review_is_post_only_and_preserves_creation_metadata(self):
        self.product.needs_review = True
        self.product.creation_source = Product.CreationSource.POS_QUICK_CREATE
        self.product.save(update_fields=["needs_review", "creation_source"])
        creator_id = self.product.created_by_id
        self.client.force_login(self.admin)
        url = reverse("catalog:product_review", args=[self.product.pk])

        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)

        self.assertRedirects(response, reverse("catalog:product_detail", args=[self.product.pk]))
        self.product.refresh_from_db()
        self.assertFalse(self.product.needs_review)
        self.assertEqual(self.product.created_by_id, creator_id)
        self.assertEqual(self.product.creation_source, Product.CreationSource.POS_QUICK_CREATE)

    def test_modal_create_can_atomically_receive_stock(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("catalog:product_create"),
            {
                "name": "Flour",
                "barcode": "00888",
                "sku": "FL-8",
                "selling_price": "200.00",
                "cost_price": "180.00",
                "quantity_received_now": "12",
                "receipt_note": "Opening count",
            },
            headers={"X-Product-Workspace": "modal"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], "ok")
        product = Product.objects.get(barcode="00888")
        movement = InventoryMovement.objects.get(product=product)
        self.assertEqual(product.stock_on_hand, 12)
        self.assertEqual(movement.quantity_change, 12)

    def test_lookup_prioritizes_exact_barcode_and_unknown_only_filters(self):
        self.client.force_login(self.admin)
        lookup_url = reverse("catalog:product_lookup")
        exact = self.client.get(
            lookup_url,
            {"q": "00123"},
            headers={"X-Product-Workspace": "lookup"},
        )
        self.assertEqual(exact.json()["result"], "modal")
        self.assertEqual(exact.json()["url"], reverse("inventory:receive", args=[self.product.pk]))

        unknown = self.client.get(
            lookup_url,
            {"q": "00000"},
            headers={"X-Product-Workspace": "lookup"},
        )
        self.assertEqual(unknown.json()["result"], "search")
        self.assertIn("q=00000", unknown.json()["url"])
        self.assertEqual(Product.objects.filter(shop=self.shop).count(), 1)

        self.client.force_login(self.cashier)
        cashier_exact = self.client.get(
            lookup_url,
            {"q": "00123"},
            headers={"X-Product-Workspace": "lookup"},
        )
        self.assertEqual(
            cashier_exact.json()["url"],
            reverse("catalog:product_detail", args=[self.product.pk]),
        )

    def test_results_fragment_and_modal_detail_are_role_safe(self):
        self.client.force_login(self.admin)
        fragment = self.client.get(
            reverse("catalog:product_list"),
            {"q": "Rice"},
            headers={"X-Product-Workspace": "results"},
        )
        self.assertEqual(fragment.status_code, 200)
        self.assertContains(fragment, self.product.name)
        self.assertNotContains(fragment, "<html")

        detail = self.client.get(
            reverse("catalog:product_detail", args=[self.product.pk]),
            headers={"X-Product-Workspace": "modal"},
        )
        self.assertIn("Cost price", detail.json()["dialog_html"])

        self.client.force_login(self.cashier)
        cashier_detail = self.client.get(
            reverse("catalog:product_detail", args=[self.product.pk]),
            headers={"X-Product-Workspace": "modal"},
        )
        self.assertNotIn("Cost price", cashier_detail.json()["dialog_html"])
        self.assertNotIn("Receive stock", cashier_detail.json()["dialog_html"])

    def test_invalid_modal_create_returns_422_with_form_values(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("catalog:product_create"),
            {
                "name": "Invalid receipt",
                "barcode": "00999",
                "sku": "",
                "selling_price": "20.00",
                "cost_price": "",
                "quantity_received_now": "0",
                "receipt_note": "",
            },
            headers={"X-Product-Workspace": "modal"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["result"], "invalid")
        self.assertIn("Invalid receipt", response.json()["dialog_html"])
        self.assertFalse(Product.objects.filter(barcode="00999").exists())

    def test_modal_edit_status_and_review_mutate_once_without_stock_change(self):
        self.product.stock_on_hand = 6
        self.product.needs_review = True
        self.product.save(update_fields=["stock_on_hand", "needs_review"])
        self.client.force_login(self.admin)
        headers = {"X-Product-Workspace": "modal"}

        edit = self.client.post(
            reverse("catalog:product_edit", args=[self.product.pk]),
            {
                "name": "Updated rice",
                "barcode": self.product.barcode,
                "sku": self.product.sku,
                "selling_price": "125.00",
                "cost_price": "100.00",
            },
            headers=headers,
        )
        self.assertEqual(edit.json()["result"], "ok")

        status = self.client.post(
            reverse("catalog:product_status", args=[self.product.pk]),
            headers=headers,
        )
        self.assertEqual(status.json()["result"], "ok")

        review = self.client.post(
            reverse("catalog:product_review", args=[self.product.pk]),
            headers=headers,
        )
        self.assertEqual(review.json()["result"], "ok")
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Updated rice")
        self.assertEqual(self.product.stock_on_hand, 6)
        self.assertFalse(self.product.is_active)
        self.assertFalse(self.product.needs_review)
        self.assertFalse(self.product.movements.exists())
