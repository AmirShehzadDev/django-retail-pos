from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .policies import can_change_role, can_create_role

User = get_user_model()

INPUT_CLASSES = (
    "block min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 "
    "text-slate-950 shadow-sm outline-none focus:border-blue-600 focus:ring-2 "
    "focus:ring-blue-200 disabled:bg-slate-100 disabled:text-slate-600"
)
SELECT_CLASSES = INPUT_CLASSES


def _username_field():
    model_field = User._meta.get_field("username")
    return forms.CharField(
        max_length=model_field.max_length,
        validators=model_field.validators,
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASSES, "autocomplete": "username", "autofocus": True}
        ),
    )


def _name_field(label):
    return forms.CharField(
        label=label,
        max_length=User._meta.get_field("first_name").max_length,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASSES, "autocomplete": "name"}),
    )


class PosAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Invalid username or password.",
        "inactive": "Invalid username or password.",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": INPUT_CLASSES, "autocomplete": "username", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"class": INPUT_CLASSES, "autocomplete": "current-password"}
        )

    def clean(self):
        username = self.cleaned_data.get("username")
        if username:
            normalized = username.strip()
            matches = list(
                User._default_manager.filter(username__iexact=normalized)
                .values_list("username", flat=True)
                .order_by("pk")[:2]
            )
            if len(matches) > 1:
                raise ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                )
            self.cleaned_data["username"] = matches[0] if matches else normalized
        return super().clean()

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError(
                self.error_messages["inactive"],
                code="inactive",
            )


class ManagedUserCreateForm(forms.Form):
    username = _username_field()
    first_name = _name_field("First name")
    last_name = _name_field("Last name")
    role = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES, "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES, "autocomplete": "new-password"}),
    )

    def __init__(self, *args, actor, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        roles = [
            (value, label) for value, label in User.Role.choices if can_create_role(actor, value)
        ]
        if actor.role == User.Role.ADMIN:
            self.fields.pop("role")
        else:
            self.fields["role"].choices = roles

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User._default_manager.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role", User.Role.CASHIER)
        if not can_create_role(self.actor, role):
            self.add_error("role" if "role" in self.fields else None, "Role is not permitted.")
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two password fields did not match.")
        if password1:
            candidate = User(
                username=cleaned_data.get("username", ""),
                first_name=cleaned_data.get("first_name", "").strip(),
                last_name=cleaned_data.get("last_name", "").strip(),
                role=role,
                shop=self.actor.shop,
            )
            try:
                validate_password(password1, user=candidate)
            except ValidationError as error:
                self.add_error("password1", error)
        cleaned_data["role"] = role
        return cleaned_data


class ManagedUserUpdateForm(forms.Form):
    username = _username_field()
    first_name = _name_field("First name")
    last_name = _name_field("Last name")
    role = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
    )

    def __init__(self, *args, actor, target, **kwargs):
        self.actor = actor
        self.target = target
        initial = kwargs.setdefault("initial", {})
        initial.update(
            {
                "username": target.username,
                "first_name": target.first_name,
                "last_name": target.last_name,
                "role": target.role,
            }
        )
        super().__init__(*args, **kwargs)
        if actor.role == User.Role.OWNER:
            self.fields["role"].choices = [
                (role, label) for role, label in User.Role.choices if role != User.Role.OWNER
            ]
        else:
            self.fields.pop("role")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if (
            User._default_manager.filter(username__iexact=username)
            .exclude(pk=self.target.pk)
            .exists()
        ):
            raise ValidationError("A user with that username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role", self.target.role)
        if role != self.target.role and not can_change_role(self.actor, self.target, role):
            self.add_error("role" if "role" in self.fields else None, "Role is not permitted.")
        cleaned_data["role"] = role
        return cleaned_data


class ManagedPasswordResetForm(forms.Form):
    password1 = forms.CharField(
        label="New password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": INPUT_CLASSES, "autocomplete": "new-password", "autofocus": True}
        ),
    )
    password2 = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES, "autocomplete": "new-password"}),
    )

    def __init__(self, *args, target, **kwargs):
        self.target = target
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two password fields did not match.")
        if password1:
            try:
                validate_password(password1, user=self.target)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data


class PosPasswordChangeForm(PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES
