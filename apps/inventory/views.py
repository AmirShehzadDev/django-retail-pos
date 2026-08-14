from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.catalog.models import Product
from apps.catalog.policies import can_change_product_stock, can_manage_catalog

from .forms import (
    MovementFilterForm,
    ProductScanForm,
    StockAdjustmentForm,
    StockReceiptForm,
)
from .models import InventoryMovement
from .services import adjust_stock, receive_stock

WORKSPACE_HEADER = "X-Product-Workspace"


def _add_validation_error(form, error):
    if hasattr(error, "message_dict"):
        for field, errors in error.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, error)


def _require_inventory_manager(actor):
    if not can_manage_catalog(actor):
        raise PermissionDenied


def _visible_product_or_404(actor, product_id):
    product = get_object_or_404(
        Product.objects.select_related("shop").filter(shop_id=actor.shop_id),
        pk=product_id,
    )
    if not can_change_product_stock(actor, product):
        raise PermissionDenied
    return product


def _pagination_query(request):
    query = request.GET.copy()
    query.pop("page", None)
    return query.urlencode()


def _is_modal_request(request):
    return request.headers.get(WORKSPACE_HEADER) == "modal"


def _dialog_response(request, template_name, context, *, status=200):
    return JsonResponse(
        {
            "result": "invalid" if status == 422 else "ok",
            "dialog_html": render_to_string(template_name, context, request=request),
        },
        status=status,
    )


def _success_response(message):
    return JsonResponse({"result": "ok", "message": message})


@never_cache
@login_required
@require_http_methods(["GET"])
def scan(request):
    _require_inventory_manager(request.user)
    submitted = "barcode" in request.GET
    form = ProductScanForm(request.GET if submitted else None)
    if submitted and form.is_valid():
        barcode = form.cleaned_data["barcode"]
        product = Product.objects.filter(
            shop_id=request.user.shop_id,
            barcode=barcode,
        ).first()
        if product is None:
            create_url = reverse("catalog:product_create")
            return redirect(f"{create_url}?{urlencode({'barcode': barcode})}")
        if not product.is_active:
            messages.warning(
                request,
                f"{product.name} is inactive. Reactivate it before receiving stock.",
            )
            return redirect("catalog:product_detail", product_id=product.pk)
        return redirect("inventory:receive", product_id=product.pk)
    return render(request, "inventory/scan.html", {"form": form})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def receive(request, product_id):
    _require_inventory_manager(request.user)
    product = _visible_product_or_404(request.user, product_id)
    if request.method == "GET" and not product.is_active:
        if _is_modal_request(request):
            return JsonResponse(
                {
                    "result": "error",
                    "message": "Reactivate this product before receiving stock.",
                },
                status=409,
            )
        messages.warning(request, "Reactivate this product before receiving stock.")
        return redirect("catalog:product_detail", product_id=product.pk)
    form = StockReceiptForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            product, movement = receive_stock(
                actor=request.user,
                product_id=product.pk,
                quantity=form.cleaned_data["quantity"],
                note=form.cleaned_data["note"],
            )
        except ValidationError as error:
            _add_validation_error(form, error)
            product.refresh_from_db(fields=["stock_on_hand", "is_active"])
        else:
            message = (
                f"Received {movement.quantity_change} units. New stock is {product.stock_on_hand}."
            )
            if _is_modal_request(request):
                return _success_response(message)
            messages.success(request, message)
            return redirect("catalog:product_detail", product_id=product.pk)

    projected_balance = None
    if form.is_bound and not form.errors and "quantity" in form.cleaned_data:
        projected_balance = product.stock_on_hand + form.cleaned_data["quantity"]
    context = {
        "form": form,
        "product": product,
        "projected_balance": projected_balance,
    }
    if _is_modal_request(request):
        return _dialog_response(
            request,
            "inventory/_receipt_dialog.html",
            context,
            status=422 if request.method == "POST" else 200,
        )
    return render(request, "inventory/receipt_form.html", context)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def adjust(request, product_id):
    _require_inventory_manager(request.user)
    product = _visible_product_or_404(request.user, product_id)
    if request.method == "GET" and not product.is_active:
        if _is_modal_request(request):
            return JsonResponse(
                {
                    "result": "error",
                    "message": "Reactivate this product before correcting stock.",
                },
                status=409,
            )
        messages.warning(request, "Reactivate this product before correcting stock.")
        return redirect("catalog:product_detail", product_id=product.pk)
    form = StockAdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            product, movement = adjust_stock(
                actor=request.user,
                product_id=product.pk,
                quantity_change=form.cleaned_data["quantity_change"],
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as error:
            _add_validation_error(form, error)
            product.refresh_from_db(fields=["stock_on_hand", "is_active"])
        else:
            message = (
                f"Stock changed by {movement.quantity_change:+d}. New stock is "
                f"{product.stock_on_hand}."
            )
            if _is_modal_request(request):
                return _success_response(message)
            messages.success(request, message)
            return redirect("catalog:product_detail", product_id=product.pk)

    projected_balance = None
    if form.is_bound and not form.errors and "quantity_change" in form.cleaned_data:
        projected_balance = product.stock_on_hand + form.cleaned_data["quantity_change"]
    context = {
        "form": form,
        "product": product,
        "projected_balance": projected_balance,
    }
    if _is_modal_request(request):
        return _dialog_response(
            request,
            "inventory/_adjustment_dialog.html",
            context,
            status=422 if request.method == "POST" else 200,
        )
    return render(request, "inventory/adjustment_form.html", context)


@never_cache
@login_required
@require_http_methods(["GET"])
def movement_list(request):
    _require_inventory_manager(request.user)
    form = MovementFilterForm(request.GET or None)
    movements = InventoryMovement.objects.filter(shop_id=request.user.shop_id).select_related(
        "product", "actor"
    )
    q = ""
    selected_type = ""
    if form.is_valid():
        q = form.cleaned_data["q"]
        selected_type = form.cleaned_data["movement_type"]
        if q:
            movements = movements.filter(
                Q(product__name__icontains=q)
                | Q(product__barcode__icontains=q)
                | Q(product__sku__icontains=q)
            )
        if selected_type:
            movements = movements.filter(movement_type=selected_type)

    paginator = Paginator(movements.order_by("-created_at", "-id"), 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "inventory/movement_list.html",
        {
            "form": form,
            "page_obj": page_obj,
            "movements": page_obj.object_list,
            "q": q,
            "selected_type": selected_type,
            "pagination_query": _pagination_query(request),
        },
    )
