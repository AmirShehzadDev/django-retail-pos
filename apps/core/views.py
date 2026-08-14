from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.policies import can_edit_shop_settings, can_view_shop_settings

from .forms import AuditFilterForm, DailySummaryForm, ShopSettingsForm
from .models import AuditEvent
from .policies import can_view_reports
from .reporting import audit_events, current_review_counts, daily_summary, format_audit_payload
from .services import update_shop_name


@never_cache
@login_required
def home(request):
    return render(request, "core/home.html")


@never_cache
@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "version": settings.POS_APP_VERSION})


def _require_reports(actor):
    if not can_view_reports(actor):
        raise PermissionDenied("You cannot view reports.")


@never_cache
@login_required
@require_GET
def daily_summary_view(request):
    _require_reports(request.user)
    today = timezone.localdate(timezone=ZoneInfo(request.user.shop.timezone))
    if request.GET:
        form = DailySummaryForm(request.GET)
        if form.is_valid():
            selected_date = form.cleaned_data.get("date") or today
        else:
            selected_date = today
    else:
        form = DailySummaryForm(initial={"date": today})
        selected_date = today
    context = {
        "form": form,
        "summary": daily_summary(request.user, selected_date),
        "review_counts": current_review_counts(request.user),
        "previous_date": selected_date - timedelta(days=1),
        "next_date": selected_date + timedelta(days=1),
    }
    return render(request, "core/daily_summary.html", context)


@never_cache
@login_required
@require_GET
def audit_history(request):
    _require_reports(request.user)
    form = AuditFilterForm(request.GET, actor=request.user)
    if form.is_valid():
        events = audit_events(
            request.user,
            query=form.cleaned_data["q"],
            date_from=form.cleaned_data["date_from"],
            date_to=form.cleaned_data["date_to"],
            event_actor=form.cleaned_data["actor"],
            action=form.cleaned_data["action"],
            target_type=form.cleaned_data["target_type"],
        )
    else:
        events = AuditEvent.objects.none()
    page_obj = Paginator(events, 50).get_page(request.GET.get("page"))
    for event in page_obj.object_list:
        event.before_display = format_audit_payload(event.before_values)
        event.after_display = format_audit_payload(event.after_values)
    preserved = request.GET.copy()
    preserved.pop("page", None)
    return render(
        request,
        "core/audit_history.html",
        {
            "form": form,
            "page_obj": page_obj,
            "events": page_obj.object_list,
            "query_string": preserved.urlencode(),
        },
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def shop_settings(request):
    if not can_view_shop_settings(request.user):
        raise PermissionDenied
    can_edit = can_edit_shop_settings(request.user)
    if request.method == "POST" and not can_edit:
        raise PermissionDenied

    shop = request.user.shop
    form = ShopSettingsForm(request.POST or None, initial={"name": shop.name})
    if request.method == "POST" and form.is_valid():
        try:
            result = update_shop_name(actor=request.user, name=form.cleaned_data["name"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            shop = result[0] if isinstance(result, tuple) else result
            messages.success(request, "Shop settings were updated.")
            return redirect("core:shop_settings")

    return render(
        request,
        "core/shop_settings.html",
        {"form": form, "shop": shop, "can_edit": can_edit},
    )
