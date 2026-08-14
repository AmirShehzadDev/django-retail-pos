from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import AuditEvent, Shop
from apps.core.services import update_shop_name


class ShopServiceTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Old Shop")
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
        )

    def test_owner_updates_only_trimmed_name_and_records_event(self):
        shop, changed = update_shop_name(actor=self.owner, name="  New Shop  ")

        self.assertTrue(changed)
        self.assertEqual(shop.name, "New Shop")
        self.assertEqual(shop.currency, Shop.Currency.PKR)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.SHOP_NAME_CHANGED)
        self.assertEqual(event.before_values, {"name": "Old Shop"})
        self.assertEqual(event.after_values, {"name": "New Shop"})

    def test_unchanged_name_does_not_audit(self):
        _, changed = update_shop_name(actor=self.owner, name=" Old Shop ")

        self.assertFalse(changed)
        self.assertFalse(AuditEvent.objects.exists())

    def test_admin_and_inactive_owner_are_rejected(self):
        with self.assertRaises(PermissionDenied):
            update_shop_name(actor=self.admin, name="Denied")
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            update_shop_name(actor=self.owner, name="Denied")

    def test_blank_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            update_shop_name(actor=self.owner, name="   ")

    def test_audit_failure_rolls_back_shop_change(self):
        with patch("apps.core.services.record", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                update_shop_name(actor=self.owner, name="New Shop")

        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "Old Shop")
