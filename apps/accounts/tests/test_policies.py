from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.accounts.models import User
from apps.accounts.policies import (
    can_change_active_state,
    can_change_role,
    can_create_role,
    can_edit_shop_settings,
    can_edit_user,
    can_reset_password,
    can_view_shop_settings,
    can_view_user,
)


def user(*, pk, shop_id, role, active=True, staff=False, superuser=False):
    return SimpleNamespace(
        pk=pk,
        shop_id=shop_id,
        role=role,
        is_active=active,
        is_authenticated=True,
        is_staff=staff,
        is_superuser=superuser,
    )


class UserPolicyTests(SimpleTestCase):
    def setUp(self):
        self.owner = user(pk=1, shop_id=1, role=User.Role.OWNER)
        self.admin = user(pk=2, shop_id=1, role=User.Role.ADMIN)
        self.cashier = user(pk=3, shop_id=1, role=User.Role.CASHIER)

    def test_view_matrix(self):
        cases = [
            (self.owner, self.owner, True),
            (self.owner, self.admin, True),
            (self.owner, self.cashier, True),
            (self.admin, self.owner, False),
            (self.admin, self.admin, False),
            (self.admin, self.cashier, True),
            (self.cashier, self.cashier, False),
        ]
        for actor, target, expected in cases:
            with self.subTest(actor=actor.role, target=target.role):
                self.assertIs(can_view_user(actor, target), expected)

    def test_management_matrix(self):
        for policy in (can_edit_user, can_change_active_state, can_reset_password):
            cases = [
                (self.owner, self.owner, False),
                (self.owner, self.admin, True),
                (self.owner, self.cashier, True),
                (self.admin, self.owner, False),
                (self.admin, self.admin, False),
                (self.admin, self.cashier, True),
                (self.cashier, self.admin, False),
            ]
            for actor, target, expected in cases:
                with self.subTest(policy=policy.__name__, actor=actor.role, target=target.role):
                    self.assertIs(policy(actor, target), expected)

    def test_create_role_matrix(self):
        cases = [
            (self.owner, User.Role.OWNER, False),
            (self.owner, User.Role.ADMIN, True),
            (self.owner, User.Role.CASHIER, True),
            (self.admin, User.Role.ADMIN, False),
            (self.admin, User.Role.CASHIER, True),
            (self.cashier, User.Role.CASHIER, False),
        ]
        for actor, role, expected in cases:
            with self.subTest(actor=actor.role, role=role):
                self.assertIs(can_create_role(actor, role), expected)

    def test_only_owner_can_change_non_owner_roles(self):
        self.assertTrue(can_change_role(self.owner, self.admin, User.Role.CASHIER))
        self.assertTrue(can_change_role(self.owner, self.cashier, User.Role.ADMIN))
        self.assertFalse(can_change_role(self.owner, self.cashier, User.Role.OWNER))
        self.assertFalse(can_change_role(self.admin, self.cashier, User.Role.ADMIN))

    def test_cross_shop_targets_are_always_rejected(self):
        other_cashier = user(pk=4, shop_id=2, role=User.Role.CASHIER)
        for policy in (
            can_view_user,
            can_edit_user,
            can_change_active_state,
            can_reset_password,
        ):
            with self.subTest(policy=policy.__name__):
                self.assertFalse(policy(self.owner, other_cashier))
        self.assertFalse(can_change_role(self.owner, other_cashier, User.Role.ADMIN))

    def test_inactive_actor_and_django_flags_do_not_grant_access(self):
        inactive_owner = user(pk=8, shop_id=1, role=User.Role.OWNER, active=False)
        flagged_cashier = user(
            pk=9,
            shop_id=1,
            role=User.Role.CASHIER,
            staff=True,
            superuser=True,
        )
        self.assertFalse(can_edit_user(inactive_owner, self.cashier))
        self.assertFalse(can_edit_user(flagged_cashier, self.admin))
        self.assertFalse(can_view_shop_settings(flagged_cashier))

    def test_shop_settings_matrix(self):
        self.assertTrue(can_view_shop_settings(self.owner))
        self.assertTrue(can_view_shop_settings(self.admin))
        self.assertFalse(can_view_shop_settings(self.cashier))
        self.assertTrue(can_edit_shop_settings(self.owner))
        self.assertFalse(can_edit_shop_settings(self.admin))
