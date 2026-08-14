from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.forms import ProductCreateForm, ProductForm, ProductScanForm, ProductSearchForm
from apps.catalog.models import Product
from apps.core.models import Shop


class ProductFormTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.OWNER,
        )

    def data(self, **overrides):
        values = {
            "name": " Rice ",
            "barcode": "00123",
            "sku": "RICE-1",
            "selling_price": "120.00",
            "cost_price": "100.00",
        }
        values.update(overrides)
        return values

    def test_normalizes_safe_fields_and_preserves_leading_zeroes(self):
        form = ProductForm(self.data(name="  Rice  ", barcode=" 00123 "), shop=self.shop)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["name"], "Rice")
        self.assertEqual(form.cleaned_data["barcode"], "00123")

    def test_blank_identifiers_become_none(self):
        form = ProductForm(self.data(barcode="  ", sku=""), shop=self.shop)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["barcode"])
        self.assertIsNone(form.cleaned_data["sku"])

    def test_duplicate_identifiers_have_friendly_field_errors(self):
        Product.objects.create(
            shop=self.shop,
            name="Existing",
            barcode="00123",
            sku="Rice-1",
            selling_price="10.00",
            created_by=self.owner,
        )

        form = ProductForm(self.data(sku="RICE-1"), shop=self.shop)

        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.errors["barcode"][0])
        self.assertIn("already exists", form.errors["sku"][0])

    def test_negative_price_is_rejected(self):
        form = ProductForm(self.data(selling_price="-1.00"), shop=self.shop)

        self.assertFalse(form.is_valid())
        self.assertIn("selling_price", form.errors)

    def test_scan_and_search_forms_use_safe_normalization(self):
        scan = ProductScanForm({"barcode": " 00123 "})
        invalid_scan = ProductScanForm({"barcode": "   "})
        search = ProductSearchForm({"q": " rice ", "status": "not-valid"})

        self.assertTrue(scan.is_valid())
        self.assertEqual(scan.cleaned_data["barcode"], "00123")
        self.assertFalse(invalid_scan.is_valid())
        self.assertFalse(search.is_valid())
        self.assertEqual(search.cleaned_data["q"], "rice")

    def test_create_form_accepts_optional_receipt_and_rejects_non_positive_quantity(self):
        form = ProductCreateForm(
            self.data(quantity_received_now="7", receipt_note=" Opening count "),
            shop=self.shop,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["quantity_received_now"], 7)
        self.assertEqual(form.cleaned_data["receipt_note"], "Opening count")

        invalid = ProductCreateForm(
            self.data(barcode="00200", sku="RICE-2", quantity_received_now="0"),
            shop=self.shop,
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn("quantity_received_now", invalid.errors)
