from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import Shop, Terminal
from apps.sales.exceptions import QuickCreateContextInvalid
from apps.sales.models import Order
from apps.sales.signing import create_quick_create_context, read_quick_create_context


class QuickCreateSigningTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.actor = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")
        self.draft = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=1,
            created_by=self.actor,
            current_cashier=self.actor,
        )
        self.session_key = "session-key-one"

    def token(self):
        return create_quick_create_context(
            self.actor,
            self.terminal,
            self.draft,
            " 0012345 ",
            session_key=self.session_key,
        )

    def test_valid_context_preserves_barcode_and_exact_scope(self):
        token = self.token()

        context = read_quick_create_context(token, self.actor, session_key=self.session_key)

        self.assertEqual(context.actor_id, self.actor.pk)
        self.assertEqual(context.shop_id, self.shop.pk)
        self.assertEqual(context.terminal_id, self.terminal.pk)
        self.assertEqual(context.draft_id, self.draft.pk)
        self.assertEqual(context.barcode, "0012345")
        self.assertEqual(context.expected_version, 1)
        self.assertNotIn(self.session_key, token)

    def test_tampered_or_expired_context_is_rejected(self):
        token = self.token()
        for candidate, max_age in ((f"{token}x", 900), (token, -1)):
            with self.subTest(candidate=candidate[-8:], max_age=max_age):
                with self.assertRaises(QuickCreateContextInvalid):
                    read_quick_create_context(
                        candidate,
                        self.actor,
                        session_key=self.session_key,
                        max_age=max_age,
                    )

    def test_missing_changed_or_other_session_is_rejected(self):
        token = self.token()
        for session_key in ("", "session-key-two"):
            with self.subTest(session_key=session_key):
                with self.assertRaises(QuickCreateContextInvalid):
                    read_quick_create_context(token, self.actor, session_key=session_key)

    def test_actor_change_is_rejected(self):
        token = self.token()
        other = User.objects.create_user(
            username="other",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.ADMIN,
        )

        with self.assertRaises(QuickCreateContextInvalid):
            read_quick_create_context(token, other, session_key=self.session_key)

    def test_draft_mutation_takeover_or_clear_invalidates_context(self):
        token = self.token()
        self.draft.version = 2
        self.draft.save(update_fields=["version"])
        with self.assertRaises(QuickCreateContextInvalid):
            read_quick_create_context(token, self.actor, session_key=self.session_key)

    def test_configured_terminal_change_invalidates_context(self):
        token = self.token()
        self.terminal.is_active = False
        self.terminal.save(update_fields=["is_active"])
        with self.assertRaises(QuickCreateContextInvalid):
            read_quick_create_context(token, self.actor, session_key=self.session_key)
