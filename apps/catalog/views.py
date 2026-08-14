from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ProductCreateForm, ProductForm, ProductSearchForm
from .models import Product
from .policies import (
    can_edit_product,
    can_manage_catalog,
    can_view_catalog,
    can_view_product,
)
from .services import (
    create_product_with_optional_receipt,
    mark_product_reviewed,
    set_product_active,
    update_product,
)

WORKSPACE_HEADER = "X-Product-Workspace"


def _require_catalog_manager(actor):
    if not can_manage_catalog(actor):
        raise PermissionDenied


def _require_catalog_viewer(actor):
    if not can_view_catalog(actor):
        raise PermissionDenied


def _visible_product_or_404(actor, product_id):
    products = Product.objects.filter(shop_id=actor.shop_id)
    if can_manage_catalog(actor):
        products = products.select_related("shop", "created_by")
    product = get_object_or_404(products, pk=product_id)
    if not can_view_product(actor, product):
        raise Http404
    return product


def _add_validation_error(form, error):
    if hasattr(error, "message_dict"):
        for field, errors in error.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, error)


def _workspace_mode(request):
    return request.headers.get(WORKSPACE_HEADER, "")


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


def _product_list_context(request):
    is_catalog_manager = can_manage_catalog(request.user)
    products = Product.objects.filter(shop_id=request.user.shop_id)
    form = ProductSearchForm(request.GET)
    form.is_valid()
    q = form.cleaned_data.get("q", "")
    status = form.cleaned_data.get("status", "")
    negative = form.cleaned_data.get("negative", False)
    needs_review = form.cleaned_data.get("needs_review", False) if is_catalog_manager else False

    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(barcode__icontains=q) | Q(sku__icontains=q)
        )
    if status == "active":
        products = products.filter(is_active=True)
    elif status == "inactive":
        products = products.filter(is_active=False)
    if negative:
        products = products.filter(stock_on_hand__lt=0)
    if needs_review:
        products = products.filter(needs_review=True)

    products = products.order_by(Lower("name"), "id")
    page_obj = Paginator(products, 50).get_page(request.GET.get("page"))
    preserved = request.GET.copy()
    preserved.pop("page", None)
    if not is_catalog_manager:
        preserved.pop("needs_review", None)
    offer_create_barcode = ""
    if is_catalog_manager and q and len(q) <= 64 and not page_obj.object_list:
        exact_barcode_exists = Product.objects.filter(
            shop_id=request.user.shop_id,
            barcode=q,
        ).exists()
        if not exact_barcode_exists:
            offer_create_barcode = q
    return {
        "filter_form": form,
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "query_string": preserved.urlencode(),
        "q": q,
        "selected_status": status,
        "negative": negative,
        "needs_review": needs_review,
        "is_catalog_manager": is_catalog_manager,
        "offer_create_barcode": offer_create_barcode,
    }


@never_cache
@login_required
@require_http_methods(["GET"])
def product_list(request):
    _require_catalog_viewer(request.user)
    context = _product_list_context(request)
    if _workspace_mode(request) == "results":
        return render(request, "catalog/_product_results.html", context)
    return render(request, "catalog/product_list.html", context)


@never_cache
@login_required
@require_http_methods(["GET"])
def product_lookup(request):
    _require_catalog_viewer(request.user)
    q = request.GET.get("q", "").strip()
    product = None
    if q and len(q) <= 64:
        product = Product.objects.filter(shop_id=request.user.shop_id, barcode=q).first()

    if product is not None:
        if can_manage_catalog(request.user) and product.is_active:
            destination = reverse("inventory:receive", args=[product.pk])
        else:
            destination = reverse("catalog:product_detail", args=[product.pk])
        if _workspace_mode(request) == "lookup":
            return JsonResponse({"result": "modal", "url": destination})
        if can_manage_catalog(request.user) and not product.is_active:
            messages.warning(
                request,
                f"{product.name} is inactive. Reactivate it before changing stock.",
            )
        return redirect(destination)

    list_url = reverse("catalog:product_list")
    if q:
        list_url = f"{list_url}?{request.GET.urlencode()}"
    if _workspace_mode(request) == "lookup":
        return JsonResponse({"result": "search", "url": list_url})
    return redirect(list_url)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def product_create(request):
    _require_catalog_manager(request.user)
    initial = {}
    if request.method == "GET":
        initial["barcode"] = request.GET.get("barcode", "")
    form = ProductCreateForm(request.POST or None, initial=initial, shop=request.user.shop)
    if request.method == "POST" and form.is_valid():
        try:
            product, movement = create_product_with_optional_receipt(
                actor=request.user,
                name=form.cleaned_data["name"],
                barcode=form.cleaned_data["barcode"],
                sku=form.cleaned_data["sku"],
                selling_price=form.cleaned_data["selling_price"],
                cost_price=form.cleaned_data["cost_price"],
                quantity_received_now=form.cleaned_data["quantity_received_now"],
                receipt_note=form.cleaned_data["receipt_note"],
            )
        except ValidationError as error:
            _add_validation_error(form, error)
        else:
            if movement is None:
                message = f"Product {product.name} was created at zero stock."
            else:
                message = (
                    f"Product {product.name} was created and {movement.quantity_change} units "
                    f"were received. Stock is {product.stock_on_hand}."
                )
            if _workspace_mode(request) == "modal":
                return _success_response(message)
            messages.success(request, message)
            return redirect("catalog:product_detail", product_id=product.pk)
    context = {
        "form": form,
        "page_title": "Create product",
        "submit_label": "Create product",
    }
    if _workspace_mode(request) == "modal":
        return _dialog_response(
            request,
            "catalog/_product_form_dialog.html",
            context,
            status=422 if request.method == "POST" else 200,
        )
    return render(request, "catalog/product_form.html", context)


@never_cache
@login_required
@require_http_methods(["GET"])
def product_detail(request, product_id):
    _require_catalog_viewer(request.user)
    product = _visible_product_or_404(request.user, product_id)
    is_catalog_manager = can_manage_catalog(request.user)
    if not is_catalog_manager:
        if _workspace_mode(request) == "modal":
            return _dialog_response(
                request,
                "catalog/_product_detail_dialog.html",
                {"product": product, "is_catalog_manager": False},
            )
        return render(
            request,
            "catalog/product_detail_readonly.html",
            {"product": product, "is_catalog_manager": False},
        )
    recent_movements = product.movements.select_related("actor").order_by("-created_at", "-id")[:20]
    context = {
        "product": product,
        "recent_movements": recent_movements,
        "can_edit": can_edit_product(request.user, product),
        "is_catalog_manager": True,
    }
    if _workspace_mode(request) == "modal":
        return _dialog_response(request, "catalog/_product_detail_dialog.html", context)
    return render(request, "catalog/product_detail.html", context)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def product_edit(request, product_id):
    _require_catalog_manager(request.user)
    product = _visible_product_or_404(request.user, product_id)
    if not can_edit_product(request.user, product):
        raise PermissionDenied
    form = ProductForm(request.POST or None, instance=product, shop=request.user.shop)
    if request.method == "POST" and form.is_valid():
        try:
            product, _ = update_product(
                actor=request.user,
                product_id=product.pk,
                **form.cleaned_data,
            )
        except ValidationError as error:
            _add_validation_error(form, error)
        else:
            message = f"Product {product.name} was updated."
            if _workspace_mode(request) == "modal":
                return _success_response(message)
            messages.success(request, message)
            return redirect("catalog:product_detail", product_id=product.pk)
    context = {
        "form": form,
        "product": product,
        "page_title": "Edit product",
        "submit_label": "Save changes",
    }
    if _workspace_mode(request) == "modal":
        return _dialog_response(
            request,
            "catalog/_product_form_dialog.html",
            context,
            status=422 if request.method == "POST" else 200,
        )
    return render(request, "catalog/product_form.html", context)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def product_status(request, product_id):
    _require_catalog_manager(request.user)
    product = _visible_product_or_404(request.user, product_id)
    if not can_edit_product(request.user, product):
        raise PermissionDenied
    if request.method == "POST":
        product, _ = set_product_active(
            actor=request.user,
            product_id=product.pk,
            is_active=not product.is_active,
        )
        state = "reactivated" if product.is_active else "deactivated"
        message = f"Product {product.name} was {state}."
        if _workspace_mode(request) == "modal":
            return _success_response(message)
        messages.success(request, message)
        return redirect("catalog:product_detail", product_id=product.pk)
    if _workspace_mode(request) == "modal":
        return _dialog_response(
            request,
            "catalog/_product_status_dialog.html",
            {"product": product},
        )
    return render(request, "catalog/product_status.html", {"product": product})


@never_cache
@login_required
@require_POST
def product_review(request, product_id):
    _require_catalog_manager(request.user)
    product = _visible_product_or_404(request.user, product_id)
    if not can_edit_product(request.user, product):
        raise PermissionDenied
    product, changed = mark_product_reviewed(actor=request.user, product_id=product.pk)
    if changed:
        message = f"Product {product.name} was marked reviewed."
    else:
        message = f"Product {product.name} is already reviewed."
    if _workspace_mode(request) == "modal":
        return _success_response(message)
    if changed:
        messages.success(request, message)
    else:
        messages.info(request, message)
    return redirect("catalog:product_detail", product_id=product.pk)
