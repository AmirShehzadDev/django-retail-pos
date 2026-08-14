from django import forms
from django.contrib.auth import get_user_model

from .models import AuditEvent, Shop

INPUT_CLASSES = (
    "block min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 "
    "text-slate-950 shadow-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-200"
)


class ShopSettingsForm(forms.Form):
    name = forms.CharField(
        label="Shop name",
        max_length=Shop._meta.get_field("name").max_length,
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASSES, "autocomplete": "organization", "autofocus": True}
        ),
    )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Shop name is required.")
        return name


class DailySummaryForm(forms.Form):
    date = forms.DateField(
        label="Business date",
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}),
    )


class AuditFilterForm(forms.Form):
    q = forms.CharField(
        label="Target",
        required=False,
        max_length=64,
        widget=forms.SearchInput(
            attrs={"class": INPUT_CLASSES, "placeholder": "Order number, product ID, or user ID"}
        ),
    )
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
    actor = forms.ChoiceField(
        label="Actor",
        required=False,
        choices=(),
        widget=forms.Select(attrs={"class": INPUT_CLASSES}),
    )
    action = forms.ChoiceField(
        label="Action",
        required=False,
        choices=[("", "All actions"), *AuditEvent.Action.choices],
        widget=forms.Select(attrs={"class": INPUT_CLASSES}),
    )
    target_type = forms.ChoiceField(
        label="Target type",
        required=False,
        choices=[("", "All target types"), *AuditEvent.TargetType.choices],
        widget=forms.Select(attrs={"class": INPUT_CLASSES}),
    )

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "All actors")]
        if actor and actor.shop_id:
            choices.extend(
                (str(user.pk), user.get_full_name() or user.username)
                for user in get_user_model()
                .objects.filter(shop_id=actor.shop_id)
                .order_by("first_name", "last_name", "username", "id")
            )
        self.fields["actor"].choices = choices

    def clean_q(self):
        return self.cleaned_data["q"].strip()

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("date_from")
            and cleaned.get("date_to")
            and cleaned["date_from"] > cleaned["date_to"]
        ):
            raise forms.ValidationError("From date cannot be after To date.")
        return cleaned
