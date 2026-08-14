from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import Shop


class UserModelTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Test Shop")

    def test_custom_user_model_is_active(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")

    def test_user_requires_shop(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="cashier", password="StrongPass!2026")

    def test_database_rejects_unknown_role(self):
        user = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(role="UNKNOWN")

    def test_creator_is_set_null_when_creator_is_removed(self):
        owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )
        cashier = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
            created_by=owner,
        )

        owner.delete()
        cashier.refresh_from_db()

        self.assertIsNone(cashier.created_by)

    def test_shop_is_protected_while_users_reference_it(self):
        User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
        )

        with self.assertRaises(ProtectedError):
            self.shop.delete()
