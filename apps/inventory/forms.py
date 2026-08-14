from django import forms
from django.core.exceptions import ValidationError

from .models import InventoryMovement

INPUT_CLASSES = (
    "block min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 "
    "text-slate-950 shadow-sm outline-none focus:border-blue-600 focus:ring-2 "
    "focus:ring-blue-200 disabled:bg-slate-100 disabled:text-slate-600"
)


class ProductScanForm(forms.Form):
    barcode = forms.CharField(
        label="Barcode",
        max_length=64,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASSES,
                "autocomplete": "off",
                "data-autofocus": "",
                "placeholder": "Scan or type a barcode",
            }
        ),
    )

    def clean_barcode(self):
        barcode = self.cleaned_data["barcode"].strip()
        if not barcode:
            raise ValidationError("Scan or enter a barcode.")
        return barcode


class StockReceiptForm(forms.Form):
    quantity = forms.IntegerField(
        label="Quantity received",
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": INPUT_CLASSES,
                "min": "1",
                "step": "1",
                "inputmode": "numeric",
                "data-quantity-change": "",
                "data-autofocus": "",
            }
        ),
    )
    note = forms.CharField(
        label="Receipt note",
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASSES,
                "rows": "3",
                "placeholder": "Optional delivery or opening-stock note",
            }
        ),
    )

    def clean_note(self):
        return self.cleaned_data["note"].strip()


class StockAdjustmentForm(forms.Form):
    quantity_change = forms.IntegerField(
        label="Quantity change",
        help_text="Use a positive number to add stock or a negative number to remove stock.",
        widget=forms.NumberInput(
            attrs={
                "class": INPUT_CLASSES,
                "step": "1",
                "inputmode": "numeric",
                "data-quantity-change": "",
                "data-autofocus": "",
                "placeholder": "For example, 5 or -3",
            }
        ),
    )
    reason = forms.CharField(
        label="Reason",
        max_length=500,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASSES,
                "rows": "3",
                "placeholder": "Explain the physical or recording correction",
            }
        ),
    )

    def clean_quantity_change(self):
        quantity_change = self.cleaned_data["quantity_change"]
        if quantity_change == 0:
            raise ValidationError("Enter a non-zero whole number.")
        return quantity_change

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise ValidationError("Explain why this stock correction is needed.")
        return reason


class MovementFilterForm(forms.Form):
    q = forms.CharField(
        label="Product",
        required=False,
        max_length=200,
        widget=forms.SearchInput(
            attrs={
                "class": INPUT_CLASSES,
                "placeholder": "Name, barcode, or SKU",
            }
        ),
    )
    movement_type = forms.ChoiceField(
        label="Movement type",
        required=False,
        choices=[("", "All movement types"), *InventoryMovement.MovementType.choices],
        widget=forms.Select(attrs={"class": INPUT_CLASSES}),
    )

    def clean_q(self):
        return self.cleaned_data["q"].strip()
