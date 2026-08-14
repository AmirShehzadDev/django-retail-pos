from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import Shop


class ProductModelTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )

    def product(self, **overrides):
        values = {
            "shop": self.shop,
            "created_by": self.owner,
            "name": "Tea",
            "barcode": "0012345",
            "sku": "TEA-1",
            "selling_price": Decimal("250.00"),
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_clean_normalizes_optional_identifiers_and_preserves_leading_zeroes(self):
        product = Product(
            shop=self.shop,
            created_by=self.owner,
            name="  Tea  ",
            barcode="  0012345  ",
            sku="   ",
            selling_price=Decimal("250.00"),
        )

        product.full_clean()

        self.assertEqual(product.name, "Tea")
        self.assertEqual(product.barcode, "0012345")
        self.assertIsNone(product.sku)

    def test_clean_rejects_a_blank_name(self):
        product = Product(
            shop=self.shop,
            created_by=self.owner,
            name="  ",
            selling_price=Decimal("250.00"),
        )

        with self.assertRaises(ValidationError) as error:
            product.full_clean()

        self.assertIn("name", error.exception.message_dict)

    def test_barcode_is_unique_within_shop_but_not_across_shops(self):
        self.product()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.product(name="Coffee", sku="COFFEE-1")

        other_shop = Shop.objects.create(name="Other")
        other_owner = User.objects.create_user(
            username="other-owner",
            password="StrongPass!2026",
            shop=other_shop,
            role=User.Role.OWNER,
        )
        Product.objects.create(
            shop=other_shop,
            created_by=other_owner,
            name="Tea",
            barcode="0012345",
            selling_price=Decimal("250.00"),
        )

    def test_multiple_null_barcodes_and_skus_are_allowed(self):
        self.product(barcode=None, sku=None)
        self.product(name="Coffee", barcode=None, sku=None)

        self.assertEqual(Product.objects.count(), 2)

    def test_sku_is_unique_case_insensitively_within_shop(self):
        self.product(sku="Tea-1")

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.product(name="Coffee", barcode="0099999", sku="TEA-1")

    def test_database_rejects_negative_prices(self):
        for field in ("selling_price", "cost_price"):
            with self.subTest(field=field), self.assertRaises(IntegrityError), transaction.atomic():
                self.product(
                    barcode=f"code-{field}",
                    sku=f"sku-{field}",
                    **{field: Decimal("-0.01")},
                )

    def test_nullable_cost_price_and_negative_stock_are_allowed(self):
        product = self.product(cost_price=None, stock_on_hand=-2)

        product.refresh_from_db()
        self.assertIsNone(product.cost_price)
        self.assertEqual(product.stock_on_hand, -2)

    def test_product_relationships_are_protected(self):
        self.product()

        with self.assertRaises(ProtectedError):
            self.owner.delete()
        with self.assertRaises(ProtectedError):
            self.shop.delete()
