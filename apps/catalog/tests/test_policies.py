from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.catalog.policies import (
    can_change_product_stock,
    can_edit_product,
    can_manage_catalog,
    can_view_catalog,
    can_view_product,
)
from apps.core.models import Shop


class CatalogPolicyTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.owner = self._user("owner", User.Role.OWNER)
        self.admin = self._user("admin", User.Role.ADMIN)
        self.cashier = self._user("cashier", User.Role.CASHIER)
        self.product = Product.objects.create(
            shop=self.shop,
            name="Rice",
            selling_price="100.00",
            created_by=self.owner,
        )

    def _user(self, username, role, *, shop=None, active=True):
        return User.objects.create_user(
            username=username,
            password="StrongPass!2026",
            shop=shop or self.shop,
            role=role,
            is_active=active,
        )

    def test_owner_and_admin_can_manage_same_shop_product(self):
        for actor in (self.owner, self.admin):
            with self.subTest(actor=actor.role):
                self.assertTrue(can_manage_catalog(actor))
                self.assertTrue(can_view_catalog(actor))
                self.assertTrue(can_view_product(actor, self.product))
                self.assertTrue(can_edit_product(actor, self.product))
                self.assertTrue(can_change_product_stock(actor, self.product))

    def test_cashier_can_view_but_cannot_manage_same_shop_product(self):
        self.assertTrue(can_view_catalog(self.cashier))
        self.assertTrue(can_view_product(self.cashier, self.product))
        self.assertFalse(can_manage_catalog(self.cashier))
        self.assertFalse(can_edit_product(self.cashier, self.product))
        self.assertFalse(can_change_product_stock(self.cashier, self.product))

    def test_inactive_and_foreign_users_cannot_view_product(self):
        other_shop = Shop.objects.create(name="Other")
        foreign_admin = self._user("foreign", User.Role.ADMIN, shop=other_shop)
        inactive_admin = self._user("inactive", User.Role.ADMIN, active=False)

        self.assertFalse(can_manage_catalog(inactive_admin))
        self.assertFalse(can_view_catalog(inactive_admin))
        self.assertTrue(can_manage_catalog(foreign_admin))
        for actor in (foreign_admin, inactive_admin):
            with self.subTest(actor=actor.username):
                self.assertFalse(can_view_product(actor, self.product))
                self.assertFalse(can_edit_product(actor, self.product))

        shopless = User(
            username="shopless",
            shop=None,
            role=User.Role.CASHIER,
            is_active=True,
        )
        self.assertFalse(can_view_catalog(shopless))
        self.assertFalse(can_view_product(shopless, self.product))

    def test_inactive_product_does_not_change_catalog_authorization(self):
        self.product.is_active = False

        self.assertTrue(can_change_product_stock(self.admin, self.product))
