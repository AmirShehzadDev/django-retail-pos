from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import Shop, Terminal
from apps.sales.models import Order
from apps.sales.policies import (
    can_create_draft,
    can_edit_draft,
    can_quick_create_product,
    can_take_over_draft,
    can_use_pos,
    can_view_draft,
)


class PosPolicyTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")

    def user(self, role, *, shop=None, active=True, username=None):
        return User.objects.create_user(
            username=username or role.lower(),
            password="StrongPass!2026",
            shop=shop or self.shop,
            role=role,
            is_active=active,
        )

    def test_all_three_roles_have_pos_parity(self):
        for role in (User.Role.OWNER, User.Role.ADMIN, User.Role.CASHIER):
            actor = self.user(role, username=f"user-{role.lower()}")
            with self.subTest(role=role):
                self.assertTrue(can_use_pos(actor))
                self.assertTrue(can_create_draft(actor, self.terminal))
                self.assertTrue(can_quick_create_product(actor))

    def test_anonymous_inactive_invalid_role_and_inactive_shop_are_denied(self):
        inactive = self.user(User.Role.CASHIER, active=False, username="inactive")
        invalid = self.user(User.Role.CASHIER, username="invalid")
        invalid.role = "REPORTER"
        self.shop.is_active = False
        shop_inactive = self.user(User.Role.ADMIN, username="shop-inactive")

        for actor in (AnonymousUser(), inactive, invalid, shop_inactive):
            with self.subTest(actor=actor):
                self.assertFalse(can_use_pos(actor))

    def test_draft_capability_matrix_and_scope(self):
        cashier = self.user(User.Role.CASHIER, username="cashier")
        other = self.user(User.Role.ADMIN, username="other")
        order = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=1,
            created_by=cashier,
            current_cashier=cashier,
        )

        self.assertTrue(can_view_draft(cashier, order, self.terminal))
        self.assertTrue(can_edit_draft(cashier, order, self.terminal))
        self.assertFalse(can_take_over_draft(cashier, order, self.terminal))
        self.assertTrue(can_view_draft(other, order, self.terminal))
        self.assertFalse(can_edit_draft(other, order, self.terminal))
        self.assertTrue(can_take_over_draft(other, order, self.terminal))

        foreign_shop = Shop.objects.create(name="Foreign")
        foreign_terminal = Terminal.objects.create(
            shop=foreign_shop, code="TILL-1", name="Foreign till"
        )
        order.status = Order.Status.DISCARDED
        self.assertFalse(can_view_draft(cashier, order, self.terminal))
        order.status = Order.Status.DRAFT
        self.assertFalse(can_view_draft(cashier, order, foreign_terminal))

        foreign_cashier = self.user(
            User.Role.CASHIER,
            shop=foreign_shop,
            username="foreign-cashier",
        )
        order.current_cashier = foreign_cashier
        self.assertFalse(can_view_draft(cashier, order, self.terminal))
