from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Order, SalesReturnItem
from .services import POSTGRESQL_POSITIVE_BIGINT_MAX, normalize_barcode

INPUT_CLASSES = (
    "block min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 "
    "text-slate-950 shadow-sm outline-none focus:border-blue-600 focus:ring-2 "
    "focus:ring-blue-200 disabled:bg-slate-100 disabled:text-slate-600"
)


def _positive_bigint(value, *, label):
    if isinstance(value, bool):
        raise ValidationError(f"Enter a valid {label}.")
    normalized = str(value or "").strip()
    if not normalized or not normalized.isascii() or not normalized.isdecimal():
        raise ValidationError(f"Enter a positive whole-number {label}.")
    parsed = int(normalized, 10)
    if parsed < 1 or parsed > POSTGRESQL_POSITIVE_BIGINT_MAX:
        raise ValidationError(f"Enter a valid {label}.")
    return parsed


class StartWorkspaceForm(forms.Form):
    pass


class NewDraftForm(forms.Form):
    pass


class PositiveBigIntegerField(forms.CharField):
    def __init__(self, *args, value_label="value", **kwargs):
        self.value_label = value_label
        super().__init__(*args, strip=True, **kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        return _positive_bigint(value, label=self.value_label)


class BarcodeScanForm(forms.Form):
    barcode = forms.CharField(
        label="Barcode",
        max_length=64,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASSES,
                "autocomplete": "off",
                "data-pos-scanner": "",
                "inputmode": "numeric",
                "placeholder": "Scan or type a barcode",
            }
        ),
    )
    expected_version = PositiveBigIntegerField(
        value_label="order version",
        widget=forms.HiddenInput(attrs={"data-pos-version": ""}),
    )

    def clean_barcode(self):
        return normalize_barcode(self.cleaned_data["barcode"])


class PosProductSearchForm(forms.Form):
    q = forms.CharField(
        label="Find a product",
        required=False,
        max_length=200,
        strip=True,
        widget=forms.SearchInput(
            attrs={
                "class": INPUT_CLASSES,
                "autocomplete": "off",
                "placeholder": "Name, barcode, or SKU",
            }
        ),
    )

    def clean_q(self):
        return self.cleaned_data["q"].strip()


class AddProductForm(forms.Form):
    product_id = PositiveBigIntegerField(
        value_label="product",
        widget=forms.HiddenInput(),
    )
    expected_version = PositiveBigIntegerField(
        value_label="order version",
        widget=forms.HiddenInput(attrs={"data-pos-version": ""}),
    )


class QuickCreateProductForm(forms.Form):
    context = forms.CharField(widget=forms.HiddenInput())
    name = forms.CharField(
        label="Product name",
        max_length=200,
        strip=True,
        widget=forms.TextInput(attrs={"class": INPUT_CLASSES, "autofocus": True}),
    )
    selling_price = forms.DecimalField(
        label="Selling price",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={"class": INPUT_CLASSES, "min": "0", "step": "0.01", "inputmode": "decimal"}
        ),
    )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise ValidationError("Enter a product name.")
        return name


class QuantityForm(forms.Form):
    quantity = PositiveBigIntegerField(
        value_label="quantity",
        widget=forms.NumberInput(
            attrs={
                "class": INPUT_CLASSES,
                "min": "1",
                "step": "1",
                "inputmode": "numeric",
                "data-pos-quantity": "",
            }
        ),
    )
    expected_version = PositiveBigIntegerField(
        value_label="order version",
        widget=forms.HiddenInput(attrs={"data-pos-version": ""}),
    )


class VersionedActionForm(forms.Form):
    expected_version = PositiveBigIntegerField(
        value_label="order version",
        widget=forms.HiddenInput(attrs={"data-pos-version": ""}),
    )


class CheckoutForm(VersionedActionForm):
    cash_received = forms.DecimalField(
        label="Cash received",
        max_digits=38,
        decimal_places=2,
        min_value=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={"class": INPUT_CLASSES, "min": "0", "step": "0.01", "inputmode": "decimal"}
        ),
    )


class CompletedOrderSearchForm(forms.Form):
    q = forms.CharField(
        label="Search orders",
        required=False,
        max_length=200,
        strip=True,
        widget=forms.SearchInput(
            attrs={
                "class": INPUT_CLASSES,
                "placeholder": "Order number, product, barcode, or exact amount",
            }
        ),
    )
    has_change = forms.BooleanField(label="Non-zero change only", required=False)
    date_from = forms.DateField(
        label="From",
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}),
    )
    date_to = forms.DateField(
        label="To",
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}),
    )
    cashier = forms.ChoiceField(
        label="Cashier",
        required=False,
        choices=(),
        widget=forms.Select(attrs={"class": INPUT_CLASSES}),
    )
    status = forms.ChoiceField(
        label="Status",
        required=False,
        choices=[
            ("", "All statuses"),
            (Order.Status.COMPLETED, "Completed"),
            (Order.Status.PARTIALLY_RETURNED, "Partially returned"),
            (Order.Status.RETURNED, "Returned"),
            (Order.Status.VOIDED, "Voided"),
        ],
        widget=forms.Select(attrs={"class": INPUT_CLASSES}),
    )

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "All cashiers")]
        if actor and actor.shop_id:
            choices.extend(
                (str(user.pk), user.get_full_name() or user.username)
                for user in get_user_model()
                .objects.filter(shop_id=actor.shop_id)
                .order_by("first_name", "username", "id")
            )
        self.fields["cashier"].choices = choices

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("date_from")
            and cleaned.get("date_to")
            and cleaned["date_from"] > cleaned["date_to"]
        ):
            raise ValidationError("From date cannot be after To date.")
        return cleaned


class ReturnForm(forms.Form):
    request_token = forms.UUIDField(widget=forms.HiddenInput())
    reason = forms.CharField(
        label="Return reason (optional)",
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASSES,
                "rows": 2,
                "placeholder": "Optional note about this return",
            }
        ),
    )


class ReturnItemForm(forms.Form):
    order_item_id = forms.IntegerField(widget=forms.HiddenInput(), min_value=1)
    quantity = forms.IntegerField(
        label="Return quantity",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"class": INPUT_CLASSES, "min": 0, "step": 1, "data-return-quantity": ""}
        ),
    )
    disposition = forms.ChoiceField(
        label="Disposition",
        required=False,
        choices=SalesReturnItem.Disposition.choices,
        initial=SalesReturnItem.Disposition.RESTOCK,
        widget=forms.Select(attrs={"class": INPUT_CLASSES, "data-return-disposition": ""}),
    )

    def __init__(self, *args, remaining_quantity=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.remaining_quantity = remaining_quantity
        if remaining_quantity is not None:
            self.fields["quantity"].max_value = remaining_quantity
            self.fields["quantity"].widget.attrs["max"] = remaining_quantity

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("quantity", 0) > 0 and not cleaned.get("disposition"):
            self.add_error("disposition", "Choose what happens to this item.")
        return cleaned


class VoidForm(forms.Form):
    request_token = forms.UUIDField(widget=forms.HiddenInput())
    reason = forms.CharField(
        label="Void reason",
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASSES,
                "rows": 3,
                "placeholder": "Why was this sale completed in error?",
            }
        ),
    )
