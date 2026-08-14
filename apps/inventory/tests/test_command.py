from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import Shop
from apps.inventory.services import adjust_stock, receive_stock


class ReconcileInventoryCommandTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Main Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Tea",
            selling_price=Decimal("250.00"),
            created_by=self.owner,
        )

    def test_empty_and_reconciled_ledgers_succeed(self):
        output = StringIO()
        call_command("reconcile_inventory", stdout=output)
        self.assertIn("Inventory reconciled: 1 product(s).", output.getvalue())

        receive_stock(actor=self.owner, product_id=self.product.pk, quantity=4)
        adjust_stock(
            actor=self.owner,
            product_id=self.product.pk,
            quantity_change=-6,
            reason="Count correction",
        )
        output = StringIO()
        call_command("reconcile_inventory", stdout=output)
        self.assertIn("Inventory reconciled: 1 product(s).", output.getvalue())

    def test_discrepancy_fails_without_writing(self):
        Product.objects.filter(pk=self.product.pk).update(stock_on_hand=7)
        output = StringIO()

        with self.assertRaisesMessage(CommandError, "1 mismatch"):
            call_command("reconcile_inventory", stdout=output)

        self.assertIn("cached=7 ledger=0", output.getvalue())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 7)
