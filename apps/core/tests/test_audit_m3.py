from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.core.audit import record
from apps.core.models import AuditEvent, Shop


class MilestoneThreeAuditWriterTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )

    def test_new_actions_accept_exactly_their_approved_target(self):
        mappings = {
            AuditEvent.Action.PRODUCT_QUICK_CREATED: AuditEvent.TargetType.PRODUCT,
            AuditEvent.Action.DRAFT_TAKEN_OVER: AuditEvent.TargetType.ORDER,
            AuditEvent.Action.DRAFT_DISCARDED: AuditEvent.TargetType.ORDER,
        }

        for action, approved_target in mappings.items():
            with self.subTest(action=action, target=approved_target):
                event = record(
                    shop=self.shop,
                    actor=self.owner,
                    action=action,
                    target_type=approved_target,
                    target_identifier=7,
                )
                self.assertEqual(event.target_type, approved_target)

            for rejected_target in set(AuditEvent.TargetType.values) - {approved_target}:
                with (
                    self.subTest(action=action, target=rejected_target),
                    self.assertRaises(ValidationError),
                ):
                    record(
                        shop=self.shop,
                        actor=self.owner,
                        action=action,
                        target_type=rejected_target,
                        target_identifier=7,
                    )

    def test_new_actions_preserve_sensitive_key_rejection(self):
        for action, target_type in (
            (AuditEvent.Action.PRODUCT_QUICK_CREATED, AuditEvent.TargetType.PRODUCT),
            (AuditEvent.Action.DRAFT_TAKEN_OVER, AuditEvent.TargetType.ORDER),
            (AuditEvent.Action.DRAFT_DISCARDED, AuditEvent.TargetType.ORDER),
        ):
            with self.subTest(action=action), self.assertRaises(ValidationError):
                record(
                    shop=self.shop,
                    actor=self.owner,
                    action=action,
                    target_type=target_type,
                    target_identifier=7,
                    after_values={"nested": {"session_token": "secret"}},
                )

        self.assertFalse(AuditEvent.objects.exists())
