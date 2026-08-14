from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Shop


class CoreViewTests(TestCase):
    password = "StrongPass!2026"

    def setUp(self):
        self.shop = Shop.objects.create(name="Original Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password=self.password,
            shop=self.shop,
            role=User.Role.OWNER,
        )
        self.admin = User.objects.create_user(
            username="admin",
            password=self.password,
            shop=self.shop,
            role=User.Role.ADMIN,
            created_by=self.owner,
        )
        self.cashier = User.objects.create_user(
            username="cashier",
            password=self.password,
            shop=self.shop,
            role=User.Role.CASHIER,
            created_by=self.owner,
        )

    def test_health_remains_public(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "version": settings.POS_APP_VERSION},
        )

    def test_home_requires_authentication_and_identifies_user(self):
        anonymous = self.client.get(reverse("core:home"))
        self.assertEqual(anonymous.status_code, 302)
        self.assertEqual(
            anonymous.url,
            f"{reverse('accounts:login')}?next={reverse('core:home')}",
        )

        self.client.force_login(self.owner)
        authenticated = self.client.get(reverse("core:home"))

        self.assertEqual(authenticated.status_code, 200)
        self.assertContains(authenticated, self.shop.name)
        self.assertContains(authenticated, self.owner.username)

    def test_home_navigation_uses_one_product_stock_destination_for_managers(self):
        self.client.force_login(self.admin)
        manager_response = self.client.get(reverse("core:home"))

        self.assertContains(manager_response, reverse("catalog:product_list"), count=2)
        self.assertContains(manager_response, "Products &amp; Stock", count=2)
        self.assertNotContains(manager_response, reverse("inventory:scan"))
        self.assertNotContains(manager_response, "Receive stock")

        self.client.force_login(self.cashier)
        cashier_response = self.client.get(reverse("core:home"))

        self.assertContains(cashier_response, reverse("catalog:product_list"), count=2)
        self.assertContains(cashier_response, "Browse products")
        self.assertNotContains(cashier_response, reverse("inventory:scan"))

    def test_owner_changes_only_shop_name(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("core:shop_settings"),
            {
                "name": "  Updated Shop  ",
                "currency": "USD",
                "timezone": "UTC",
                "is_active": "",
            },
        )

        self.assertRedirects(response, reverse("core:shop_settings"))
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "Updated Shop")
        self.assertEqual(self.shop.currency, Shop.Currency.PKR)
        self.assertEqual(self.shop.timezone, Shop.Timezone.ASIA_KARACHI)
        self.assertTrue(self.shop.is_active)

    def test_admin_can_view_settings_but_cannot_post(self):
        self.client.force_login(self.admin)

        get_response = self.client.get(reverse("core:shop_settings"))
        post_response = self.client.post(reverse("core:shop_settings"), {"name": "Not allowed"})

        self.assertEqual(get_response.status_code, 200)
        self.assertFalse(get_response.context["can_edit"])
        self.assertEqual(post_response.status_code, 403)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "Original Shop")

    def test_cashier_cannot_view_shop_settings(self):
        self.client.force_login(self.cashier)

        response = self.client.get(reverse("core:shop_settings"))

        self.assertEqual(response.status_code, 403)
