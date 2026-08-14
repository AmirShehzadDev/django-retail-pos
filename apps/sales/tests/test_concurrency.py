from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.catalog.services import update_product
from apps.core.models import AuditEvent, Shop, Terminal
from apps.inventory.models import InventoryMovement
from apps.sales.exceptions import BarcodeNowKnown, DraftLimitReached, DraftVersionConflict
from apps.sales.models import Order, OrderItem
from apps.sales.services import (
    ScanStatus,
    add_product,
    clear_draft,
    create_draft,
    quick_create_and_add,
    remove_item,
    scan_barcode,
    set_item_quantity,
    start_workspace,
    take_over_draft,
)


class SalesConcurrencyTests(TransactionTestCase):
    """PostgreSQL transaction tests; run against an isolated POS_TEST_DB_NAME."""

    reset_sequences = True

    def setUp(self):
        self.shop = Shop.objects.create(name="Concurrency Shop")
        self.cashier = self._user("cashier", User.Role.CASHIER)
        self.admin = self._user("admin", User.Role.ADMIN)
        self.owner = self._user("owner", User.Role.OWNER)
        self.terminal = Terminal.objects.create(
            shop=self.shop,
            code="TILL-1",
            name="Concurrency Till",
        )
        self.product = Product.objects.create(
            shop=self.shop,
            created_by=self.admin,
            name="Tea",
            barcode="0012345",
            selling_price=Decimal("10.00"),
            stock_on_hand=-4,
        )
        self.initial_inventory = self._inventory_snapshot()

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def _user(self, username, role):
        return User.objects.create_user(
            username=username,
            password=None,
            shop=self.shop,
            role=role,
        )

    def _draft(self, *, slot=1, cashier=None):
        return Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=slot,
            created_by=self.cashier,
            current_cashier=cashier or self.cashier,
        )

    def _inventory_snapshot(self):
        products = list(Product.objects.order_by("pk").values_list("pk", "stock_on_hand"))
        movements = list(
            InventoryMovement.objects.order_by("pk").values_list(
                "pk",
                "product_id",
                "movement_type",
                "quantity_change",
                "balance_after",
                "actor_id",
                "reason",
            )
        )
        return products, movements

    def _assert_inventory_unchanged(self):
        self.assertEqual(self._inventory_snapshot(), self.initial_inventory)

    def _race(self, *operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as executor:
            futures = [executor.submit(run, operation) for operation in operations]
            return [future.result(timeout=20) for future in futures]

    @staticmethod
    def _versioned_outcome(operation, projector):
        try:
            return "ok", projector(operation())
        except DraftVersionConflict as exc:
            return "version_conflict", (exc.expected_version, exc.current_version)

    def test_concurrent_initial_workspace_requests_are_idempotent(self):
        def start():
            order = start_workspace(self.cashier)
            return order.pk, order.slot, order.version

        outcomes = self._race(start, start, start)

        self.assertEqual(len(set(outcomes)), 1)
        self.assertEqual(outcomes[0][1:], (1, 1))
        self.assertEqual(
            list(Order.objects.filter(status=Order.Status.DRAFT).values_list("slot", flat=True)),
            [1],
        )
        self._assert_inventory_unchanged()

    def test_concurrent_new_drafts_fill_distinct_slots_and_stop_at_three(self):
        first = start_workspace(self.cashier)

        def create(actor):
            try:
                order = create_draft(actor)
                return "ok", (order.pk, order.slot)
            except DraftLimitReached:
                return "limit", None

        outcomes = self._race(
            lambda: create(self.cashier),
            lambda: create(self.admin),
            lambda: create(self.owner),
        )

        self.assertEqual([kind for kind, _ in outcomes].count("ok"), 2)
        self.assertEqual([kind for kind, _ in outcomes].count("limit"), 1)
        active = list(
            Order.objects.filter(status=Order.Status.DRAFT)
            .order_by("slot")
            .values_list("slot", flat=True)
        )
        self.assertEqual(active, [1, 2, 3])
        self.assertEqual(Order.objects.filter(status=Order.Status.DRAFT).count(), 3)
        self.assertEqual(first.slot, 1)
        self._assert_inventory_unchanged()

    def test_same_version_scans_have_one_increment_and_one_version_conflict(self):
        draft = self._draft()

        def scan():
            return self._versioned_outcome(
                lambda: scan_barcode(
                    self.cashier,
                    draft.pk,
                    draft.version,
                    self.product.barcode,
                ),
                lambda result: (result.status, result.version),
            )

        outcomes = self._race(scan, scan)

        self.assertCountEqual(
            outcomes,
            [
                ("ok", (ScanStatus.ADDED, 2)),
                ("version_conflict", (1, 2)),
            ],
        )
        draft.refresh_from_db()
        item = draft.items.get()
        self.assertEqual((draft.version, draft.subtotal), (2, Decimal("10.00")))
        self.assertEqual((item.quantity, item.line_total), (1, Decimal("10.00")))
        self._assert_inventory_unchanged()

    def test_same_version_search_adds_have_no_lost_increment(self):
        draft = self._draft()

        def add():
            return self._versioned_outcome(
                lambda: add_product(self.cashier, draft.pk, draft.version, self.product.pk),
                lambda order: order.version,
            )

        outcomes = self._race(add, add)

        self.assertCountEqual(
            outcomes,
            [("ok", 2), ("version_conflict", (1, 2))],
        )
        draft.refresh_from_db()
        self.assertEqual(draft.version, 2)
        self.assertEqual(draft.items.get().quantity, 1)
        self._assert_inventory_unchanged()

    def test_sequential_scan_queue_uses_returned_versions_and_keeps_both_scans(self):
        draft = self._draft()

        first = scan_barcode(
            self.cashier,
            draft.pk,
            draft.version,
            self.product.barcode,
        )
        second = scan_barcode(
            self.cashier,
            draft.pk,
            first.version,
            self.product.barcode,
        )

        draft.refresh_from_db()
        item = draft.items.get()
        self.assertEqual((first.version, second.version, draft.version), (2, 3, 3))
        self.assertEqual((item.quantity, item.line_total), (2, Decimal("20.00")))
        self.assertEqual(draft.subtotal, Decimal("20.00"))
        self._assert_inventory_unchanged()

    def test_same_version_quantity_and_remove_serialize_without_partial_change(self):
        draft = self._draft()
        draft = add_product(self.cashier, draft.pk, draft.version, self.product.pk)
        item = draft.items.get()

        def change_quantity():
            return self._versioned_outcome(
                lambda: set_item_quantity(
                    self.cashier,
                    draft.pk,
                    draft.version,
                    item.pk,
                    3,
                ),
                lambda order: ("quantity", order.version),
            )

        def remove():
            return self._versioned_outcome(
                lambda: remove_item(
                    self.cashier,
                    draft.pk,
                    draft.version,
                    item.pk,
                ),
                lambda order: ("remove", order.version),
            )

        outcomes = self._race(change_quantity, remove)

        self.assertEqual([kind for kind, _ in outcomes].count("ok"), 1)
        self.assertEqual([kind for kind, _ in outcomes].count("version_conflict"), 1)
        conflict = next(value for kind, value in outcomes if kind == "version_conflict")
        self.assertEqual(conflict, (2, 3))
        winner, version = next(value for kind, value in outcomes if kind == "ok")
        self.assertEqual(version, 3)
        draft.refresh_from_db()
        self.assertEqual(draft.version, 3)
        if winner == "quantity":
            retained = draft.items.get()
            self.assertEqual((retained.quantity, retained.line_total), (3, Decimal("30.00")))
            self.assertEqual(draft.subtotal, Decimal("30.00"))
        else:
            self.assertFalse(draft.items.exists())
            self.assertEqual(draft.subtotal, Decimal("0.00"))
        self._assert_inventory_unchanged()

    def test_simultaneous_takeovers_have_one_winner_conflict_and_audit(self):
        draft = self._draft()

        def takeover(actor):
            return self._versioned_outcome(
                lambda: take_over_draft(actor, draft.pk, draft.version),
                lambda order: (order.current_cashier_id, order.version),
            )

        outcomes = self._race(
            lambda: takeover(self.admin),
            lambda: takeover(self.owner),
        )

        self.assertEqual([kind for kind, _ in outcomes].count("ok"), 1)
        self.assertEqual([kind for kind, _ in outcomes].count("version_conflict"), 1)
        winner_id, winner_version = next(value for kind, value in outcomes if kind == "ok")
        self.assertIn(winner_id, {self.admin.pk, self.owner.pk})
        self.assertEqual(winner_version, 2)
        self.assertIn(("version_conflict", (1, 2)), outcomes)
        draft.refresh_from_db()
        self.assertEqual((draft.current_cashier_id, draft.version), (winner_id, 2))
        event = AuditEvent.objects.get(action=AuditEvent.Action.DRAFT_TAKEN_OVER)
        self.assertEqual(event.actor_id, winner_id)
        self.assertEqual(event.target_identifier, str(draft.pk))
        self.assertEqual(event.before_values, {"current_cashier_id": self.cashier.pk})
        self.assertEqual(event.after_values["current_cashier_id"], winner_id)
        self.assertEqual(event.after_values["creator_id"], self.cashier.pk)
        self._assert_inventory_unchanged()

    def test_clear_racing_edit_commits_one_complete_final_state(self):
        draft = self._draft()
        draft = add_product(self.cashier, draft.pk, draft.version, self.product.pk)
        original_item = draft.items.get()

        def edit():
            try:
                result = scan_barcode(
                    self.cashier,
                    draft.pk,
                    draft.version,
                    self.product.barcode,
                )
                return "ok", ("edit", result.version)
            except DraftVersionConflict as exc:
                return "version_conflict", (exc.expected_version, exc.current_version)
            except ValidationError as exc:
                return "inactive_conflict", tuple(exc.messages)

        def clear():
            try:
                cleared = clear_draft(self.cashier, draft.pk, draft.version)
                return "ok", ("clear", cleared.version)
            except DraftVersionConflict as exc:
                return "version_conflict", (exc.expected_version, exc.current_version)
            except ValidationError as exc:
                return "validation", tuple(exc.messages)

        outcomes = self._race(edit, clear)

        self.assertEqual([kind for kind, _ in outcomes].count("ok"), 1)
        draft.refresh_from_db()
        self.assertEqual((draft.status, draft.version), (Order.Status.DRAFT, 3))
        if OrderItem.objects.filter(pk=original_item.pk).exists():
            item = OrderItem.objects.get(pk=original_item.pk)
            self.assertIn(("ok", ("edit", 3)), outcomes)
            self.assertIn(("version_conflict", (2, 3)), outcomes)
            self.assertEqual(item.quantity, 2)
            self.assertEqual((item.line_total, draft.subtotal), (Decimal("20.00"),) * 2)
        else:
            self.assertIn(("ok", ("clear", 3)), outcomes)
            self.assertIn(("version_conflict", (2, 3)), outcomes)
            self.assertEqual(draft.subtotal, Decimal("0.00"))
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(AuditEvent.objects.exists())
        self._assert_inventory_unchanged()

    def test_same_barcode_quick_create_race_has_one_clean_winner(self):
        first = self._draft(slot=1, cashier=self.cashier)
        second = self._draft(slot=2, cashier=self.admin)

        def quick_create(actor, draft):
            try:
                product, order = quick_create_and_add(
                    actor,
                    draft.pk,
                    draft.version,
                    "009999",
                    "Race product",
                    "12.50",
                )
                return "ok", (product.pk, order.pk, order.version)
            except BarcodeNowKnown as exc:
                return "known", (exc.product_id, exc.is_active)

        outcomes = self._race(
            lambda: quick_create(self.cashier, first),
            lambda: quick_create(self.admin, second),
        )

        self.assertEqual([kind for kind, _ in outcomes].count("ok"), 1)
        self.assertEqual([kind for kind, _ in outcomes].count("known"), 1)
        product_id, winner_order_id, winner_version = next(
            value for kind, value in outcomes if kind == "ok"
        )
        self.assertEqual(
            next(value for kind, value in outcomes if kind == "known"), (product_id, True)
        )
        self.assertEqual(winner_version, 2)
        product = Product.objects.get(pk=product_id)
        self.assertEqual(product.barcode, "009999")
        self.assertEqual(product.creation_source, Product.CreationSource.POS_QUICK_CREATE)
        self.assertEqual(product.stock_on_hand, 0)
        item = OrderItem.objects.get(product=product)
        self.assertEqual(item.order_id, winner_order_id)
        self.assertEqual((item.quantity, item.unit_price), (1, Decimal("12.50")))
        self.assertEqual(OrderItem.objects.filter(product=product).count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditEvent.Action.PRODUCT_QUICK_CREATED).count(),
            1,
        )
        orders = dict(Order.objects.values_list("pk", "version"))
        self.assertEqual(orders[winner_order_id], 2)
        loser_order_id = second.pk if winner_order_id == first.pk else first.pk
        self.assertEqual(orders[loser_order_id], 1)
        self.assertFalse(InventoryMovement.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, -4)

    def test_price_edit_racing_first_add_captures_one_committed_price(self):
        draft = self._draft()

        def add():
            order = add_product(self.cashier, draft.pk, draft.version, self.product.pk)
            return "add", order.version

        def edit_price():
            product, changed = update_product(
                actor=self.admin,
                product_id=self.product.pk,
                name=self.product.name,
                barcode=self.product.barcode,
                sku=self.product.sku,
                selling_price="15.00",
                cost_price=self.product.cost_price,
            )
            return "price", (product.selling_price, changed)

        outcomes = self._race(add, edit_price)

        self.assertCountEqual(
            outcomes,
            [("add", 2), ("price", (Decimal("15.00"), True))],
        )
        draft.refresh_from_db()
        self.product.refresh_from_db()
        item = draft.items.get()
        self.assertIn(item.unit_price, {Decimal("10.00"), Decimal("15.00")})
        self.assertEqual(item.line_total, item.unit_price)
        self.assertEqual(draft.subtotal, item.unit_price)
        self.assertEqual(self.product.selling_price, Decimal("15.00"))
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditEvent.Action.PRODUCT_PRICE_CHANGED).count(),
            1,
        )
        self._assert_inventory_unchanged()

    def test_quick_create_rolls_back_when_audit_line_or_order_write_fails(self):
        draft = self._draft()
        failures = (
            "apps.sales.services.record",
            "apps.sales.services.OrderItem.save",
            "apps.sales.services.Order.save",
        )

        for target in failures:
            with self.subTest(target=target):
                with patch(target, side_effect=RuntimeError("injected write failure")):
                    with self.assertRaisesRegex(RuntimeError, "injected write failure"):
                        quick_create_and_add(
                            self.cashier,
                            draft.pk,
                            draft.version,
                            "008888",
                            "Rollback product",
                            "7.25",
                        )

                draft.refresh_from_db()
                self.assertEqual((draft.version, draft.subtotal), (1, Decimal("0.00")))
                self.assertFalse(Product.objects.filter(barcode="008888").exists())
                self.assertFalse(OrderItem.objects.exists())
                self.assertFalse(
                    AuditEvent.objects.filter(
                        action=AuditEvent.Action.PRODUCT_QUICK_CREATED
                    ).exists()
                )
                self._assert_inventory_unchanged()

    def test_clear_rolls_back_when_draft_save_fails(self):
        draft = self._draft()
        draft = add_product(self.cashier, draft.pk, draft.version, self.product.pk)

        with (
            patch(
                "apps.sales.services._save_material_change",
                side_effect=RuntimeError("draft save failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "draft save failed"),
        ):
            clear_draft(self.cashier, draft.pk, draft.version)

        draft.refresh_from_db()
        self.assertEqual((draft.status, draft.version), (Order.Status.DRAFT, 2))
        self.assertEqual(draft.items.count(), 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(AuditEvent.objects.exists())
        self._assert_inventory_unchanged()
