from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.catalog.models import Product

from .exceptions import (
    BarcodeNowKnown,
    DraftLimitReached,
    DraftTakeoverRequired,
    DraftVersionConflict,
    QuickCreateContextInvalid,
    TerminalUnavailable,
)
from .forms import (
    AddProductForm,
    BarcodeScanForm,
    CheckoutForm,
    NewDraftForm,
    PosProductSearchForm,
    QuantityForm,
    QuickCreateProductForm,
    StartWorkspaceForm,
    VersionedActionForm,
)
from .models import Order, OrderItem
from .policies import can_edit_draft, can_take_over_draft, can_use_pos
from .queries import load_workspace, recent_completed_orders
from .services import (
    POSTGRESQL_POSITIVE_BIGINT_MAX,
    add_product,
    clear_draft,
    close_empty_draft,
    create_draft,
    quick_create_and_add,
    remove_item,
    scan_barcode,
    set_item_quantity,
    start_workspace,
    take_over_draft,
)
from .signing import create_quick_create_context, read_quick_create_context
from .terminals import resolve_pos_terminal

ENHANCED_HEADER = "X-POS-Enhanced"
ENHANCED_HEADER_VALUE = "1"


def _require_pos(actor):
    if not can_use_pos(actor):
        raise PermissionDenied("You cannot use the POS.")


def _is_enhanced(request):
    return request.headers.get(ENHANCED_HEADER) == ENHANCED_HEADER_VALUE


def _workspace_url(draft_id=None, *, query=""):
    parameters = {}
    if draft_id is not None:
        parameters["draft"] = str(draft_id)
    if query:
        parameters["q"] = query
    url = reverse("sales:workspace")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _session_key(request):
    session_key = request.session.session_key
    if not session_key:
        raise QuickCreateContextInvalid("The quick-create session is unavailable.")
    return session_key


def _add_validation_error(form, error):
    if hasattr(error, "message_dict"):
        for field, errors in error.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, error)


def _message_validation_error(request, error):
    if hasattr(error, "messages"):
        for error_message in error.messages:
            messages.error(request, error_message)
    else:
        messages.error(request, str(error))


def _workspace_context(request, *, selected_draft_id=None, query="", overrides=None):
    terminal = resolve_pos_terminal(request.user)
    state = load_workspace(
        request.user,
        terminal,
        selected_draft_id=selected_draft_id,
        query=query,
    )
    selected = state.selected_draft
    selected_version = str(selected.version) if selected else ""
    line_controls = ()
    search_product_forms = ()
    selected_shortages = ()
    checkout_total = "0.00"
    if selected:
        line_controls = tuple(
            {
                "item": item,
                "decreased_quantity": item.quantity - 1 if item.quantity > 1 else None,
                "increased_quantity": (
                    item.quantity + 1
                    if item.product.is_active and item.quantity < POSTGRESQL_POSITIVE_BIGINT_MAX
                    else None
                ),
                "quantity_form": QuantityForm(
                    initial={"quantity": str(item.quantity), "expected_version": selected_version}
                ),
                "remove_form": VersionedActionForm(initial={"expected_version": selected_version}),
            }
            for item in selected.items.all()
        )
        search_product_forms = tuple(
            {
                "product": product,
                "form": AddProductForm(
                    initial={"product_id": str(product.pk), "expected_version": selected_version}
                ),
            }
            for product in state.search_results
        )
        selected_shortages = tuple(
            {
                "product": item.product,
                "item": item,
                "projected": item.product.stock_on_hand - item.quantity,
            }
            for item in selected.items.all()
            if item.product.stock_on_hand - item.quantity < 0
        )
        checkout_total = format(selected.subtotal, ".2f")

    can_edit_selected = bool(selected and can_edit_draft(request.user, selected, terminal))
    context = {
        "workspace": state,
        "terminal": state.terminal,
        "drafts": state.drafts,
        "selected_draft": selected,
        "selected_draft_id": str(selected.pk) if selected else "",
        "selected_version": selected_version,
        "search_query": state.search_query,
        "search_results": state.search_results,
        "needs_initial_draft": state.needs_initial_draft,
        "can_create_draft": len(state.drafts) < 3,
        "can_edit_selected": can_edit_selected,
        "can_close_selected_tab": bool(
            can_edit_selected and selected.item_count == 0 and len(state.drafts) > 1
        ),
        "can_take_over_selected": bool(
            selected and can_take_over_draft(request.user, selected, terminal)
        ),
        "start_form": StartWorkspaceForm(),
        "new_draft_form": NewDraftForm(),
        "search_form": PosProductSearchForm(initial={"q": state.search_query}),
        "scan_form": BarcodeScanForm(initial={"expected_version": selected_version}),
        "search_product_forms": search_product_forms,
        "line_controls": line_controls,
        "checkout_form": CheckoutForm(
            initial={"expected_version": selected_version, "cash_received": checkout_total}
        ),
        "checkout_total": checkout_total,
        "selected_shortages": selected_shortages,
        "recent_completed_orders": tuple(recent_completed_orders(request.user)),
        "takeover_form": VersionedActionForm(initial={"expected_version": selected_version}),
        "clear_form": VersionedActionForm(initial={"expected_version": selected_version}),
        "close_form": VersionedActionForm(initial={"expected_version": selected_version}),
        "enhanced_header": ENHANCED_HEADER,
        "enhanced_header_value": ENHANCED_HEADER_VALUE,
    }
    if overrides:
        context.update(overrides)
    return context


def _scoped_workspace_context(request, draft_id, *, overrides=None):
    context = _workspace_context(
        request,
        selected_draft_id=draft_id,
        overrides=overrides,
    )
    if not any(draft.pk == draft_id for draft in context["drafts"]):
        raise Http404
    return context


def _require_scoped_item(context, item_id):
    if not any(item.pk == item_id for item in context["selected_draft"].items.all()):
        raise Http404


def _enhanced_state(
    request,
    *,
    result,
    status=200,
    selected_draft_id=None,
    error="",
    overrides=None,
    extra=None,
):
    context = _workspace_context(
        request,
        selected_draft_id=selected_draft_id,
        overrides=overrides,
    )
    selected = context["selected_draft"]
    payload = {
        "result": result,
        "draft_id": str(selected.pk) if selected else "",
        "version": str(selected.version) if selected else "",
        "can_create_draft": context["can_create_draft"],
        "tabs_html": render_to_string("sales/partials/draft_tabs.html", context, request=request),
        "draft_panel_html": render_to_string(
            "sales/partials/draft_panel.html", context, request=request
        ),
    }
    if error:
        payload["error"] = error
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _terminal_failure(request, *, database_failure=False):
    message = (
        "The POS could not complete that request. Refresh and try again."
        if database_failure
        else "The configured POS terminal is unavailable."
    )
    if _is_enhanced(request):
        return JsonResponse({"result": "unavailable", "error": message}, status=503)
    return render(
        request,
        "sales/terminal_unavailable.html",
        {"terminal_error_message": message},
        status=503,
    )


def _enhanced_conflict(request, error, *, draft_id=None, result="conflict", extra=None):
    try:
        return _enhanced_state(
            request,
            result=result,
            status=409,
            selected_draft_id=draft_id,
            error=str(error),
            extra=extra,
        )
    except TerminalUnavailable:
        return _terminal_failure(request)


def _normal_conflict(request, error, *, draft_id=None):
    messages.warning(request, str(error))
    return redirect(_workspace_url(draft_id))


def _invalid_mutation(request, form, *, draft_id, form_key):
    if _is_enhanced(request):
        try:
            return _enhanced_state(
                request,
                result="invalid",
                status=422,
                selected_draft_id=draft_id,
                error="Correct the highlighted fields and try again.",
                overrides={form_key: form},
            )
        except TerminalUnavailable:
            return _terminal_failure(request)
    for error in form.errors.values():
        for error_message in error:
            messages.error(request, error_message)
    return redirect(_workspace_url(draft_id))


@never_cache
@login_required
@require_GET
def workspace(request):
    _require_pos(request.user)
    search_form = PosProductSearchForm(request.GET)
    query = ""
    if search_form.is_valid():
        query = search_form.cleaned_data["q"]
    try:
        context = _workspace_context(
            request,
            selected_draft_id=request.GET.get("draft"),
            query=query,
            overrides={"search_form": search_form},
        )
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    return render(request, "sales/pos_workspace.html", context)


@never_cache
@login_required
@require_POST
def start_workspace_view(request):
    _require_pos(request.user)
    form = StartWorkspaceForm(request.POST)
    if not form.is_valid():
        return _invalid_mutation(request, form, draft_id=None, form_key="start_form")
    try:
        draft = start_workspace(request.user)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    if _is_enhanced(request):
        return _enhanced_state(request, result="ok", selected_draft_id=draft.pk)
    messages.success(request, "Order 1 is ready.")
    return redirect(_workspace_url(draft.pk))


@never_cache
@login_required
@require_POST
def draft_create(request):
    _require_pos(request.user)
    form = NewDraftForm(request.POST)
    if not form.is_valid():
        return _invalid_mutation(request, form, draft_id=None, form_key="new_draft_form")
    try:
        draft = create_draft(request.user)
    except DraftLimitReached as error:
        if _is_enhanced(request):
            return _enhanced_conflict(request, error, result="draft_limit")
        return _normal_conflict(request, error)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    if _is_enhanced(request):
        return _enhanced_state(request, result="ok", selected_draft_id=draft.pk)
    messages.success(request, f"Order {draft.slot} was created.")
    return redirect(_workspace_url(draft.pk))


@never_cache
@login_required
@require_POST
def draft_scan(request, draft_id):
    _require_pos(request.user)
    try:
        scoped_context = _scoped_workspace_context(request, draft_id)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    form = BarcodeScanForm(request.POST)
    if not form.is_valid():
        return _invalid_mutation(request, form, draft_id=draft_id, form_key="scan_form")
    try:
        outcome = scan_barcode(
            request.user,
            draft_id,
            form.cleaned_data["expected_version"],
            form.cleaned_data["barcode"],
        )
        if outcome.is_unknown:
            token = create_quick_create_context(
                request.user,
                scoped_context["terminal"],
                scoped_context["selected_draft"],
                outcome.barcode,
                session_key=_session_key(request),
            )
            next_url = reverse("sales:quick_create", kwargs={"draft_id": outcome.draft_id})
            next_url = f"{next_url}?{urlencode({'context': token})}"
            if _is_enhanced(request):
                return JsonResponse(
                    {
                        "result": "quick_create_required",
                        "draft_id": str(outcome.draft_id),
                        "version": str(outcome.version),
                        "next_url": next_url,
                    }
                )
            return redirect(next_url)
    except DraftVersionConflict as error:
        if _is_enhanced(request):
            return _enhanced_conflict(request, error, draft_id=error.draft_id)
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except DraftTakeoverRequired as error:
        if _is_enhanced(request):
            return _enhanced_conflict(
                request, error, draft_id=error.draft_id, result="takeover_required"
            )
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except (Order.DoesNotExist, Product.DoesNotExist):
        raise Http404 from None
    except ValidationError as error:
        _add_validation_error(form, error)
        return _invalid_mutation(request, form, draft_id=draft_id, form_key="scan_form")
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    if _is_enhanced(request):
        return _enhanced_state(request, result="ok", selected_draft_id=outcome.draft_id)
    messages.success(request, "Product added to the order.")
    return redirect(_workspace_url(outcome.draft_id))


@never_cache
@login_required
@require_POST
def draft_add_product(request, draft_id):
    _require_pos(request.user)
    try:
        _scoped_workspace_context(request, draft_id)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    form = AddProductForm(request.POST)
    if not form.is_valid():
        return _invalid_mutation(request, form, draft_id=draft_id, form_key="add_product_form")
    try:
        draft = add_product(
            request.user,
            draft_id,
            form.cleaned_data["expected_version"],
            form.cleaned_data["product_id"],
        )
    except DraftVersionConflict as error:
        if _is_enhanced(request):
            return _enhanced_conflict(request, error, draft_id=error.draft_id)
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except DraftTakeoverRequired as error:
        if _is_enhanced(request):
            return _enhanced_conflict(
                request, error, draft_id=error.draft_id, result="takeover_required"
            )
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except (Order.DoesNotExist, Product.DoesNotExist):
        raise Http404 from None
    except ValidationError as error:
        _add_validation_error(form, error)
        return _invalid_mutation(request, form, draft_id=draft_id, form_key="add_product_form")
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    if _is_enhanced(request):
        return _enhanced_state(request, result="ok", selected_draft_id=draft.pk)
    messages.success(request, "Product added to the order.")
    return redirect(_workspace_url(draft.pk))


def _read_quick_create(request, draft_id, token):
    resolve_pos_terminal(request.user)
    context = read_quick_create_context(
        token,
        request.user,
        session_key=_session_key(request),
    )
    if context.draft_id != draft_id:
        raise Http404
    workspace_context = _scoped_workspace_context(request, draft_id)
    return context, workspace_context


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def quick_create(request, draft_id):
    _require_pos(request.user)
    token = request.POST.get("context") if request.method == "POST" else request.GET.get("context")
    try:
        signed_context, workspace_context = _read_quick_create(request, draft_id, token)
    except Http404:
        raise
    except QuickCreateContextInvalid as error:
        if _is_enhanced(request):
            try:
                return _enhanced_state(
                    request,
                    result="invalid_context",
                    status=422,
                    selected_draft_id=draft_id,
                    error=str(error),
                )
            except TerminalUnavailable:
                return _terminal_failure(request)
        messages.error(request, "That quick-create request expired or changed. Scan again.")
        return redirect(_workspace_url(draft_id))
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)

    form = QuickCreateProductForm(
        request.POST if request.method == "POST" else None,
        initial={"context": token},
    )
    page_context = {
        "form": form,
        "barcode": signed_context.barcode,
        "draft": workspace_context["selected_draft"],
        "terminal": workspace_context["terminal"],
    }
    if request.method == "POST" and form.is_valid():
        try:
            product, draft = quick_create_and_add(
                request.user,
                signed_context.draft_id,
                signed_context.expected_version,
                signed_context.barcode,
                form.cleaned_data["name"],
                form.cleaned_data["selling_price"],
            )
        except BarcodeNowKnown as error:
            guidance = (
                "That barcode now belongs to an existing product. Add it from the current catalog."
                if error.is_active
                else "That barcode now belongs to an inactive product and cannot be added."
            )
            if _is_enhanced(request):
                return _enhanced_conflict(
                    request,
                    guidance,
                    draft_id=draft_id,
                    result="barcode_now_known",
                    extra={
                        "known_product_id": str(error.product_id),
                        "known_product_active": error.is_active,
                    },
                )
            messages.warning(request, guidance)
            return redirect(_workspace_url(draft_id))
        except DraftVersionConflict as error:
            if _is_enhanced(request):
                return _enhanced_conflict(request, error, draft_id=error.draft_id)
            return _normal_conflict(request, error, draft_id=error.draft_id)
        except DraftTakeoverRequired as error:
            if _is_enhanced(request):
                return _enhanced_conflict(
                    request, error, draft_id=error.draft_id, result="takeover_required"
                )
            return _normal_conflict(request, error, draft_id=error.draft_id)
        except (Order.DoesNotExist, Product.DoesNotExist):
            raise Http404 from None
        except ValidationError as error:
            _add_validation_error(form, error)
        except TerminalUnavailable:
            return _terminal_failure(request)
        except DatabaseError:
            return _terminal_failure(request, database_failure=True)
        else:
            if _is_enhanced(request):
                return _enhanced_state(request, result="ok", selected_draft_id=draft.pk)
            messages.success(request, f"{product.name} was created and added to the order.")
            return redirect(_workspace_url(draft.pk))

    if request.method == "POST" and _is_enhanced(request):
        return JsonResponse(
            {
                "result": "invalid",
                "draft_id": str(draft_id),
                "version": str(signed_context.expected_version),
                "quick_create_html": render_to_string(
                    "sales/quick_create.html", page_context, request=request
                ),
            },
            status=422,
        )
    return render(request, "sales/quick_create.html", page_context)


@never_cache
@login_required
@require_POST
def item_quantity(request, draft_id, item_id):
    _require_pos(request.user)
    try:
        scoped_context = _scoped_workspace_context(request, draft_id)
        _require_scoped_item(scoped_context, item_id)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    form = QuantityForm(request.POST)
    if not form.is_valid():
        return _invalid_mutation(request, form, draft_id=draft_id, form_key="quantity_form")
    try:
        draft = set_item_quantity(
            request.user,
            draft_id,
            form.cleaned_data["expected_version"],
            item_id,
            form.cleaned_data["quantity"],
        )
    except DraftVersionConflict as error:
        if _is_enhanced(request):
            return _enhanced_conflict(request, error, draft_id=error.draft_id)
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except DraftTakeoverRequired as error:
        if _is_enhanced(request):
            return _enhanced_conflict(
                request, error, draft_id=error.draft_id, result="takeover_required"
            )
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except (Order.DoesNotExist, OrderItem.DoesNotExist):
        raise Http404 from None
    except ValidationError as error:
        _add_validation_error(form, error)
        return _invalid_mutation(request, form, draft_id=draft_id, form_key="quantity_form")
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    if _is_enhanced(request):
        return _enhanced_state(request, result="ok", selected_draft_id=draft.pk)
    messages.success(request, "Quantity updated.")
    return redirect(_workspace_url(draft.pk))


@never_cache
@login_required
@require_POST
def item_remove(request, draft_id, item_id):
    _require_pos(request.user)
    try:
        scoped_context = _scoped_workspace_context(request, draft_id)
        _require_scoped_item(scoped_context, item_id)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    form = VersionedActionForm(request.POST)
    if not form.is_valid():
        return _invalid_mutation(request, form, draft_id=draft_id, form_key="remove_form")
    try:
        draft = remove_item(
            request.user,
            draft_id,
            form.cleaned_data["expected_version"],
            item_id,
        )
    except DraftVersionConflict as error:
        if _is_enhanced(request):
            return _enhanced_conflict(request, error, draft_id=error.draft_id)
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except DraftTakeoverRequired as error:
        if _is_enhanced(request):
            return _enhanced_conflict(
                request, error, draft_id=error.draft_id, result="takeover_required"
            )
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except (Order.DoesNotExist, OrderItem.DoesNotExist):
        raise Http404 from None
    except ValidationError as error:
        _message_validation_error(request, error)
        if _is_enhanced(request):
            return _enhanced_state(
                request,
                result="invalid",
                status=422,
                selected_draft_id=draft_id,
                error=str(error),
            )
        return redirect(_workspace_url(draft_id))
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    if _is_enhanced(request):
        return _enhanced_state(request, result="ok", selected_draft_id=draft.pk)
    messages.success(request, "Product removed from the order.")
    return redirect(_workspace_url(draft.pk))


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def draft_takeover(request, draft_id):
    _require_pos(request.user)
    try:
        context = _scoped_workspace_context(request, draft_id)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    draft = context["selected_draft"]
    form = VersionedActionForm(
        request.POST if request.method == "POST" else None,
        initial={"expected_version": str(draft.version)},
    )
    if request.method == "POST" and form.is_valid():
        try:
            draft = take_over_draft(
                request.user,
                draft_id,
                form.cleaned_data["expected_version"],
            )
        except DraftVersionConflict as error:
            if _is_enhanced(request):
                return _enhanced_conflict(request, error, draft_id=error.draft_id)
            return _normal_conflict(request, error, draft_id=error.draft_id)
        except Order.DoesNotExist:
            raise Http404 from None
        except (PermissionDenied, ValidationError) as error:
            if isinstance(error, PermissionDenied):
                raise
            _add_validation_error(form, error)
        except TerminalUnavailable:
            return _terminal_failure(request)
        except DatabaseError:
            return _terminal_failure(request, database_failure=True)
        else:
            if _is_enhanced(request):
                return _enhanced_state(request, result="ok", selected_draft_id=draft.pk)
            messages.success(request, f"Order {draft.slot} is now assigned to you.")
            return redirect(_workspace_url(draft.pk))
    if request.method == "POST" and _is_enhanced(request):
        return _enhanced_state(
            request,
            result="invalid",
            status=422,
            selected_draft_id=draft_id,
            error="The order could not be resumed.",
            overrides={"takeover_form": form},
        )
    return render(
        request,
        "sales/takeover_confirm.html",
        {**context, "draft": draft, "form": form},
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def draft_clear(request, draft_id):
    _require_pos(request.user)
    try:
        context = _scoped_workspace_context(request, draft_id)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    draft = context["selected_draft"]
    if not can_edit_draft(request.user, draft, context["terminal"]):
        raise PermissionDenied("Only the current cashier can clear this order.")
    if request.method == "GET" and draft.item_count == 0:
        messages.warning(request, "This order is already empty.")
        return redirect(_workspace_url(draft.pk))
    form = VersionedActionForm(
        request.POST if request.method == "POST" else None,
        initial={"expected_version": str(draft.version)},
    )
    if request.method == "POST" and form.is_valid():
        try:
            draft = clear_draft(
                request.user,
                draft_id,
                form.cleaned_data["expected_version"],
            )
        except DraftVersionConflict as error:
            if _is_enhanced(request):
                return _enhanced_conflict(request, error, draft_id=error.draft_id)
            return _normal_conflict(request, error, draft_id=error.draft_id)
        except DraftTakeoverRequired as error:
            if _is_enhanced(request):
                return _enhanced_conflict(
                    request, error, draft_id=error.draft_id, result="takeover_required"
                )
            return _normal_conflict(request, error, draft_id=error.draft_id)
        except Order.DoesNotExist:
            raise Http404 from None
        except ValidationError as error:
            _add_validation_error(form, error)
        except TerminalUnavailable:
            return _terminal_failure(request)
        except DatabaseError:
            return _terminal_failure(request, database_failure=True)
        else:
            if _is_enhanced(request):
                return _enhanced_state(request, result="ok", selected_draft_id=draft.pk)
            messages.success(request, f"Order {draft.slot} was cleared.")
            return redirect(_workspace_url(draft.pk))
    if request.method == "POST" and _is_enhanced(request):
        return _enhanced_state(
            request,
            result="invalid",
            status=422,
            selected_draft_id=draft_id,
            error="The order could not be cleared.",
            overrides={"clear_form": form},
        )
    return render(
        request,
        "sales/clear_confirm.html",
        {
            **context,
            "draft": draft,
            "form": form,
        },
    )


@never_cache
@login_required
@require_POST
def draft_close(request, draft_id):
    _require_pos(request.user)
    try:
        context = _scoped_workspace_context(request, draft_id)
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    draft = context["selected_draft"]
    if not can_edit_draft(request.user, draft, context["terminal"]):
        raise PermissionDenied("Only the current cashier can close this tab.")
    form = VersionedActionForm(request.POST)
    if not form.is_valid():
        return _invalid_mutation(request, form, draft_id=draft_id, form_key="close_form")
    try:
        selected = close_empty_draft(
            request.user,
            draft_id,
            form.cleaned_data["expected_version"],
        )
    except DraftVersionConflict as error:
        if _is_enhanced(request):
            return _enhanced_conflict(request, error, draft_id=error.draft_id)
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except DraftTakeoverRequired as error:
        if _is_enhanced(request):
            return _enhanced_conflict(
                request, error, draft_id=error.draft_id, result="takeover_required"
            )
        return _normal_conflict(request, error, draft_id=error.draft_id)
    except Order.DoesNotExist:
        raise Http404 from None
    except ValidationError as error:
        if _is_enhanced(request):
            return _enhanced_state(
                request,
                result="invalid",
                status=422,
                selected_draft_id=draft_id,
                error=error.messages[0] if error.messages else "The tab could not be closed.",
            )
        _message_validation_error(request, error)
        return redirect(_workspace_url(draft_id))
    except TerminalUnavailable:
        return _terminal_failure(request)
    except DatabaseError:
        return _terminal_failure(request, database_failure=True)
    if _is_enhanced(request):
        return _enhanced_state(request, result="ok", selected_draft_id=selected.pk)
    messages.success(request, f"Order {draft.slot} tab was closed.")
    return redirect(_workspace_url(selected.pk))
