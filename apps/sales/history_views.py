import uuid
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .corrections import complete_return, returnable_items, void_order
from .forms import CompletedOrderSearchForm, ReturnForm, ReturnItemForm, VoidForm
from .history import completed_order_detail, paginated_completed_orders
from .models import Order, SalesReturnItem
from .policies import can_process_return, can_view_completed_orders, can_void_order


def _require_history(actor):
    if not can_view_completed_orders(actor):
        raise PermissionDenied("You cannot view completed orders.")


def _load_order(actor, order_number):
    try:
        return completed_order_detail(actor, order_number)
    except Order.DoesNotExist:
        raise Http404 from None


def _detail_context(actor, order):
    items = returnable_items(order)
    total_refunded = sum((row.total_refund for row in order.returns.all()), Decimal("0.00"))
    try:
        order_void = order.void
    except ObjectDoesNotExist:
        order_void = None
    if order_void:
        total_refunded += order_void.refund_payment.amount
    return {
        "order": order,
        "order_items": items,
        "order_void": order_void,
        "total_refunded": total_refunded,
        "remaining_quantity": sum(row.remaining_quantity for row in items),
        "can_return": can_process_return(actor, order),
        "can_void": can_void_order(actor, order)
        and not order.returns.exists()
        and order_void is None,
    }


@never_cache
@login_required
@require_GET
def order_list(request):
    _require_history(request.user)
    form = CompletedOrderSearchForm(request.GET, actor=request.user)
    filters = {
        "query": "",
        "has_change": False,
        "date_from": None,
        "date_to": None,
        "cashier": "",
        "status": "",
    }
    if form.is_valid():
        filters.update(
            query=form.cleaned_data["q"],
            has_change=form.cleaned_data["has_change"],
            date_from=form.cleaned_data["date_from"],
            date_to=form.cleaned_data["date_to"],
            cashier=form.cleaned_data["cashier"],
            status=form.cleaned_data["status"],
        )
    page = paginated_completed_orders(request.user, page=request.GET.get("page", 1), **filters)
    filters_query = urlencode(
        [(key, value) for key, value in request.GET.items() if key != "page" and value]
    )
    return render(
        request,
        "sales/order_list.html",
        {
            "form": form,
            "page_obj": page,
            "orders": page.object_list,
            "filters_query": filters_query,
        },
    )


@never_cache
@login_required
@require_GET
def order_detail(request, order_number):
    _require_history(request.user)
    context = _detail_context(request.user, _load_order(request.user, order_number))
    if request.headers.get("X-Order-Correction") == "detail":
        return render(request, "sales/_order_detail_content.html", context)
    return render(request, "sales/order_detail.html", context)


def _return_forms(request, items, token=None):
    bound = request.method == "POST"
    main = ReturnForm(
        request.POST if bound else None, initial=None if bound else {"request_token": token}
    )
    line_forms = []
    for item in items:
        initial = {
            "order_item_id": item.pk,
            "quantity": 0,
            "disposition": SalesReturnItem.Disposition.RESTOCK,
        }
        form = ReturnItemForm(
            request.POST if bound else None,
            prefix=f"item-{item.pk}",
            initial=initial,
            remaining_quantity=item.remaining_quantity,
        )
        form.order_item = item
        line_forms.append(form)
    return main, line_forms


def _render_return(request, context, *, status=200):
    if request.headers.get("X-Order-Correction") == "modal":
        html = render_to_string("sales/_return_dialog.html", context, request=request)
        return JsonResponse({"dialog_html": html}, status=status)
    return render(request, "sales/return_order.html", context, status=status)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def return_order(request, order_number):
    _require_history(request.user)
    order = _load_order(request.user, order_number)
    if request.method == "GET" and not can_process_return(request.user, order):
        raise PermissionDenied("This order cannot be returned.")
    items = returnable_items(order)
    form, line_forms = _return_forms(request, items, uuid.uuid4())
    context = {"order": order, "form": form, "line_forms": line_forms}
    if request.method == "GET":
        return _render_return(request, context)

    valid = form.is_valid()
    for line_form in line_forms:
        valid = line_form.is_valid() and valid
        if (
            line_form.is_valid()
            and line_form.cleaned_data["order_item_id"] != line_form.order_item.pk
        ):
            line_form.add_error(None, "The order item changed. Reload this return.")
            valid = False
    if valid:
        selections = [line_form.cleaned_data for line_form in line_forms]
        try:
            result = complete_return(
                actor=request.user,
                order_id=order.pk,
                request_token=form.cleaned_data["request_token"],
                reason=form.cleaned_data["reason"],
                selections=selections,
            )
        except ValidationError as exc:
            form.add_error(None, "; ".join(exc.messages))
            valid = False
    if valid:
        message = (
            f"{result.correction.return_number} completed. Refund PKR {result.payment.amount:.2f}."
        )
        if request.headers.get("X-Order-Correction") == "modal":
            return JsonResponse(
                {
                    "result": "ok",
                    "message": message,
                    "detail_url": order.get_absolute_url()
                    if hasattr(order, "get_absolute_url")
                    else request.build_absolute_uri(f"/orders/{order.order_number}/"),
                }
            )
        return redirect("order_history:detail", order_number=order.order_number)
    return _render_return(request, context, status=422)


def _render_void(request, context, *, status=200):
    if request.headers.get("X-Order-Correction") == "modal":
        html = render_to_string("sales/_void_dialog.html", context, request=request)
        return JsonResponse({"dialog_html": html}, status=status)
    return render(request, "sales/void_order.html", context, status=status)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def void_order_view(request, order_number):
    _require_history(request.user)
    order = _load_order(request.user, order_number)
    if not can_void_order(request.user, order):
        raise PermissionDenied("You cannot void this order.")
    form = VoidForm(
        request.POST if request.method == "POST" else None, initial={"request_token": uuid.uuid4()}
    )
    context = {"order": order, "form": form}
    if request.method == "GET":
        return _render_void(request, context)
    if form.is_valid():
        try:
            result = void_order(
                actor=request.user,
                order_id=order.pk,
                request_token=form.cleaned_data["request_token"],
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            form.add_error(None, "; ".join(exc.messages))
        else:
            message = f"{order.order_number} voided. Refund PKR {result.payment.amount:.2f}."
            if request.headers.get("X-Order-Correction") == "modal":
                return JsonResponse(
                    {
                        "result": "ok",
                        "message": message,
                        "detail_url": request.build_absolute_uri(f"/orders/{order.order_number}/"),
                    }
                )
            return redirect("order_history:detail", order_number=order.order_number)
    return _render_void(request, context, status=422)
