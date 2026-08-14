from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Lower

from apps.catalog.models import Product
from apps.core.models import Terminal

from .corrections import COMPLETED_ORDER_STATUSES
from .models import Order, OrderItem
from .policies import can_create_draft, can_use_pos


@dataclass(frozen=True)
class WorkspaceState:
    terminal: Terminal
    drafts: tuple[Order, ...]
    selected_draft: Order | None
    search_query: str
    search_results: tuple[Product, ...]
    needs_initial_draft: bool


def search_pos_products(actor, *, query, limit=50):
    if not can_use_pos(actor):
        raise PermissionDenied("You cannot use the POS.")
    normalized = (query or "").strip()
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return Product.objects.none()
    limit = min(limit, 50)
    queryset = Product.objects.filter(shop_id=actor.shop_id, is_active=True)
    if normalized:
        queryset = queryset.filter(
            Q(name__icontains=normalized)
            | Q(barcode__icontains=normalized)
            | Q(sku__icontains=normalized)
        )
    return queryset.annotate(_pos_name=Lower("name")).order_by("_pos_name", "id")[:limit]


def recent_completed_orders(actor, *, limit=3):
    if not can_use_pos(actor):
        raise PermissionDenied("You cannot use the POS.")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return Order.objects.none()
    bounded_limit = min(limit, 3)
    return (
        Order.objects.filter(
            shop_id=actor.shop_id,
            status__in=COMPLETED_ORDER_STATUSES,
            payment__isnull=False,
        )
        .select_related("completed_by", "payment")
        .order_by("-completed_at", "-id")[:bounded_limit]
    )


def load_workspace(actor, terminal, *, selected_draft_id=None, query=""):
    if not can_create_draft(actor, terminal):
        raise PermissionDenied("You cannot view this POS workspace.")

    item_queryset = OrderItem.objects.select_related("product").order_by("id")
    drafts = tuple(
        Order.objects.filter(
            shop_id=actor.shop_id,
            terminal_id=terminal.pk,
            status=Order.Status.DRAFT,
            created_by__shop_id=actor.shop_id,
            current_cashier__shop_id=actor.shop_id,
        )
        .select_related("created_by", "current_cashier", "terminal", "shop")
        .annotate(item_count=Count("items"))
        .prefetch_related(Prefetch("items", queryset=item_queryset))
        .order_by("slot")
    )

    selected = next(
        (draft for draft in drafts if str(draft.pk) == str(selected_draft_id)),
        None,
    )
    if selected is None and drafts:
        selected = max(drafts, key=lambda draft: (draft.updated_at, -draft.slot))

    normalized_query = (query or "").strip()
    results = tuple(search_pos_products(actor, query=normalized_query))
    return WorkspaceState(
        terminal=terminal,
        drafts=drafts,
        selected_draft=selected,
        search_query=normalized_query,
        search_results=results,
        needs_initial_draft=not drafts,
    )
