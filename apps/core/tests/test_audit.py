from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.accounts.models import User
from apps.core.audit import record
from apps.core.models import AuditEvent, Shop


class AuditWriterTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )

    def test_record_appends_approved_event_and_copies_values(self):
        before = {"name": "Old"}
        event = record(
            shop=self.shop,
            actor=self.owner,
            action=AuditEvent.Action.SHOP_NAME_CHANGED,
            target_type=AuditEvent.TargetType.SHOP,
            target_identifier=self.shop.pk,
            before_values=before,
            after_values={"name": "New"},
        )
        before["name"] = "Mutated"

        self.assertEqual(event.before_values, {"name": "Old"})
        self.assertEqual(event.target_identifier, str(self.shop.pk))

    def test_sensitive_keys_are_rejected_recursively(self):
        sensitive_payloads = [
            {"password": "secret"},
            {"password_hash": "secret"},
            {"nested": {"csrfToken": "secret"}},
            {"items": [{"session_id": "secret"}]},
        ]
        for payload in sensitive_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                record(
                    shop=self.shop,
                    actor=self.owner,
                    action=AuditEvent.Action.USER_PASSWORD_CHANGED,
                    target_type=AuditEvent.TargetType.USER,
                    target_identifier=self.owner.pk,
                    after_values=payload,
                )
        self.assertFalse(AuditEvent.objects.exists())

    def test_inactive_or_cross_shop_actor_is_rejected(self):
        other_shop = Shop.objects.create(name="Other")
        for shop in (other_shop, self.shop):
            self.owner.is_active = shop != self.shop
            with self.subTest(shop=shop.pk), self.assertRaises(ValidationError):
                record(
                    shop=shop,
                    actor=self.owner,
                    action=AuditEvent.Action.SHOP_NAME_CHANGED,
                    target_type=AuditEvent.TargetType.SHOP,
                    target_identifier=shop.pk,
                )

    def test_action_target_mismatch_is_rejected(self):
        with self.assertRaises(ValidationError):
            record(
                shop=self.shop,
                actor=self.owner,
                action=AuditEvent.Action.USER_CREATED,
                target_type=AuditEvent.TargetType.SHOP,
                target_identifier=self.owner.pk,
            )

    def test_actor_and_shop_references_are_protected(self):
        record(
            shop=self.shop,
            actor=self.owner,
            action=AuditEvent.Action.USER_PASSWORD_CHANGED,
            target_type=AuditEvent.TargetType.USER,
            target_identifier=self.owner.pk,
        )

        with self.assertRaises(ProtectedError):
            self.owner.delete()
        with self.assertRaises(ProtectedError):
            self.shop.delete()
