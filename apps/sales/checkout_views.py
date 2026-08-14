from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .checkout import complete_cash_checkout
from .exceptions import DraftTakeoverRequired, DraftVersionConflict, TerminalUnavailable
from .forms import CheckoutForm
from .models import Order
from .policies import can_use_pos

REFRESH_FAILURE_MESSAGE = "The POS could not refresh the current order. Refresh before continuing."


def _workspace_url(draft_id):
    return f"{reverse('sales:workspace')}?draft={draft_id}"


def _message_validation_error(request, error):
    if hasattr(error, "messages"):
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.error(request, str(error))


def _is_enhanced(request):
    return request.headers.get("X-POS-Enhanced") == "1"


def _enhanced_error(message, *, status, result="invalid"):
    return JsonResponse({"result": result, "error": message}, status=status)


def _enhanced_workspace(
    request,
    *,
    result,
    selected_draft_id,
    status=200,
    error="",
    overrides=None,
    extra=None,
    refresh_failure_message=REFRESH_FAILURE_MESSAGE,
):
    from .views import _enhanced_state

    try:
        return _enhanced_state(
            request,
            result=result,
            status=status,
            selected_draft_id=selected_draft_id,
            error=error,
            overrides=overrides,
            extra=extra,
        )
    except (TerminalUnavailable, DatabaseError):
        return _enhanced_error(
            refresh_failure_message,
            status=503,
            result="unavailable",
        )


@never_cache
@login_required
@require_POST
def checkout(request, draft_id):
    if not can_use_pos(request.user):
        raise PermissionDenied("You cannot use the POS.")
    form = CheckoutForm(request.POST)
    if not form.is_valid():
        if _is_enhanced(request):
            error = next(
                (str(item) for errors in form.errors.values() for item in errors),
                "Correct the checkout fields and try again.",
            )
            return _enhanced_workspace(
                request,
                result="invalid",
                status=422,
                selected_draft_id=draft_id,
                error=error,
                overrides={"checkout_form": form},
            )
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(_workspace_url(draft_id))
    try:
        result = complete_cash_checkout(
            request.user,
            draft_id,
            form.cleaned_data["expected_version"],
            form.cleaned_data["cash_received"],
        )
    except (DraftVersionConflict, DraftTakeoverRequired) as error:
        if _is_enhanced(request):
            return _enhanced_workspace(
                request,
                result="conflict",
                status=409,
                selected_draft_id=error.draft_id,
                error=str(error),
            )
        messages.warning(request, str(error))
        return redirect(_workspace_url(draft_id))
    except ValidationError as error:
        if _is_enhanced(request):
            message = error.messages[0] if hasattr(error, "messages") else str(error)
            return _enhanced_workspace(
                request,
                result="invalid",
                status=422,
                selected_draft_id=draft_id,
                error=message,
            )
        _message_validation_error(request, error)
        return redirect(_workspace_url(draft_id))
    except Order.DoesNotExist:
        if _is_enhanced(request):
            return _enhanced_error(
                "This order is no longer available.", status=404, result="not_found"
            )
        raise Http404 from None
    except TerminalUnavailable:
        if _is_enhanced(request):
            return _enhanced_error(
                "The configured POS terminal is unavailable.",
                status=503,
                result="unavailable",
            )
        messages.error(request, "The configured POS terminal is unavailable.")
        return redirect("sales:workspace")
    except DatabaseError:
        if _is_enhanced(request):
            return _enhanced_error(
                "Checkout failed safely. The draft was not changed.",
                status=503,
                result="unavailable",
            )
        messages.error(request, "Checkout failed safely. The draft was not changed.")
        return redirect(_workspace_url(draft_id))

    if _is_enhanced(request):
        return _enhanced_workspace(
            request,
            result="ok",
            selected_draft_id=result.replacement.pk if result.replacement else None,
            extra={
                "completed_order": {
                    "order_number": result.order.order_number,
                    "detail_url": reverse("order_history:detail", args=[result.order.order_number]),
                    "total": format(result.order.final_total, ".2f"),
                    "cash_received": format(result.payment.cash_received, ".2f"),
                    "change": format(result.payment.change_given, ".2f"),
                    "already_completed": result.already_completed,
                }
            },
            refresh_failure_message=(
                "Checkout completed, but the refreshed POS could not be loaded. "
                "Refresh before continuing."
            ),
        )

    if result.already_completed:
        messages.info(request, f"{result.order.order_number} was already completed.")
    else:
        messages.success(
            request,
            f"{result.order.order_number} completed. Order {result.replacement.slot} is ready.",
        )
    return redirect("order_history:detail", order_number=result.order.order_number)
