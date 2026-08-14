from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.services import (
    change_own_password,
    create_managed_user,
    reset_managed_user_password,
    set_managed_user_active,
    update_managed_user,
)
from apps.core.models import AuditEvent, Shop


class UserConstraintTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")

    def test_case_insensitive_duplicate_username_is_rejected_by_database(self):
        User.objects.create_user(username="Cashier", password="StrongPass!2026", shop=self.shop)

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                username="cashier",
                password="StrongPass!2026",
                shop=self.shop,
            )

    def test_only_one_owner_is_allowed_per_shop(self):
        User.objects.create_user(
            username="owner-one",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                username="owner-two",
                password="StrongPass!2026",
                shop=self.shop,
                role=User.Role.OWNER,
            )

    def test_different_shops_can_have_an_owner(self):
        other_shop = Shop.objects.create(name="Other")
        first = User.objects.create_user(
            username="owner-one",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )
        second = User.objects.create_user(
            username="owner-two",
            password="StrongPass!2026",
            shop=other_shop,
            role=User.Role.OWNER,
        )

        self.assertNotEqual(first.shop_id, second.shop_id)


class AccountServiceTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
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

    def test_owner_creates_admin_with_server_controlled_fields_and_audit(self):
        user, changed = create_managed_user(
            actor=self.owner,
            username="  NewAdmin  ",
            first_name="  New ",
            last_name=" Admin  ",
            role=User.Role.ADMIN,
            password="AnotherStrong!2026",
        )

        self.assertTrue(changed)
        self.assertEqual(user.username, "NewAdmin")
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "Admin")
        self.assertEqual(user.shop, self.shop)
        self.assertEqual(user.created_by, self.owner)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.USER_CREATED)
        self.assertEqual(event.before_values, {})
        self.assertEqual(event.after_values["role"], User.Role.ADMIN)

    def test_admin_can_create_cashier_but_not_admin_or_owner(self):
        user, _ = create_managed_user(
            actor=self.admin,
            username="new-cashier",
            role=User.Role.CASHIER,
            password="AnotherStrong!2026",
        )
        self.assertEqual(user.role, User.Role.CASHIER)

        for role in (User.Role.ADMIN, User.Role.OWNER):
            with self.subTest(role=role), self.assertRaises(PermissionDenied):
                create_managed_user(
                    actor=self.admin,
                    username=f"denied-{role.lower()}",
                    role=role,
                    password="AnotherStrong!2026",
                )

    def test_create_revalidates_password_and_case_insensitive_username(self):
        with self.assertRaises(ValidationError):
            create_managed_user(
                actor=self.owner,
                username="weak-user",
                role=User.Role.CASHIER,
                password="short",
            )
        with self.assertRaises(ValidationError):
            create_managed_user(
                actor=self.owner,
                username="CASHIER",
                role=User.Role.CASHIER,
                password="AnotherStrong!2026",
            )
        self.assertFalse(AuditEvent.objects.exists())

    def test_owner_profile_and_role_edit_writes_focused_events(self):
        target, changed = update_managed_user(
            actor=self.owner,
            target_id=self.cashier.pk,
            username=" renamed ",
            first_name="First",
            last_name="Last",
            role=User.Role.ADMIN,
        )

        self.assertTrue(changed)
        self.assertEqual(target.role, User.Role.ADMIN)
        profile = AuditEvent.objects.get(action=AuditEvent.Action.USER_PROFILE_UPDATED)
        role = AuditEvent.objects.get(action=AuditEvent.Action.USER_ROLE_CHANGED)
        self.assertEqual(profile.before_values["username"], "cashier")
        self.assertEqual(profile.after_values["username"], "renamed")
        self.assertNotIn("role", profile.after_values)
        self.assertEqual(role.before_values, {"role": User.Role.CASHIER})
        self.assertEqual(role.after_values, {"role": User.Role.ADMIN})

    def test_unchanged_edit_is_successful_and_not_audited(self):
        _, changed = update_managed_user(
            actor=self.admin,
            target_id=self.cashier.pk,
            username=" cashier ",
            first_name="",
            last_name="",
            role=None,
        )

        self.assertFalse(changed)
        self.assertFalse(AuditEvent.objects.exists())

    def test_admin_cannot_promote_cashier_or_manage_admin(self):
        with self.assertRaises(PermissionDenied):
            update_managed_user(
                actor=self.admin,
                target_id=self.cashier.pk,
                username=self.cashier.username,
                role=User.Role.ADMIN,
            )
        with self.assertRaises(PermissionDenied):
            set_managed_user_active(actor=self.admin, target_id=self.admin.pk, active=False)
        self.assertFalse(AuditEvent.objects.exists())

    def test_no_manager_can_manage_owner_or_self(self):
        with self.assertRaises(PermissionDenied):
            reset_managed_user_password(
                actor=self.owner,
                target_id=self.owner.pk,
                new_password="AnotherStrong!2026",
            )
        with self.assertRaises(PermissionDenied):
            set_managed_user_active(actor=self.admin, target_id=self.admin.pk, active=False)

    def test_cross_shop_target_is_rejected(self):
        other_shop = Shop.objects.create(name="Other")
        outsider = User.objects.create_user(
            username="outsider",
            password="StrongPass!2026",
            shop=other_shop,
            role=User.Role.CASHIER,
        )

        with self.assertRaises(PermissionDenied):
            set_managed_user_active(actor=self.owner, target_id=outsider.pk, active=False)

    def test_status_change_is_idempotent_and_preserves_role_and_password(self):
        old_hash = self.cashier.password
        target, changed = set_managed_user_active(
            actor=self.admin,
            target_id=self.cashier.pk,
            active=False,
        )
        _, repeated_changed = set_managed_user_active(
            actor=self.admin,
            target_id=self.cashier.pk,
            active=False,
        )

        self.assertTrue(changed)
        self.assertFalse(repeated_changed)
        self.assertEqual(target.role, User.Role.CASHIER)
        self.assertEqual(target.password, old_hash)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.get().action, AuditEvent.Action.USER_DEACTIVATED)

    def test_manager_password_reset_has_empty_payload_and_preserves_other_fields(self):
        target, changed = reset_managed_user_password(
            actor=self.admin,
            target_id=self.cashier.pk,
            new_password="AnotherStrong!2026",
        )

        self.assertTrue(changed)
        self.assertTrue(target.check_password("AnotherStrong!2026"))
        self.assertEqual(target.role, User.Role.CASHIER)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.USER_PASSWORD_RESET)
        self.assertEqual(event.before_values, {})
        self.assertEqual(event.after_values, {})

    def test_own_password_change_is_audited_without_password_material(self):
        actor = change_own_password(actor=self.cashier, new_password="AnotherStrong!2026")

        self.assertTrue(actor.check_password("AnotherStrong!2026"))
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.USER_PASSWORD_CHANGED)
        self.assertEqual(event.before_values, {})
        self.assertEqual(event.after_values, {})

    def test_stale_inactive_actor_is_rejected(self):
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            set_managed_user_active(actor=self.admin, target_id=self.cashier.pk, active=False)

    def test_audit_failure_rolls_back_user_change(self):
        with patch("apps.accounts.services.record", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                set_managed_user_active(
                    actor=self.admin,
                    target_id=self.cashier.pk,
                    active=False,
                )

        self.cashier.refresh_from_db()
        self.assertTrue(self.cashier.is_active)
