from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.core.models import Shop, Terminal
from apps.sales.exceptions import TerminalUnavailable
from apps.sales.terminals import normalize_configured_terminal_code, resolve_pos_terminal


class PosTerminalTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.actor = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")

    @override_settings(POS_TERMINAL_CODE="  till-1 ")
    def test_configured_code_is_trimmed_and_uppercased(self):
        self.assertEqual(normalize_configured_terminal_code("  till-1 "), "TILL-1")
        self.assertEqual(resolve_pos_terminal(self.actor), self.terminal)

    def test_blank_and_overlong_configuration_are_unavailable(self):
        for value in (" ", "X" * 33):
            with self.subTest(value=value), override_settings(POS_TERMINAL_CODE=value):
                with self.assertRaises(TerminalUnavailable):
                    resolve_pos_terminal(self.actor)

    @override_settings(POS_TERMINAL_CODE="MISSING")
    def test_missing_configuration_never_falls_back(self):
        with self.assertRaises(TerminalUnavailable):
            resolve_pos_terminal(self.actor)

    def test_inactive_terminal_or_shop_is_unavailable(self):
        self.terminal.is_active = False
        self.terminal.save(update_fields=["is_active"])
        with self.assertRaises(TerminalUnavailable):
            resolve_pos_terminal(self.actor)

        self.terminal.is_active = True
        self.terminal.save(update_fields=["is_active"])
        self.shop.is_active = False
        self.shop.save(update_fields=["is_active"])
        self.actor.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            resolve_pos_terminal(self.actor)

    def test_anonymous_and_inactive_actor_are_denied(self):
        with self.assertRaises(PermissionDenied):
            resolve_pos_terminal(AnonymousUser())
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        self.actor.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            resolve_pos_terminal(self.actor)

    def test_locked_resolution_works_inside_atomic_context(self):
        with transaction.atomic():
            self.assertEqual(resolve_pos_terminal(self.actor, for_update=True), self.terminal)
