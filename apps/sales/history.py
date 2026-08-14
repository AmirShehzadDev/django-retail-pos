from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from .corrections import COMPLETED_ORDER_STATUSES
from .models import Order, OrderItem, SalesReturn, SalesReturnItem


def _search_amount(query):
    try:
        amount = Decimal(query)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        return None
    return amount


def completed_orders(
    actor, *, query="", has_change=False, date_from=None, date_to=None, cashier="", status=""
):
    queryset = (
        Order.objects.filter(shop_id=actor.shop_id, status__in=COMPLETED_ORDER_STATUSES)
        .select_related("completed_by", "payment")
        .annotate(item_count=Count("items", distinct=True))
        .order_by("-completed_at", "-id")
    )
    query = str(query or "").strip()
    if query:
        criteria = (
            Q(order_number__icontains=query)
            | Q(items__product_name__icontains=query)
            | Q(items__product_barcode__icontains=query)
        )
        amount = _search_amount(query)
        if amount is not None:
            criteria |= Q(subtotal=amount) | Q(final_total=amount)
        queryset = queryset.filter(criteria).distinct()
    if has_change:
        queryset = queryset.exclude(payment__change_given=Decimal("0.00"))
    if cashier:
        queryset = queryset.filter(completed_by_id=cashier)
    if status in COMPLETED_ORDER_STATUSES:
        queryset = queryset.filter(status=status)
    business_timezone = ZoneInfo(actor.shop.timezone)
    if date_from:
        start = timezone.make_aware(datetime.combine(date_from, time.min), business_timezone)
        queryset = queryset.filter(completed_at__gte=start)
    if date_to:
        end = timezone.make_aware(
            datetime.combine(date_to + timedelta(days=1), time.min), business_timezone
        )
        queryset = queryset.filter(completed_at__lt=end)
    return queryset


def paginated_completed_orders(actor, *, page=1, **filters):
    return Paginator(completed_orders(actor, **filters), 50).get_page(page)


def completed_order_detail(actor, order_number):
    normalized = str(order_number or "").strip().upper()
    return (
        Order.objects.filter(
            shop_id=actor.shop_id,
            status__in=COMPLETED_ORDER_STATUSES,
            order_number__iexact=normalized,
        )
        .select_related(
            "terminal",
            "created_by",
            "current_cashier",
            "completed_by",
            "rounding_by",
            "payment",
            "payment__processed_by",
            "void",
            "void__processed_by",
            "void__refund_payment",
        )
        .prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("product").order_by("id")),
            Prefetch(
                "returns",
                queryset=SalesReturn.objects.select_related("processed_by", "refund_payment")
                .prefetch_related(
                    Prefetch(
                        "items",
                        queryset=SalesReturnItem.objects.select_related("order_item").order_by(
                            "id"
                        ),
                    )
                )
                .order_by("created_at", "id"),
            ),
        )
        .get()
    )
