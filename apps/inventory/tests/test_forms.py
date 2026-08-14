from django.test import SimpleTestCase

from apps.inventory.forms import ProductScanForm, StockAdjustmentForm, StockReceiptForm


class InventoryFormTests(SimpleTestCase):
    def test_scan_preserves_leading_zeroes_and_trims_edges(self):
        form = ProductScanForm({"barcode": "  0012345  "})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["barcode"], "0012345")

    def test_scan_rejects_empty_value(self):
        form = ProductScanForm({"barcode": "   "})

        self.assertFalse(form.is_valid())
        self.assertIn("barcode", form.errors)

    def test_receipt_requires_positive_whole_quantity(self):
        for value in ("0", "-2", "1.5"):
            with self.subTest(value=value):
                form = StockReceiptForm({"quantity": value, "note": "Delivery"})
                self.assertFalse(form.is_valid())
                self.assertIn("quantity", form.errors)

    def test_adjustment_accepts_signed_nonzero_whole_quantity(self):
        for value in ("5", "-3"):
            with self.subTest(value=value):
                form = StockAdjustmentForm({"quantity_change": value, "reason": "Count correction"})
                self.assertTrue(form.is_valid())

    def test_adjustment_rejects_zero_decimal_and_blank_reason(self):
        invalid_rows = (
            {"quantity_change": "0", "reason": "Count correction"},
            {"quantity_change": "1.5", "reason": "Count correction"},
            {"quantity_change": "1", "reason": "   "},
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                self.assertFalse(StockAdjustmentForm(row).is_valid())
