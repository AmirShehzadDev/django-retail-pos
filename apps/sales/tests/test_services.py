from decimal import Decimal, localcontext
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent, Shop, Terminal
from apps.inventory.models import InventoryMovement
from apps.sales.exceptions import (
    BarcodeNowKnown,
    DraftLimitReached,
    DraftTakeoverRequired,
    DraftVersionConflict,
)
from apps.sales.models import Order, OrderItem, Payment
from apps.sales.services import (
    POSTGRESQL_POSITIVE_BIGINT_MAX,
    ScanStatus,
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


class SalesServiceTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.actor = self.user("cashier", User.Role.CASHIER)
        self.other = self.user("admin", User.Role.ADMIN)
        self.terminal = Terminal.objects.create(shop=self.shop, code="TILL-1", name="Till")

    def user(self, username, role, *, shop=None):
        return User.objects.create_user(
            username=username,
            password="StrongPass!2026",
            shop=shop or self.shop,
            role=role,
        )

    def product(self, **overrides):
        values = {
            "shop": self.shop,
            "created_by": self.other,
            "name": "Tea",
            "barcode": "0012345",
            "selling_price": Decimal("250.00"),
            "stock_on_hand": -2,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def draft(self, **overrides):
        values = {
            "shop": self.shop,
            "terminal": self.terminal,
            "slot": 1,
            "created_by": self.actor,
            "current_cashier": self.actor,
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def assert_inventory_unchanged(self, product, expected_stock=-2):
        product.refresh_from_db()
        self.assertEqual(product.stock_on_hand, expected_stock)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_start_is_idempotent_and_new_drafts_fill_lowest_gap(self):
        first = start_workspace(self.actor)
        repeated = start_workspace(self.actor)
        second = create_draft(self.actor)
        third = create_draft(self.actor)

        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual([first.slot, second.slot, third.slot], [1, 2, 3])
        self.assertEqual(first.version, 1)
        self.assertEqual(first.subtotal, Decimal("0.00"))
        with self.assertRaises(DraftLimitReached):
            create_draft(self.actor)

    def test_new_draft_reuses_lowest_free_active_slot(self):
        first = self.draft()
        Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=3,
            created_by=self.actor,
            current_cashier=self.actor,
        )
        first.status = Order.Status.DISCARDED
        first.discarded_by = self.actor
        first.discarded_at = first.updated_at
        first.discard_was_empty = True
        first.save()

        created = create_draft(self.actor)

        self.assertEqual(created.slot, 1)
        self.assertNotEqual(created.pk, first.pk)

    def test_stale_or_foreign_cashier_add_has_no_effect(self):
        draft = self.draft()
        product = self.product()
        with self.assertRaises(DraftVersionConflict) as caught:
            add_product(self.actor, draft.pk, 999, product.pk)
        self.assertEqual(caught.exception.current_version, 1)
        with self.assertRaises(DraftTakeoverRequired):
            add_product(self.other, draft.pk, 1, product.pk)
        self.assertFalse(OrderItem.objects.exists())

    def test_first_and_repeated_add_capture_snapshots_and_do_not_touch_stock(self):
        draft = self.draft()
        product = self.product()

        draft = add_product(self.actor, draft.pk, 1, product.pk)
        product.name = "New tea"
        product.barcode = "999"
        product.selling_price = Decimal("300.00")
        product.save(update_fields=["name", "barcode", "selling_price"])
        draft = add_product(self.actor, draft.pk, draft.version, product.pk)
        item = draft.items.get()

        self.assertEqual(item.product_name, "Tea")
        self.assertEqual(item.product_barcode, "0012345")
        self.assertEqual(item.unit_price, Decimal("250.00"))
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.line_total, Decimal("500.00"))
        self.assertEqual(draft.subtotal, Decimal("500.00"))
        self.assertEqual(draft.version, 3)
        self.assert_inventory_unchanged(product)

    def test_remove_then_readd_recaptures_current_product_values(self):
        draft = self.draft()
        product = self.product()
        draft = add_product(self.actor, draft.pk, 1, product.pk)
        item_id = draft.items.get().pk
        draft = remove_item(self.actor, draft.pk, draft.version, item_id)
        product.selling_price = Decimal("275.00")
        product.save(update_fields=["selling_price"])

        draft = add_product(self.actor, draft.pk, draft.version, product.pk)

        self.assertEqual(draft.items.get().unit_price, Decimal("275.00"))
        self.assertEqual(draft.subtotal, Decimal("275.00"))
        self.assert_inventory_unchanged(product)

    def test_quantity_replace_noop_validation_and_inactive_reduction(self):
        draft = self.draft()
        product = self.product()
        draft = add_product(self.actor, draft.pk, 1, product.pk)
        item = draft.items.get()
        draft = set_item_quantity(self.actor, draft.pk, draft.version, item.pk, 3)
        self.assertEqual(draft.version, 3)
        no_op = set_item_quantity(self.actor, draft.pk, draft.version, item.pk, 3)
        self.assertEqual(no_op.version, 3)

        product.is_active = False
        product.save(update_fields=["is_active"])
        reduced = set_item_quantity(self.actor, draft.pk, draft.version, item.pk, 2)
        self.assertEqual(reduced.items.get().quantity, 2)
        with self.assertRaises(ValidationError):
            set_item_quantity(self.actor, reduced.pk, reduced.version, item.pk, 4)

    def test_invalid_quantity_matrix_changes_nothing(self):
        draft = self.draft()
        product = self.product()
        draft = add_product(self.actor, draft.pk, 1, product.pk)
        item = draft.items.get()
        for value in (True, "2", 0, -1, POSTGRESQL_POSITIVE_BIGINT_MAX + 1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                set_item_quantity(self.actor, draft.pk, draft.version, item.pk, value)
        item.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(item.quantity, 1)
        self.assertEqual(draft.version, 2)

    def test_large_total_uses_local_high_precision_context(self):
        draft = self.draft()
        product = self.product(selling_price=Decimal("9999999999.99"))
        draft = add_product(self.actor, draft.pk, 1, product.pk)
        item = draft.items.get()

        with localcontext() as context:
            context.prec = 8
            draft = set_item_quantity(
                self.actor,
                draft.pk,
                draft.version,
                item.pk,
                POSTGRESQL_POSITIVE_BIGINT_MAX,
            )

        item.refresh_from_db()
        self.assertEqual(item.line_total, Decimal("92233720368455524349631452241.93"))
        self.assertEqual(draft.subtotal, item.line_total)

    def test_known_unknown_inactive_and_leading_zero_scan_contract(self):
        draft = self.draft()
        product = self.product()
        unknown = scan_barcode(self.actor, draft.pk, 1, " 009999 ")
        self.assertEqual(unknown.status, ScanStatus.UNKNOWN)
        self.assertTrue(unknown.is_unknown)
        self.assertEqual(unknown.version, 1)
        self.assertEqual(unknown.barcode, "009999")

        added = scan_barcode(self.actor, draft.pk, 1, " 0012345 ")
        self.assertEqual(added.status, ScanStatus.ADDED)
        self.assertEqual(added.order.items.get().product_barcode, "0012345")
        product.is_active = False
        product.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            scan_barcode(self.actor, draft.pk, added.version, "0012345")

    def test_invalid_barcode_and_stale_unknown_have_no_effect(self):
        draft = self.draft()
        for barcode in ("", " ", "X" * 65):
            with self.subTest(barcode=barcode), self.assertRaises(ValidationError):
                scan_barcode(self.actor, draft.pk, 1, barcode)
        with self.assertRaises(DraftVersionConflict):
            scan_barcode(self.actor, draft.pk, 2, "UNKNOWN")
        self.assertFalse(OrderItem.objects.exists())

    def test_quick_create_derives_product_line_audit_and_zero_stock(self):
        draft = self.draft()

        product, draft = quick_create_and_add(
            self.actor, draft.pk, 1, " 001999 ", "  New item ", "0.00"
        )

        self.assertEqual(product.barcode, "001999")
        self.assertEqual(product.name, "New item")
        self.assertEqual(product.creation_source, Product.CreationSource.POS_QUICK_CREATE)
        self.assertTrue(product.needs_review)
        self.assertTrue(product.is_active)
        self.assertIsNone(product.sku)
        self.assertIsNone(product.cost_price)
        self.assertEqual(product.stock_on_hand, 0)
        self.assertEqual(draft.items.get().product, product)
        event = AuditEvent.objects.get(action=AuditEvent.Action.PRODUCT_QUICK_CREATED)
        self.assertEqual(event.after_values["barcode"], "001999")
        self.assertEqual(event.after_values["selling_price"], "0.00")
        self.assertFalse(InventoryMovement.objects.exists())

    def test_quick_create_validation_and_now_known_leave_no_orphans(self):
        draft = self.draft()
        known = self.product()
        with self.assertRaises(BarcodeNowKnown) as caught:
            quick_create_and_add(
                self.actor, draft.pk, 1, known.barcode, "Duplicate", Decimal("1.00")
            )
        self.assertEqual(caught.exception.product_id, known.pk)
        for name, price in (("", "1.00"), ("Valid", "-0.01"), ("Valid", "1.001")):
            with self.subTest(name=name, price=price), self.assertRaises(ValidationError):
                quick_create_and_add(self.actor, draft.pk, 1, "NEW", name, price)
        self.assertEqual(Product.objects.count(), 1)
        self.assertFalse(OrderItem.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_quick_create_audit_failure_rolls_back_every_effect(self):
        draft = self.draft()
        with patch("apps.sales.services.record", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                quick_create_and_add(self.actor, draft.pk, 1, "NEW", "New", "1.00")
        draft.refresh_from_db()
        self.assertEqual(draft.version, 1)
        self.assertFalse(Product.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_quick_create_line_and_order_failure_roll_back_every_effect(self):
        for target in ("apps.sales.services.OrderItem.save", "apps.sales.services.Order.save"):
            with self.subTest(target=target):
                draft = self.draft()
                with patch(target, side_effect=RuntimeError("write failed")):
                    with self.assertRaises(RuntimeError):
                        quick_create_and_add(self.actor, draft.pk, 1, "NEW", "New", "1.00")
                draft.refresh_from_db()
                self.assertEqual(draft.version, 1)
                self.assertFalse(Product.objects.exists())
                self.assertFalse(OrderItem.objects.exists())
                self.assertFalse(AuditEvent.objects.exists())
                draft.delete()

    def test_takeover_is_explicit_preserves_creator_and_writes_exact_audit(self):
        draft = self.draft()
        product = self.product()
        draft = add_product(self.actor, draft.pk, 1, product.pk)

        taken = take_over_draft(self.other, draft.pk, draft.version)

        self.assertEqual(taken.created_by, self.actor)
        self.assertEqual(taken.current_cashier, self.other)
        self.assertEqual(taken.subtotal, Decimal("250.00"))
        event = AuditEvent.objects.get(action=AuditEvent.Action.DRAFT_TAKEN_OVER)
        self.assertEqual(event.before_values, {"current_cashier_id": self.actor.pk})
        self.assertEqual(event.after_values["current_cashier_id"], self.other.pk)
        self.assertEqual(event.after_values["item_count"], 1)
        with self.assertRaises(ValidationError):
            take_over_draft(self.other, taken.pk, taken.version)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_stale_or_failed_takeover_has_no_effect_or_audit(self):
        draft = self.draft()
        with self.assertRaises(DraftVersionConflict):
            take_over_draft(self.other, draft.pk, 2)
        with patch("apps.sales.services.record", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                take_over_draft(self.other, draft.pk, 1)
        draft.refresh_from_db()
        self.assertEqual(draft.current_cashier, self.actor)
        self.assertEqual(draft.version, 1)
        self.assertFalse(AuditEvent.objects.exists())

    def test_clear_nonempty_retains_draft_without_audit_or_inventory_effect(self):
        draft = self.draft()
        product = self.product()
        draft = add_product(self.actor, draft.pk, 1, product.pk)
        original = (draft.pk, draft.slot, draft.created_by_id, draft.current_cashier_id)

        cleared = clear_draft(self.actor, draft.pk, draft.version)

        self.assertEqual(
            (cleared.pk, cleared.slot, cleared.created_by_id, cleared.current_cashier_id),
            original,
        )
        self.assertEqual(cleared.status, Order.Status.DRAFT)
        self.assertEqual((cleared.subtotal, cleared.version), (Decimal("0.00"), 3))
        self.assertFalse(cleared.items.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assert_inventory_unchanged(product)

    def test_clear_rejects_empty_stale_and_unassigned_drafts(self):
        draft = self.draft()
        with self.assertRaises(ValidationError):
            clear_draft(self.actor, draft.pk, draft.version)

        product = self.product()
        draft = add_product(self.actor, draft.pk, draft.version, product.pk)
        with self.assertRaises(DraftVersionConflict):
            clear_draft(self.actor, draft.pk, draft.version - 1)
        with self.assertRaises(DraftTakeoverRequired):
            clear_draft(self.other, draft.pk, draft.version)
        self.assertTrue(OrderItem.objects.filter(order=draft).exists())

    def test_close_empty_selects_next_then_highest_lower_without_replacement(self):
        first = self.draft()
        second = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=2,
            created_by=self.actor,
            current_cashier=self.actor,
        )
        third = Order.objects.create(
            shop=self.shop,
            terminal=self.terminal,
            slot=3,
            created_by=self.actor,
            current_cashier=self.actor,
        )

        selected = close_empty_draft(self.actor, second.pk, second.version)
        self.assertEqual(selected.pk, third.pk)
        self.assertFalse(Order.objects.filter(pk=second.pk).exists())
        selected = close_empty_draft(self.actor, third.pk, third.version)
        self.assertEqual(selected.pk, first.pk)
        self.assertEqual(list(Order.objects.values_list("pk", flat=True)), [first.pk])
        self.assertFalse(AuditEvent.objects.exists())

    def test_close_rejects_last_nonempty_stale_and_unassigned_tabs(self):
        draft = self.draft()
        with self.assertRaises(ValidationError):
            close_empty_draft(self.actor, draft.pk, draft.version)
        second = self.draft(slot=2)
        with self.assertRaises(DraftVersionConflict):
            close_empty_draft(self.actor, second.pk, second.version + 1)
        second.current_cashier = self.other
        second.save(update_fields=["current_cashier"])
        with self.assertRaises(DraftTakeoverRequired):
            close_empty_draft(self.actor, second.pk, second.version)
        product = self.product()
        draft = add_product(self.actor, draft.pk, draft.version, product.pk)
        with self.assertRaises(ValidationError):
            close_empty_draft(self.actor, draft.pk, draft.version)

    def test_clear_failure_rolls_back_deleted_lines(self):
        draft = self.draft()
        product = self.product()
        draft = add_product(self.actor, draft.pk, draft.version, product.pk)
        with patch("apps.sales.services._save_material_change", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                clear_draft(self.actor, draft.pk, draft.version)
        draft.refresh_from_db()
        self.assertEqual((draft.subtotal, draft.version), (Decimal("250.00"), 2))
        self.assertEqual(draft.items.count(), 1)
        self.assertFalse(AuditEvent.objects.exists())

    def test_every_mutation_rejects_a_legacy_discarded_aggregate(self):
        draft = self.draft()
        product = self.product()
        draft = add_product(self.actor, draft.pk, 1, product.pk)
        item = draft.items.get()
        draft.status = Order.Status.DISCARDED
        draft.discarded_by = self.actor
        draft.discarded_at = draft.updated_at
        draft.discard_reason = "Historical"
        draft.save()
        operations = (
            lambda: add_product(self.actor, draft.pk, draft.version, product.pk),
            lambda: scan_barcode(self.actor, draft.pk, draft.version, product.barcode),
            lambda: set_item_quantity(self.actor, draft.pk, draft.version, item.pk, 2),
            lambda: remove_item(self.actor, draft.pk, draft.version, item.pk),
            lambda: take_over_draft(self.other, draft.pk, draft.version),
            lambda: clear_draft(self.actor, draft.pk, draft.version),
            lambda: close_empty_draft(self.actor, draft.pk, draft.version),
        )
        for operation in operations:
            with (
                self.subTest(operation=operation),
                self.assertRaises((ValidationError, Order.DoesNotExist)),
            ):
                operation()

    def test_inactive_actor_and_foreign_product_are_denied(self):
        draft = self.draft()
        foreign_shop = Shop.objects.create(name="Foreign")
        foreign_creator = self.user("foreign", User.Role.CASHIER, shop=foreign_shop)
        foreign = Product.objects.create(
            shop=foreign_shop,
            created_by=foreign_creator,
            name="Foreign",
            selling_price=Decimal("1.00"),
        )
        with self.assertRaises(Product.DoesNotExist):
            add_product(self.actor, draft.pk, 1, foreign.pk)
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            create_draft(self.actor)

    def test_corrupt_cross_shop_cashier_assignment_is_rejected(self):
        draft = self.draft()
        product = self.product()
        foreign_shop = Shop.objects.create(name="Foreign")
        foreign_cashier = self.user("foreign-cashier", User.Role.CASHIER, shop=foreign_shop)
        Order.objects.filter(pk=draft.pk).update(current_cashier=foreign_cashier)

        with self.assertRaises(ValidationError):
            add_product(self.actor, draft.pk, 1, product.pk)
        self.assertFalse(OrderItem.objects.exists())
