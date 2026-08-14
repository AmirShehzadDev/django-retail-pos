from django.test import SimpleTestCase

from apps.sales.forms import (
    AddProductForm,
    BarcodeScanForm,
    NewDraftForm,
    PosProductSearchForm,
    QuantityForm,
    QuickCreateProductForm,
    StartWorkspaceForm,
    VersionedActionForm,
)
from apps.sales.services import POSTGRESQL_POSITIVE_BIGINT_MAX


class PosFormTests(SimpleTestCase):
    def test_start_and_new_forms_accept_no_trusted_fields(self):
        crafted = {
            "shop": "99",
            "terminal": "88",
            "slot": "3",
            "created_by": "77",
        }
        for form_class in (StartWorkspaceForm, NewDraftForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(crafted)
                self.assertTrue(form.is_valid())
                self.assertEqual(form.cleaned_data, {})
                self.assertEqual(tuple(form.fields), ())

    def test_barcode_scan_trims_edges_and_preserves_leading_zeroes(self):
        form = BarcodeScanForm({"barcode": " 0012345 ", "expected_version": "7"})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data, {"barcode": "0012345", "expected_version": 7})

    def test_barcode_scan_rejects_blank_and_overlong_values(self):
        for barcode in ("", "   ", "x" * 65):
            with self.subTest(barcode=barcode):
                form = BarcodeScanForm({"barcode": barcode, "expected_version": "1"})
                self.assertFalse(form.is_valid())
                self.assertIn("barcode", form.errors)

    def test_search_query_is_optional_trimmed_and_bounded(self):
        empty = PosProductSearchForm({"q": "   "})
        valid = PosProductSearchForm({"q": "  rice  "})
        overlong = PosProductSearchForm({"q": "x" * 201})

        self.assertTrue(empty.is_valid())
        self.assertEqual(empty.cleaned_data["q"], "")
        self.assertTrue(valid.is_valid())
        self.assertEqual(valid.cleaned_data["q"], "rice")
        self.assertFalse(overlong.is_valid())

    def test_positive_bigint_fields_reject_non_decimal_or_out_of_range_values(self):
        invalid_values = (
            "",
            "0",
            "-1",
            "+1",
            "1.0",
            "1e2",
            "True",
            str(POSTGRESQL_POSITIVE_BIGINT_MAX + 1),
        )
        form_factories = (
            lambda value: VersionedActionForm({"expected_version": value}),
            lambda value: QuantityForm({"quantity": value, "expected_version": "1"}),
            lambda value: AddProductForm({"product_id": value, "expected_version": "1"}),
        )
        for form_factory in form_factories:
            for value in invalid_values:
                with self.subTest(factory=form_factory, value=value):
                    self.assertFalse(form_factory(value).is_valid())

    def test_positive_bigint_fields_accept_storage_maximum(self):
        form = QuantityForm(
            {
                "quantity": str(POSTGRESQL_POSITIVE_BIGINT_MAX),
                "expected_version": str(POSTGRESQL_POSITIVE_BIGINT_MAX),
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["quantity"], POSTGRESQL_POSITIVE_BIGINT_MAX)
        self.assertEqual(form.cleaned_data["expected_version"], POSTGRESQL_POSITIVE_BIGINT_MAX)

    def test_quick_create_accepts_only_context_name_and_nonnegative_price(self):
        form = QuickCreateProductForm(
            {
                "context": "signed-token",
                "name": "  New product  ",
                "selling_price": "0.00",
                "barcode": "crafted",
                "stock_on_hand": "999",
                "needs_review": "false",
                "shop": "99",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data,
            {"context": "signed-token", "name": "New product", "selling_price": 0},
        )
        self.assertEqual(tuple(form.fields), ("context", "name", "selling_price"))

    def test_quick_create_rejects_invalid_name_and_money(self):
        invalid = (
            {"context": "token", "name": " ", "selling_price": "1.00"},
            {"context": "token", "name": "x" * 201, "selling_price": "1.00"},
            {"context": "token", "name": "Product", "selling_price": "-0.01"},
            {"context": "token", "name": "Product", "selling_price": "1.001"},
            {"context": "token", "name": "Product", "selling_price": "10000000000.00"},
        )
        for data in invalid:
            with self.subTest(data=data):
                self.assertFalse(QuickCreateProductForm(data).is_valid())

    def test_mutation_forms_expose_no_server_derived_fields(self):
        forbidden = {
            "shop",
            "terminal",
            "slot",
            "actor",
            "status",
            "source",
            "needs_review",
            "stock_on_hand",
            "unit_price",
            "line_total",
            "subtotal",
            "current_cashier",
            "discarded_by",
        }
        forms = (
            BarcodeScanForm(),
            AddProductForm(),
            QuickCreateProductForm(),
            QuantityForm(),
            VersionedActionForm(),
        )
        for form in forms:
            with self.subTest(form=type(form).__name__):
                self.assertFalse(forbidden.intersection(form.fields))
