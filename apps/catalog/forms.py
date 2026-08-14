from django import forms
from django.core.exceptions import ValidationError

from .models import Product
from .services import normalize_optional_identifier

INPUT_CLASSES = (
    "block min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 "
    "text-slate-950 shadow-sm outline-none focus:border-blue-600 focus:ring-2 "
    "focus:ring-blue-200 disabled:bg-slate-100 disabled:text-slate-600"
)
SELECT_CLASSES = INPUT_CLASSES
CHECKBOX_CLASSES = (
    "size-5 rounded border-slate-300 text-brand-700 focus:ring-2 focus:ring-brand-300"
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("name", "barcode", "sku", "selling_price", "cost_price")
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASSES, "autofocus": True}),
            "barcode": forms.TextInput(
                attrs={"class": INPUT_CLASSES, "autocomplete": "off", "inputmode": "numeric"}
            ),
            "sku": forms.TextInput(attrs={"class": INPUT_CLASSES, "autocomplete": "off"}),
            "selling_price": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "min": "0", "step": "0.01"}
            ),
            "cost_price": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "min": "0", "step": "0.01"}
            ),
        }
        help_texts = {
            "barcode": "Optional. Leading zeroes are preserved.",
            "sku": "Optional. SKU matching is not case-sensitive.",
            "selling_price": "PKR amount, excluding tax.",
            "cost_price": "Optional PKR amount for your records.",
        }

    def __init__(self, *args, shop, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "Product name"

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise ValidationError("Enter a product name.")
        return name

    def clean_barcode(self):
        barcode = normalize_optional_identifier(self.cleaned_data.get("barcode"))
        if barcode:
            matches = Product.objects.filter(shop=self.shop, barcode=barcode)
            if self.instance.pk:
                matches = matches.exclude(pk=self.instance.pk)
            if matches.exists():
                raise ValidationError("A product with this barcode already exists.")
        return barcode

    def clean_sku(self):
        sku = normalize_optional_identifier(self.cleaned_data.get("sku"))
        if sku:
            matches = Product.objects.filter(shop=self.shop, sku__iexact=sku)
            if self.instance.pk:
                matches = matches.exclude(pk=self.instance.pk)
            if matches.exists():
                raise ValidationError("A product with this SKU already exists.")
        return sku

    def clean_selling_price(self):
        value = self.cleaned_data["selling_price"]
        if value < 0:
            raise ValidationError("Selling price cannot be negative.")
        return value

    def clean_cost_price(self):
        value = self.cleaned_data.get("cost_price")
        if value is not None and value < 0:
            raise ValidationError("Cost price cannot be negative.")
        return value


class ProductCreateForm(ProductForm):
    quantity_received_now = forms.IntegerField(
        label="Quantity received now",
        required=False,
        min_value=1,
        help_text="Optional. Records opening stock as a receipt movement.",
        widget=forms.NumberInput(
            attrs={
                "class": INPUT_CLASSES,
                "min": "1",
                "step": "1",
                "inputmode": "numeric",
            }
        ),
    )
    receipt_note = forms.CharField(
        label="Receipt note",
        required=False,
        max_length=500,
        help_text="Optional delivery or opening-stock note.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": "2"}),
    )

    def clean_receipt_note(self):
        return self.cleaned_data["receipt_note"].strip()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("receipt_note") and cleaned_data.get("quantity_received_now") is None:
            self.add_error(
                "receipt_note",
                "Enter Quantity received now when adding a receipt note.",
            )
        return cleaned_data


class ProductSearchForm(forms.Form):
    STATUS_CHOICES = (
        ("", "All statuses"),
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    q = forms.CharField(required=False, max_length=200)
    status = forms.ChoiceField(required=False, choices=STATUS_CHOICES)
    negative = forms.BooleanField(required=False)
    needs_review = forms.BooleanField(required=False)

    def clean_q(self):
        return self.cleaned_data["q"].strip()


class ProductScanForm(forms.Form):
    barcode = forms.CharField(
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASSES,
                "autocomplete": "off",
                "data-autofocus": True,
                "inputmode": "numeric",
            }
        ),
    )

    def clean_barcode(self):
        barcode = normalize_optional_identifier(self.cleaned_data["barcode"])
        if not barcode:
            raise ValidationError("Scan or enter a barcode.")
        return barcode
