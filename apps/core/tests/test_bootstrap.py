import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.core.models import Shop, Terminal


class BootstrapCommandTests(TestCase):
    password_variable = "TEST_POS_OWNER_PASSWORD"
    strong_password = "Bootstrap-Owner!2026"

    def call_bootstrap(self, *, output=None, **options):
        defaults = {
            "shop_name": "Test Shop",
            "terminal_code": "TILL-1",
            "terminal_name": "Main Checkout",
            "owner_username": "owner",
            "owner_password_env": self.password_variable,
        }
        defaults.update(options)
        with patch.dict(os.environ, {self.password_variable: self.strong_password}):
            call_command("bootstrap_pos", stdout=output or StringIO(), **defaults)

    def test_clean_bootstrap_creates_shop_terminal_and_owner(self):
        output = StringIO()

        self.call_bootstrap(output=output)

        shop = Shop.objects.get()
        terminal = Terminal.objects.get()
        owner = get_user_model().objects.get()
        self.assertEqual(shop.name, "Test Shop")
        self.assertEqual(terminal.code, "TILL-1")
        self.assertEqual(terminal.shop, shop)
        self.assertEqual(owner.role, get_user_model().Role.OWNER)
        self.assertEqual(owner.shop, shop)
        self.assertTrue(owner.is_staff)
        self.assertTrue(owner.is_superuser)
        self.assertTrue(owner.check_password(self.strong_password))
        self.assertNotIn(self.strong_password, output.getvalue())

    def test_repeat_bootstrap_is_idempotent_and_does_not_reset_password(self):
        self.call_bootstrap()
        owner = get_user_model().objects.get(username="owner")
        password_hash = owner.password
        output = StringIO()

        call_command(
            "bootstrap_pos",
            shop_name="Test Shop",
            terminal_code="TILL-1",
            terminal_name="Main Checkout",
            owner_username="owner",
            stdout=output,
        )

        owner.refresh_from_db()
        self.assertEqual(Shop.objects.count(), 1)
        self.assertEqual(Terminal.objects.count(), 1)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(owner.password, password_hash)
        self.assertIn("no changes made", output.getvalue())

    def test_weak_password_rolls_back_new_shop_and_terminal(self):
        with patch.dict(os.environ, {self.password_variable: "password"}):
            with self.assertRaises(CommandError):
                call_command(
                    "bootstrap_pos",
                    shop_name="Test Shop",
                    terminal_code="TILL-1",
                    terminal_name="Main Checkout",
                    owner_username="owner",
                    owner_password_env=self.password_variable,
                )

        self.assertFalse(Shop.objects.exists())
        self.assertFalse(Terminal.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    def test_conflicting_terminal_is_rejected_without_creating_owner(self):
        shop = Shop.objects.create(name="Test Shop")
        Terminal.objects.create(shop=shop, code="OTHER", name="Other")

        with self.assertRaises(CommandError):
            self.call_bootstrap()

        self.assertEqual(Shop.objects.count(), 1)
        self.assertEqual(Terminal.objects.count(), 1)
        self.assertFalse(get_user_model().objects.exists())

    def test_conflicting_owner_is_rejected(self):
        shop = Shop.objects.create(name="Test Shop")
        Terminal.objects.create(shop=shop, code="TILL-1", name="Main Checkout")
        get_user_model().objects.create_user(
            username="owner",
            password=self.strong_password,
            shop=shop,
            role=get_user_model().Role.CASHIER,
        )

        with self.assertRaises(CommandError):
            self.call_bootstrap()
