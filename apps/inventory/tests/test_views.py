from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import Shop
from apps.inventory.models import InventoryMovement


class InventoryViewTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Main Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.ADMIN,
            created_by=self.owner,
        )
        self.cashier = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
            created_by=self.owner,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            barcode="0012345",
            sku="TEA-1",
            name="Tea",
            selling_price=Decimal("250.00"),
            created_by=self.admin,
        )

    def test_inventory_pages_require_login_and_manager_role(self):
        url = reverse("inventory:scan")
        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 302)

        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("inventory:movement_list")).status_code,
            403,
        )

    def test_scan_routes_known_unknown_blank_and_inactive_barcodes(self):
        self.client.force_login(self.admin)

        known = self.client.get(reverse("inventory:scan"), {"barcode": "0012345"})
        self.assertRedirects(
            known,
            reverse("inventory:receive", args=[self.product.pk]),
            fetch_redirect_response=False,
        )

        unknown = self.client.get(reverse("inventory:scan"), {"barcode": "000999"})
        self.assertEqual(unknown.status_code, 302)
        self.assertEqual(
            unknown.url,
            f"{reverse('catalog:product_create')}?barcode=000999",
        )
        self.assertEqual(Product.objects.count(), 1)

        blank = self.client.get(reverse("inventory:scan"), {"barcode": "   "})
        self.assertEqual(blank.status_code, 200)
        self.assertContains(blank, "This field is required")

        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        inactive = self.client.get(reverse("inventory:scan"), {"barcode": "0012345"})
        self.assertRedirects(
            inactive,
            reverse("catalog:product_detail", args=[self.product.pk]),
            fetch_redirect_response=False,
        )

    def test_receipt_uses_post_redirect_get_and_does_not_repeat_on_refresh(self):
        self.client.force_login(self.admin)
        url = reverse("inventory:receive", args=[self.product.pk])

        response = self.client.post(url, {"quantity": "10", "note": "Opening count"})

        self.assertRedirects(
            response,
            reverse("catalog:product_detail", args=[self.product.pk]),
            fetch_redirect_response=False,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 10)
        self.assertEqual(InventoryMovement.objects.count(), 1)

        self.client.get(response.url)
        self.assertEqual(InventoryMovement.objects.count(), 1)

    def test_adjustment_allows_negative_result_and_history_shows_details(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("inventory:adjust", args=[self.product.pk]),
            {"quantity_change": "-3", "reason": "Damaged item"},
        )

        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, -3)

        history = self.client.get(
            reverse("inventory:movement_list"), {"movement_type": "ADJUSTMENT"}
        )
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, "Damaged item")
        self.assertContains(history, "-3")
        self.assertContains(history, self.owner.username)

    def test_stale_inactive_post_is_rejected_without_a_movement(self):
        self.client.force_login(self.admin)
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("inventory:receive", args=[self.product.pk]),
            {"quantity": "2", "note": "Delivery"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reactivate this product")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 0)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_foreign_shop_product_is_not_found(self):
        foreign_shop = Shop.objects.create(name="Other Shop")
        foreign_owner = User.objects.create_user(
            username="foreign-owner",
            password="StrongPass!2026",
            shop=foreign_shop,
            role=User.Role.OWNER,
        )
        self.client.force_login(foreign_owner)

        self.assertEqual(
            self.client.get(reverse("inventory:receive", args=[self.product.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("inventory:adjust", args=[self.product.pk])).status_code,
            404,
        )

    def test_modal_receipt_and_adjustment_return_json_and_validation_html(self):
        self.client.force_login(self.admin)
        receipt_url = reverse("inventory:receive", args=[self.product.pk])
        get_response = self.client.get(
            receipt_url,
            headers={"X-Product-Workspace": "modal"},
        )
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("Quantity received", get_response.json()["dialog_html"])

        invalid = self.client.post(
            receipt_url,
            {"quantity": "0", "note": "Bad"},
            headers={"X-Product-Workspace": "modal"},
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("greater than or equal to 1", invalid.json()["dialog_html"])

        received = self.client.post(
            receipt_url,
            {"quantity": "4", "note": "Delivery"},
            headers={"X-Product-Workspace": "modal"},
        )
        self.assertEqual(received.status_code, 200)
        self.assertEqual(received.json()["result"], "ok")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 4)

        adjusted = self.client.post(
            reverse("inventory:adjust", args=[self.product.pk]),
            {"quantity_change": "-6", "reason": "Count correction"},
            headers={"X-Product-Workspace": "modal"},
        )
        self.assertEqual(adjusted.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, -2)
        self.assertEqual(InventoryMovement.objects.filter(product=self.product).count(), 2)
