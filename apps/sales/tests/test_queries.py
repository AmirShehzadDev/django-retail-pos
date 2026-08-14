from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import Shop, Terminal
from apps.sales.models import Order, OrderItem, Payment
from apps.sales.queries import load_workspace, recent_completed_orders, search_pos_products


class PosQueryTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.actor = User.objects.create_user(
            username="cashier",
            password="StrongPass!2026",
            shop=self.shop,
            role=User.Role.CASHIER,
        )
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")

    def order(self, slot, **overrides):
        values = {
            "shop": self.shop,
            "terminal": self.terminal,
            "slot": slot,
            "created_by": self.actor,
            "current_cashier": self.actor,
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def product(self, index=1, **overrides):
        values = {
            "shop": self.shop,
            "created_by": self.actor,
            "name": f"Tea {index:02d}",
            "barcode": f"0012{index:02d}",
            "sku": f"SKU-{index:02d}",
            "selling_price": Decimal("10.00"),
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def completed_order(self, number, *, completed_at, change=Decimal("0.00"), shop=None):
        shop = shop or self.shop
        actor = self.actor
        terminal = self.terminal
        if shop != self.shop:
            actor = User.objects.create_user(
                username=f"cashier-{number}",
                password="StrongPass!2026",
                shop=shop,
                role=User.Role.CASHIER,
            )
            terminal = Terminal.objects.create(
                shop=shop,
                code=f"TILL-{number}",
                name="Other till",
            )
        order = Order.objects.create(
            shop=shop,
            terminal=terminal,
            slot=1,
            status=Order.Status.COMPLETED,
            order_number=f"ORD-{number:06d}",
            created_by=actor,
            current_cashier=actor,
            completed_by=actor,
            completed_at=completed_at,
            subtotal=Decimal("10.00"),
            final_total=Decimal("10.00"),
        )
        Payment.objects.create(
            shop=shop,
            order=order,
            amount=Decimal("10.00"),
            cash_received=Decimal("10.00") + change,
            change_given=change,
            processed_by=actor,
        )
        return order

    def test_empty_workspace_is_read_only(self):
        state = load_workspace(self.actor, self.terminal)

        self.assertTrue(state.needs_initial_draft)
        self.assertEqual(state.drafts, ())
        self.assertIsNone(state.selected_draft)
        self.assertFalse(Order.objects.exists())

    def test_tabs_lines_and_requested_selection_are_stable(self):
        second = self.order(2)
        first = self.order(1)
        product = self.product()
        OrderItem.objects.create(
            order=first,
            product=product,
            product_name=product.name,
            product_barcode=product.barcode,
            unit_price=product.selling_price,
            quantity=1,
            line_total=product.selling_price,
        )

        state = load_workspace(self.actor, self.terminal, selected_draft_id=second.pk)

        self.assertEqual([order.slot for order in state.drafts], [1, 2])
        self.assertEqual(state.selected_draft, second)
        self.assertEqual(state.drafts[0].item_count, 1)
        self.assertEqual(list(state.drafts[0].items.all()), [first.items.get()])

    def test_invalid_selection_uses_latest_then_lowest_slot_tiebreak(self):
        first = self.order(1)
        second = self.order(2)
        now = timezone.now()
        Order.objects.filter(pk__in=[first.pk, second.pk]).update(updated_at=now)

        state = load_workspace(self.actor, self.terminal, selected_draft_id="foreign")

        self.assertEqual(state.selected_draft.pk, first.pk)

    def test_foreign_wrong_terminal_and_discarded_orders_are_excluded(self):
        valid = self.order(1)
        other_terminal = Terminal.objects.create(shop=self.shop, code="TILL-2", name="Other")
        self.order(2, terminal=other_terminal)
        self.order(
            3,
            status=Order.Status.DISCARDED,
            discarded_by=self.actor,
            discarded_at=timezone.now(),
            discard_was_empty=True,
        )

        state = load_workspace(self.actor, self.terminal, selected_draft_id=999999)

        self.assertEqual([order.pk for order in state.drafts], [valid.pk])

    def test_search_is_scoped_active_ordered_and_limited(self):
        for index in range(25, 0, -1):
            self.product(index)
        self.product(99, name="tea inactive", barcode="00999", is_active=False)
        other_shop = Shop.objects.create(name="Other")
        self.product(98, shop=other_shop, name="tea foreign", barcode="00998")

        results = list(search_pos_products(self.actor, query=" tea "))

        self.assertEqual(len(results), 25)
        self.assertEqual([product.name for product in results], sorted(p.name for p in results))
        self.assertNotIn("tea inactive", [product.name for product in results])
        self.assertNotIn("tea foreign", [product.name for product in results])

    def test_search_matches_barcode_sku_and_barcode_less_product(self):
        leading = self.product(1, barcode="0012345")
        barcode_less = self.product(2, barcode=None, sku="SPECIAL-SKU")

        self.assertEqual(list(search_pos_products(self.actor, query="0123")), [leading])
        self.assertEqual(list(search_pos_products(self.actor, query="special-sku")), [barcode_less])
        self.assertEqual(
            list(search_pos_products(self.actor, query="   ")),
            [leading, barcode_less],
        )

    def test_inactive_actor_is_denied(self):
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        self.actor.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            load_workspace(self.actor, self.terminal)

    def test_recent_completed_orders_are_paid_scoped_ordered_bounded_and_eager(self):
        now = timezone.now()
        completed = [
            self.completed_order(index, completed_at=now + timedelta(minutes=index))
            for index in range(1, 6)
        ]
        unpaid = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=2,
            status=Order.Status.COMPLETED,
            order_number="ORD-UNPAID",
            created_by=self.actor,
            current_cashier=self.actor,
            completed_by=self.actor,
            completed_at=now + timedelta(hours=1),
            subtotal=Decimal("1.00"),
            final_total=Decimal("1.00"),
        )
        other_shop = Shop.objects.create(name="Other")
        foreign = self.completed_order(99, completed_at=now + timedelta(hours=2), shop=other_shop)

        with self.assertNumQueries(1):
            rows = list(recent_completed_orders(self.actor, limit=50))
            changes = [row.payment.change_given for row in rows]

        self.assertEqual(rows, [completed[4], completed[3], completed[2]])
        self.assertEqual(changes, [Decimal("0.00")] * 3)
        self.assertNotIn(unpaid, rows)
        self.assertNotIn(foreign, rows)

    def test_recent_completed_orders_denies_inactive_actor_and_invalid_limit_is_empty(self):
        self.assertEqual(list(recent_completed_orders(self.actor, limit=0)), [])
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        self.actor.refresh_from_db()

        with self.assertRaises(PermissionDenied):
            recent_completed_orders(self.actor)
