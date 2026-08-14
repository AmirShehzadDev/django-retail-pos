from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.core.audit import record
from apps.core.models import AuditEvent, Shop


class MilestoneTwoAuditWriterTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )

    def test_product_price_change_mapping_is_allowed(self):
        event = record(
            shop=self.shop,
            actor=self.owner,
            action=AuditEvent.Action.PRODUCT_PRICE_CHANGED,
            target_type=AuditEvent.TargetType.PRODUCT,
            target_identifier=7,
            before_values={"selling_price": "100.00"},
            after_values={"selling_price": "110.00"},
        )

        self.assertEqual(event.target_type, AuditEvent.TargetType.PRODUCT)

    def test_inventory_adjustment_mapping_is_allowed(self):
        event = record(
            shop=self.shop,
            actor=self.owner,
            action=AuditEvent.Action.INVENTORY_ADJUSTED,
            target_type=AuditEvent.TargetType.PRODUCT,
            target_identifier=7,
            after_values={
                "movement_id": 11,
                "quantity_change": -2,
                "reason": "Damaged stock",
                "balance_before": 5,
                "balance_after": 3,
            },
        )

        self.assertEqual(event.action, AuditEvent.Action.INVENTORY_ADJUSTED)

    def test_m2_actions_reject_non_product_targets(self):
        for action in (
            AuditEvent.Action.PRODUCT_PRICE_CHANGED,
            AuditEvent.Action.INVENTORY_ADJUSTED,
        ):
            with self.subTest(action=action), self.assertRaises(ValidationError):
                record(
                    shop=self.shop,
                    actor=self.owner,
                    action=action,
                    target_type=AuditEvent.TargetType.SHOP,
                    target_identifier=7,
                )
