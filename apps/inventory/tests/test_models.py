from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import Shop
from apps.inventory.models import InventoryMovement


class InventoryMovementModelTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            created_by=self.owner,
            name="Tea",
            barcode="0012345",
            selling_price=Decimal("250.00"),
        )

    def movement(self, **overrides):
        values = {
            "shop": self.shop,
            "product": self.product,
            "movement_type": InventoryMovement.MovementType.RECEIPT,
            "quantity_change": 5,
            "balance_after": 5,
            "actor": self.owner,
            "reason": "Manual stock receipt",
        }
        values.update(overrides)
        return InventoryMovement.objects.create(**values)

    def test_receipt_must_have_a_positive_quantity(self):
        for quantity in (0, -1):
            with (
                self.subTest(quantity=quantity),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                self.movement(quantity_change=quantity)

    def test_non_receipt_movement_must_have_a_nonzero_quantity(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.movement(
                movement_type=InventoryMovement.MovementType.ADJUSTMENT,
                quantity_change=0,
            )

        movement = self.movement(
            movement_type=InventoryMovement.MovementType.ADJUSTMENT,
            quantity_change=-2,
            balance_after=-2,
            reason="Damaged stock",
        )
        self.assertEqual(movement.quantity_change, -2)

    def test_reason_must_not_be_empty(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.movement(reason="")

    def test_default_order_is_newest_first(self):
        first = self.movement()
        second = self.movement(
            movement_type=InventoryMovement.MovementType.ADJUSTMENT,
            quantity_change=1,
            balance_after=6,
            reason="Count correction",
        )

        self.assertEqual(list(InventoryMovement.objects.all()), [second, first])

    def test_instance_and_queryset_mutations_are_rejected(self):
        movement = self.movement()
        movement.reason = "Rewritten"

        with self.assertRaises(ValidationError):
            movement.save()
        with self.assertRaises(ValidationError):
            movement.delete()
        with self.assertRaises(ValidationError):
            InventoryMovement.objects.filter(pk=movement.pk).update(reason="Rewritten")
        with self.assertRaises(ValidationError):
            InventoryMovement.objects.filter(pk=movement.pk).delete()

        movement.refresh_from_db()
        self.assertEqual(movement.reason, "Manual stock receipt")

    def test_all_referenced_relationships_are_protected(self):
        self.movement()

        with self.assertRaises(ProtectedError):
            self.product.delete()
        with self.assertRaises(ProtectedError):
            self.owner.delete()
        with self.assertRaises(ProtectedError):
            self.shop.delete()
