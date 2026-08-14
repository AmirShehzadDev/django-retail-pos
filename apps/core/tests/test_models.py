from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.core.models import Shop, Terminal


class ShopModelTests(TestCase):
    def test_shop_uses_approved_localization_defaults(self):
        shop = Shop.objects.create(name="Test Shop")

        self.assertEqual(shop.currency, Shop.Currency.PKR)
        self.assertEqual(shop.timezone, Shop.Timezone.ASIA_KARACHI)
        self.assertTrue(shop.is_active)

    def test_database_rejects_non_pkr_currency(self):
        shop = Shop.objects.create(name="Test Shop")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Shop.objects.filter(pk=shop.pk).update(currency="USD")

    def test_database_rejects_other_timezone(self):
        shop = Shop.objects.create(name="Test Shop")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Shop.objects.filter(pk=shop.pk).update(timezone="UTC")


class TerminalModelTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Test Shop")

    def test_terminal_code_is_normalized_to_uppercase(self):
        terminal = Terminal.objects.create(shop=self.shop, code=" till-1 ", name="Main")

        self.assertEqual(terminal.code, "TILL-1")

    def test_duplicate_terminal_code_in_same_shop_is_rejected(self):
        Terminal.objects.create(shop=self.shop, code="TILL-1", name="Main")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Terminal.objects.create(shop=self.shop, code="TILL-1", name="Other")

    def test_same_terminal_code_is_allowed_in_another_shop(self):
        other_shop = Shop.objects.create(name="Other Shop")
        Terminal.objects.create(shop=self.shop, code="TILL-1", name="Main")

        terminal = Terminal.objects.create(shop=other_shop, code="TILL-1", name="Main")

        self.assertEqual(terminal.code, "TILL-1")

    def test_database_rejects_lowercase_terminal_code(self):
        terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Main")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Terminal.objects.filter(pk=terminal.pk).update(code="till-2")
