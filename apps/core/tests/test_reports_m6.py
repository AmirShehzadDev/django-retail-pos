from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, Shop, Terminal
from apps.core.reporting import business_day_bounds, current_review_counts, daily_summary
from apps.sales.models import Order, OrderVoid, Payment, SalesReturn


class ReportFixture(TestCase):
    password = "StrongPass!2026"

    def setUp(self):
        self.shop = Shop.objects.create(name="Report shop")
        self.other_shop = Shop.objects.create(name="Other shop")
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Main checkout")
        self.other_terminal = Terminal.objects.create(
            shop=self.other_shop, code="TILL-1", name="Other checkout"
        )
        self.owner = User.objects.create_user(
            username="report-owner",
            password=self.password,
            shop=self.shop,
            role=User.Role.OWNER,
        )
        self.admin = User.objects.create_user(
            username="report-admin",
            password=self.password,
            shop=self.shop,
            role=User.Role.ADMIN,
            created_by=self.owner,
        )
        self.cashier = User.objects.create_user(
            username="report-cashier",
            password=self.password,
            shop=self.shop,
            role=User.Role.CASHIER,
            created_by=self.owner,
        )
        self.other_owner = User.objects.create_user(
            username="other-owner",
            password=self.password,
            shop=self.other_shop,
            role=User.Role.OWNER,
        )

    def local_time(self, business_date, hour=12, minute=0):
        return timezone.make_aware(
            datetime.combine(business_date, time(hour=hour, minute=minute)),
            ZoneInfo(self.shop.timezone),
        )

    def sale(
        self,
        *,
        number,
        amount,
        cash_received,
        when,
        status=Order.Status.COMPLETED,
        shop=None,
        terminal=None,
        cashier=None,
    ):
        shop = shop or self.shop
        terminal = terminal or self.terminal
        cashier = cashier or self.cashier
        order = Order.objects.create(
            shop=shop,
            terminal=terminal,
            slot=1,
            status=status,
            created_by=cashier,
            current_cashier=cashier,
            completed_by=cashier,
            completed_at=when,
            subtotal=amount,
            final_total=amount,
            order_number=number,
        )
        with patch("django.utils.timezone.now", return_value=when):
            Payment.objects.create(
                shop=shop,
                order=order,
                direction=Payment.Direction.RECEIPT,
                amount=amount,
                cash_received=cash_received,
                change_given=cash_received - amount,
                processed_by=cashier,
            )
        return order

    def return_refund(self, order, amount, when):
        with patch("django.utils.timezone.now", return_value=when):
            sales_return = SalesReturn.objects.create(
                shop=self.shop,
                return_number=f"RET-{order.pk:06d}",
                order=order,
                processed_by=self.cashier,
                reason="",
                total_refund=amount,
                request_token=uuid4(),
            )
            Payment.objects.create(
                shop=self.shop,
                sales_return=sales_return,
                direction=Payment.Direction.REFUND,
                amount=amount,
                processed_by=self.cashier,
            )

    def void_refund(self, order, amount, when):
        with patch("django.utils.timezone.now", return_value=when):
            order_void = OrderVoid.objects.create(
                shop=self.shop,
                order=order,
                processed_by=self.owner,
                reason="Duplicate",
                request_token=uuid4(),
            )
            Payment.objects.create(
                shop=self.shop,
                order_void=order_void,
                direction=Payment.Direction.REFUND,
                amount=amount,
                processed_by=self.owner,
            )


class DailySummaryQueryTests(ReportFixture):
    def test_summary_reconciles_signed_change_and_later_corrections(self):
        selected = date(2026, 8, 7)
        previous = selected - timedelta(days=1)
        old_order = self.sale(
            number="ORD-OLD",
            amount=Decimal("40.00"),
            cash_received=Decimal("40.00"),
            when=self.local_time(previous),
            status=Order.Status.PARTIALLY_RETURNED,
        )
        self.return_refund(old_order, Decimal("10.00"), self.local_time(selected, 9))
        old_void = self.sale(
            number="ORD-OLD-VOID",
            amount=Decimal("30.00"),
            cash_received=Decimal("30.00"),
            when=self.local_time(previous, 13),
            status=Order.Status.VOIDED,
        )
        self.void_refund(old_void, Decimal("30.00"), self.local_time(selected, 9, 30))
        self.sale(
            number="ORD-TODAY-1",
            amount=Decimal("100.00"),
            cash_received=Decimal("101.00"),
            when=self.local_time(selected, 10),
        )
        self.sale(
            number="ORD-TODAY-2",
            amount=Decimal("50.00"),
            cash_received=Decimal("49.00"),
            when=self.local_time(selected, 11),
        )
        self.sale(
            number="ORD-OTHER",
            amount=Decimal("999.00"),
            cash_received=Decimal("999.00"),
            when=self.local_time(selected, 13),
            shop=self.other_shop,
            terminal=self.other_terminal,
            cashier=self.other_owner,
        )

        result = daily_summary(self.owner, selected)

        self.assertEqual(result.gross_sales, Decimal("150.00"))
        self.assertEqual(result.returns, Decimal("10.00"))
        self.assertEqual(result.voids, Decimal("30.00"))
        self.assertEqual(result.net_sales, Decimal("110.00"))
        self.assertEqual(result.order_count, 2)
        self.assertEqual(result.cash_collected, Decimal("150.00"))
        self.assertEqual(result.cash_refunded, Decimal("40.00"))
        self.assertEqual(result.nonzero_change_count, 2)
        self.assertEqual(result.signed_change_total, Decimal("0.00"))
        self.assertEqual(result.gross_reconciliation, result.gross_sales)
        self.assertEqual(result.net_cash_movement, result.net_sales)
        self.assertEqual(daily_summary(self.owner, selected + timedelta(days=1)).gross_sales, 0)

    def test_business_day_uses_karachi_midnight_boundaries(self):
        start, end = business_day_bounds(self.shop, date(2026, 8, 7))

        self.assertEqual(start.utcoffset(), timedelta(hours=5))
        self.assertEqual(
            start.astimezone(ZoneInfo("UTC")), datetime(2026, 8, 6, 19, tzinfo=ZoneInfo("UTC"))
        )
        self.assertEqual(end - start, timedelta(days=1))

    def test_current_review_counts_are_shop_scoped(self):
        Product.objects.create(
            shop=self.shop,
            name="Negative",
            selling_price=Decimal("10.00"),
            stock_on_hand=-2,
            created_by=self.owner,
        )
        Product.objects.create(
            shop=self.shop,
            name="Quick",
            selling_price=Decimal("5.00"),
            created_by=self.cashier,
            creation_source=Product.CreationSource.POS_QUICK_CREATE,
            needs_review=True,
        )
        Product.objects.create(
            shop=self.other_shop,
            name="Other negative quick",
            selling_price=Decimal("5.00"),
            stock_on_hand=-1,
            created_by=self.other_owner,
            creation_source=Product.CreationSource.POS_QUICK_CREATE,
            needs_review=True,
        )

        counts = current_review_counts(self.owner)

        self.assertEqual(counts.negative_stock, 1)
        self.assertEqual(counts.quick_created_needing_review, 1)


class ReportViewTests(ReportFixture):
    def test_manager_access_navigation_summary_and_review_links(self):
        today = timezone.localdate(timezone=ZoneInfo(self.shop.timezone))
        self.sale(
            number="ORD-NOW",
            amount=Decimal("25.00"),
            cash_received=Decimal("26.00"),
            when=self.local_time(today),
        )

        for manager in (self.owner, self.admin):
            with self.subTest(role=manager.role):
                self.client.force_login(manager)
                response = self.client.get(reverse("core:daily_summary"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Daily summary")
                self.assertContains(response, "PKR 25.00")
                self.assertContains(response, "?negative=on")
                self.assertContains(response, "?needs_review=on")
                self.assertContains(response, reverse("core:audit_history"))
                home = self.client.get(reverse("core:home"))
                self.assertContains(home, reverse("core:daily_summary"), count=2)

    def test_cashier_anonymous_and_post_boundaries(self):
        self.client.force_login(self.cashier)
        for name in ("core:daily_summary", "core:audit_history"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        home = self.client.get(reverse("core:home"))
        self.assertNotContains(home, reverse("core:daily_summary"))

        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse("core:daily_summary")).status_code, 405)
        self.assertEqual(self.client.post(reverse("core:audit_history")).status_code, 405)
        self.client.logout()
        response = self.client.get(reverse("core:daily_summary"))
        self.assertEqual(response.status_code, 302)

    def test_invalid_daily_date_shows_error_and_safe_default(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("core:daily_summary"), {"date": "not-a-date"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid date")


class AuditHistoryTests(ReportFixture):
    def audit_event(
        self,
        *,
        actor=None,
        action=AuditEvent.Action.ORDER_RETURNED,
        target_type=AuditEvent.TargetType.ORDER,
        target_identifier="ORD-42",
        when=None,
        before=None,
        after=None,
        shop=None,
    ):
        actor = actor or self.cashier
        shop = shop or self.shop
        when = when or timezone.now()
        with patch("django.utils.timezone.now", return_value=when):
            return AuditEvent.objects.create(
                shop=shop,
                actor=actor,
                action=action,
                target_type=target_type,
                target_identifier=target_identifier,
                before_values=before or {},
                after_values=after or {},
            )

    def test_filters_are_combined_shop_scoped_and_payload_is_escaped(self):
        selected = date(2026, 8, 7)
        matching = self.audit_event(
            when=self.local_time(selected, 10),
            after={"note": "<script>alert(1)</script>", "refund": "10.00"},
        )
        self.audit_event(
            actor=self.owner,
            action=AuditEvent.Action.SHOP_NAME_CHANGED,
            target_type=AuditEvent.TargetType.SHOP,
            target_identifier=str(self.shop.pk),
            when=self.local_time(selected, 11),
        )
        self.audit_event(
            actor=self.other_owner,
            target_identifier="ORD-42",
            when=self.local_time(selected, 12),
            shop=self.other_shop,
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("core:audit_history"),
            {
                "q": "ORD-42",
                "date_from": selected.isoformat(),
                "date_to": selected.isoformat(),
                "actor": self.cashier.pk,
                "action": AuditEvent.Action.ORDER_RETURNED,
                "target_type": AuditEvent.TargetType.ORDER,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["events"]), [matching])
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_invalid_range_and_foreign_actor_show_no_events(self):
        self.audit_event()
        self.client.force_login(self.owner)

        invalid_range = self.client.get(
            reverse("core:audit_history"),
            {"date_from": "2026-08-08", "date_to": "2026-08-07"},
        )
        foreign_actor = self.client.get(
            reverse("core:audit_history"), {"actor": self.other_owner.pk}
        )

        self.assertContains(invalid_range, "From date cannot be after To date")
        self.assertEqual(list(invalid_range.context["events"]), [])
        self.assertContains(foreign_actor, "Select a valid choice")
        self.assertEqual(list(foreign_actor.context["events"]), [])

    def test_newest_first_pagination_preserves_filters(self):
        for index in range(51):
            self.audit_event(
                target_identifier=f"ORD-{index:03d}",
                when=self.local_time(date(2026, 8, 7), 10) + timedelta(seconds=index),
            )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("core:audit_history"), {"q": "ORD-"})

        self.assertEqual(response.context["page_obj"].paginator.count, 51)
        self.assertEqual(response.context["events"][0].target_identifier, "ORD-050")
        self.assertContains(response, "q=ORD-&amp;page=2")
