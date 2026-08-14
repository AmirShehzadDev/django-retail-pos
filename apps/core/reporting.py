import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.catalog.models import Product
from apps.sales.models import Payment

from .models import AuditEvent

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class DailySummary:
    business_date: date
    gross_sales: Decimal
    returns: Decimal
    voids: Decimal
    net_sales: Decimal
    order_count: int
    cash_collected: Decimal
    cash_refunded: Decimal
    nonzero_change_count: int
    signed_change_total: Decimal
    gross_reconciliation: Decimal
    net_cash_movement: Decimal


@dataclass(frozen=True)
class ReviewCounts:
    negative_stock: int
    quick_created_needing_review: int


def business_day_bounds(shop, business_date):
    business_timezone = ZoneInfo(shop.timezone)
    start = timezone.make_aware(datetime.combine(business_date, time.min), business_timezone)
    end = timezone.make_aware(
        datetime.combine(business_date + timedelta(days=1), time.min), business_timezone
    )
    return start, end


def daily_summary(actor, business_date):
    start, end = business_day_bounds(actor.shop, business_date)
    day_payments = Payment.objects.filter(
        shop_id=actor.shop_id,
        processed_at__gte=start,
        processed_at__lt=end,
    )
    receipts = day_payments.filter(
        direction=Payment.Direction.RECEIPT,
        order__isnull=False,
    )
    refunds = day_payments.filter(direction=Payment.Direction.REFUND)
    receipt_totals = receipts.aggregate(
        gross_sales=Sum("amount"),
        cash_collected=Sum("cash_received"),
        signed_change_total=Sum("change_given"),
        order_count=Count("id"),
        nonzero_change_count=Count("id", filter=~Q(change_given=ZERO)),
    )
    refund_totals = refunds.aggregate(
        returns=Sum("amount", filter=Q(sales_return__isnull=False)),
        voids=Sum("amount", filter=Q(order_void__isnull=False)),
    )

    gross_sales = receipt_totals["gross_sales"] or ZERO
    return_total = refund_totals["returns"] or ZERO
    void_total = refund_totals["voids"] or ZERO
    cash_collected = receipt_totals["cash_collected"] or ZERO
    signed_change_total = receipt_totals["signed_change_total"] or ZERO
    cash_refunded = return_total + void_total

    return DailySummary(
        business_date=business_date,
        gross_sales=gross_sales,
        returns=return_total,
        voids=void_total,
        net_sales=gross_sales - cash_refunded,
        order_count=receipt_totals["order_count"],
        cash_collected=cash_collected,
        cash_refunded=cash_refunded,
        nonzero_change_count=receipt_totals["nonzero_change_count"],
        signed_change_total=signed_change_total,
        gross_reconciliation=cash_collected - signed_change_total,
        net_cash_movement=cash_collected - signed_change_total - cash_refunded,
    )


def current_review_counts(actor):
    products = Product.objects.filter(shop_id=actor.shop_id)
    totals = products.aggregate(
        negative_stock=Count("id", filter=Q(stock_on_hand__lt=0)),
        quick_created_needing_review=Count(
            "id",
            filter=Q(
                creation_source=Product.CreationSource.POS_QUICK_CREATE,
                needs_review=True,
            ),
        ),
    )
    return ReviewCounts(
        negative_stock=totals["negative_stock"],
        quick_created_needing_review=totals["quick_created_needing_review"],
    )


def audit_events(
    actor, *, query="", date_from=None, date_to=None, event_actor="", action="", target_type=""
):
    events = AuditEvent.objects.filter(shop_id=actor.shop_id).select_related("actor")
    query = str(query or "").strip()
    if query:
        events = events.filter(target_identifier__icontains=query)
    if date_from:
        start, _ = business_day_bounds(actor.shop, date_from)
        events = events.filter(created_at__gte=start)
    if date_to:
        _, end = business_day_bounds(actor.shop, date_to)
        events = events.filter(created_at__lt=end)
    if event_actor:
        events = events.filter(actor_id=event_actor)
    if action:
        events = events.filter(action=action)
    if target_type:
        events = events.filter(target_type=target_type)
    return events.order_by("-created_at", "-id")


def format_audit_payload(value):
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)
