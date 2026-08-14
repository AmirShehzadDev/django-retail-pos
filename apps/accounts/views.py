from django.contrib import messages
from django.contrib.auth import get_user_model, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    ManagedPasswordResetForm,
    ManagedUserCreateForm,
    ManagedUserUpdateForm,
    PosAuthenticationForm,
    PosPasswordChangeForm,
)
from .policies import (
    can_change_active_state,
    can_create_role,
    can_edit_user,
    can_reset_password,
    can_view_user,
)
from .services import (
    change_own_password,
    create_managed_user,
    reset_managed_user_password,
    set_managed_user_active,
    update_managed_user,
)

User = get_user_model()


def _add_validation_error(form, error):
    if hasattr(error, "message_dict"):
        for field, errors in error.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, error)


def _result_object(result):
    return result[0] if isinstance(result, tuple) else result


def _require_manager(actor):
    if not any(can_create_role(actor, role) for role in (User.Role.ADMIN, User.Role.CASHIER)):
        raise PermissionDenied


def _visible_user_or_404(actor, user_id):
    target = get_object_or_404(
        User.objects.select_related("shop", "created_by").filter(shop_id=actor.shop_id),
        pk=user_id,
    )
    if not can_view_user(actor, target):
        raise Http404
    return target


@method_decorator(never_cache, name="dispatch")
class PosLoginView(LoginView):
    authentication_form = PosAuthenticationForm
    redirect_authenticated_user = True
    template_name = "accounts/login.html"


@never_cache
@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def password_change(request):
    form = PosPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = change_own_password(
                actor=request.user,
                new_password=form.cleaned_data["new_password1"],
            )
        except ValidationError as error:
            _add_validation_error(form, error)
        else:
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was changed.")
            return redirect("core:home")
    return render(request, "accounts/password_change.html", {"form": form})


@never_cache
@login_required
@require_http_methods(["GET"])
def user_list(request):
    _require_manager(request.user)
    users = User.objects.filter(shop_id=request.user.shop_id).select_related("shop", "created_by")
    if request.user.role == User.Role.ADMIN:
        users = users.filter(role=User.Role.CASHIER)

    q = request.GET.get("q", "").strip()
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )

    permitted_roles = {User.Role.CASHIER}
    if request.user.role == User.Role.OWNER:
        permitted_roles = set(User.Role.values)
    selected_role = request.GET.get("role", "")
    if selected_role in permitted_roles:
        users = users.filter(role=selected_role)
    else:
        selected_role = ""

    selected_status = request.GET.get("status", "")
    if selected_status == "active":
        users = users.filter(is_active=True)
    elif selected_status == "inactive":
        users = users.filter(is_active=False)
    else:
        selected_status = ""

    return render(
        request,
        "accounts/user_list.html",
        {
            "users": users.order_by("username", "id"),
            "q": q,
            "selected_role": selected_role,
            "selected_status": selected_status,
        },
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def user_create(request):
    _require_manager(request.user)
    form = ManagedUserCreateForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            result = create_managed_user(
                actor=request.user,
                username=form.cleaned_data["username"],
                first_name=form.cleaned_data["first_name"].strip(),
                last_name=form.cleaned_data["last_name"].strip(),
                role=form.cleaned_data["role"],
                password=form.cleaned_data["password1"],
            )
        except ValidationError as error:
            _add_validation_error(form, error)
        else:
            managed_user = _result_object(result)
            messages.success(request, f"User {managed_user.username} was created.")
            return redirect("accounts:user_detail", user_id=managed_user.pk)
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "page_title": "Create user", "submit_label": "Create user"},
    )


@never_cache
@login_required
@require_http_methods(["GET"])
def user_detail(request, user_id):
    managed_user = _visible_user_or_404(request.user, user_id)
    return render(
        request,
        "accounts/user_detail.html",
        {
            "managed_user": managed_user,
            "can_edit": can_edit_user(request.user, managed_user),
            "can_reset_password": can_reset_password(request.user, managed_user),
            "can_change_active_state": can_change_active_state(request.user, managed_user),
        },
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def user_edit(request, user_id):
    managed_user = _visible_user_or_404(request.user, user_id)
    if not can_edit_user(request.user, managed_user):
        raise PermissionDenied
    form = ManagedUserUpdateForm(
        request.POST or None,
        actor=request.user,
        target=managed_user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = update_managed_user(
                actor=request.user,
                target_id=managed_user.pk,
                username=form.cleaned_data["username"],
                first_name=form.cleaned_data["first_name"].strip(),
                last_name=form.cleaned_data["last_name"].strip(),
                role=form.cleaned_data["role"],
            )
        except ValidationError as error:
            _add_validation_error(form, error)
        else:
            managed_user = _result_object(result)
            messages.success(request, f"User {managed_user.username} was updated.")
            return redirect("accounts:user_detail", user_id=managed_user.pk)
    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "managed_user": managed_user,
            "page_title": "Edit user",
            "submit_label": "Save changes",
        },
    )


def _set_user_active(request, user_id, *, active):
    managed_user = _visible_user_or_404(request.user, user_id)
    if not can_change_active_state(request.user, managed_user):
        raise PermissionDenied
    result = set_managed_user_active(
        actor=request.user,
        target_id=managed_user.pk,
        active=active,
    )
    managed_user = _result_object(result)
    state = "reactivated" if active else "deactivated"
    messages.success(request, f"User {managed_user.username} was {state}.")
    return redirect("accounts:user_detail", user_id=managed_user.pk)


@never_cache
@login_required
@require_POST
def user_deactivate(request, user_id):
    return _set_user_active(request, user_id, active=False)


@never_cache
@login_required
@require_POST
def user_reactivate(request, user_id):
    return _set_user_active(request, user_id, active=True)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def user_password_reset(request, user_id):
    managed_user = _visible_user_or_404(request.user, user_id)
    if not can_reset_password(request.user, managed_user):
        raise PermissionDenied
    form = ManagedPasswordResetForm(request.POST or None, target=managed_user)
    if request.method == "POST" and form.is_valid():
        try:
            reset_managed_user_password(
                actor=request.user,
                target_id=managed_user.pk,
                new_password=form.cleaned_data["password1"],
            )
        except ValidationError as error:
            _add_validation_error(form, error)
        else:
            messages.success(request, f"Password reset for {managed_user.username}.")
            return redirect("accounts:user_detail", user_id=managed_user.pk)
    return render(
        request,
        "accounts/password_reset.html",
        {"form": form, "managed_user": managed_user},
    )
