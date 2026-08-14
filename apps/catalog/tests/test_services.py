from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.catalog.services import (
    create_product,
    create_product_with_optional_receipt,
    mark_product_reviewed,
    set_product_active,
    update_product,
)
from apps.core.models import AuditEvent, Shop


class CatalogServiceTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Shop")
        self.owner = self._user("owner", User.Role.OWNER)
        self.admin = self._user("admin", User.Role.ADMIN)
        self.cashier = self._user("cashier", User.Role.CASHIER)

    def _user(self, username, role, *, shop=None):
        return User.objects.create_user(
            username=username,
            password="StrongPass!2026",
            shop=shop or self.shop,
            role=role,
        )

    def _product(self, **overrides):
        values = {
            "shop": self.shop,
            "name": "Rice",
            "barcode": "00123",
            "sku": "RICE-1",
            "selling_price": "120.00",
            "cost_price": "100.00",
            "created_by": self.owner,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_create_derives_metadata_and_zero_stock(self):
        product = create_product(
            actor=self.admin,
            name="  Flour ",
            barcode=" 00456 ",
            sku="  FL-1 ",
            selling_price="200.00",
            cost_price=None,
        )

        self.assertEqual(product.name, "Flour")
        self.assertEqual(product.barcode, "00456")
        self.assertEqual(product.shop, self.shop)
        self.assertEqual(product.created_by, self.admin)
        self.assertEqual(product.creation_source, Product.CreationSource.CATALOG)
        self.assertEqual(product.stock_on_hand, 0)
        self.assertTrue(product.is_active)
        self.assertFalse(product.needs_review)

    def test_create_with_optional_receipt_uses_real_movement_or_stays_zero(self):
        product, movement = create_product_with_optional_receipt(
            actor=self.admin,
            name="Flour",
            barcode="00456",
            selling_price="200.00",
            quantity_received_now=9,
            receipt_note="Opening count",
        )
        self.assertEqual(product.stock_on_hand, 9)
        self.assertEqual(movement.quantity_change, 9)
        self.assertEqual(movement.balance_after, 9)
        self.assertEqual(movement.reason, "Opening count")
        self.assertEqual(product.movements.count(), 1)

        zero_product, no_movement = create_product_with_optional_receipt(
            actor=self.owner,
            name="Salt",
            barcode="00457",
            selling_price="50.00",
        )
        self.assertEqual(zero_product.stock_on_hand, 0)
        self.assertIsNone(no_movement)
        self.assertFalse(zero_product.movements.exists())

    def test_create_with_receipt_failure_rolls_back_product(self):
        with patch("apps.inventory.services.receive_stock", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                create_product_with_optional_receipt(
                    actor=self.admin,
                    name="Rolled back",
                    barcode="00777",
                    selling_price="25.00",
                    quantity_received_now=2,
                )
        self.assertFalse(Product.objects.filter(barcode="00777").exists())

    def test_cashier_and_stale_inactive_actor_cannot_create(self):
        values = {
            "name": "Flour",
            "selling_price": "200.00",
        }
        with self.assertRaises(PermissionDenied):
            create_product(actor=self.cashier, **values)
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            create_product(actor=self.admin, **values)

    def test_update_prices_writes_one_focused_audit_event(self):
        product = self._product()

        product, changed = update_product(
            actor=self.admin,
            product_id=product.pk,
            name="Rice premium",
            barcode=product.barcode,
            sku=product.sku,
            selling_price="130.00",
            cost_price="105.00",
        )

        self.assertTrue(changed)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.PRODUCT_PRICE_CHANGED)
        self.assertEqual(event.target_type, AuditEvent.TargetType.PRODUCT)
        self.assertEqual(
            event.before_values,
            {"selling_price": "120.00", "cost_price": "100.00"},
        )
        self.assertEqual(
            event.after_values,
            {"selling_price": "130.00", "cost_price": "105.00"},
        )

    def test_unchanged_update_does_not_write_audit(self):
        product = self._product()

        _, changed = update_product(
            actor=self.owner,
            product_id=product.pk,
            name=product.name,
            barcode=product.barcode,
            sku=product.sku,
            selling_price=product.selling_price,
            cost_price=product.cost_price,
        )

        self.assertFalse(changed)
        self.assertFalse(AuditEvent.objects.exists())

    def test_audit_failure_rolls_back_product_update(self):
        product = self._product()

        with patch("apps.catalog.services.record", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                update_product(
                    actor=self.owner,
                    product_id=product.pk,
                    name=product.name,
                    barcode=product.barcode,
                    sku=product.sku,
                    selling_price="150.00",
                    cost_price=product.cost_price,
                )

        product.refresh_from_db()
        self.assertEqual(str(product.selling_price), "120.00")

    def test_cross_shop_update_is_denied(self):
        other_shop = Shop.objects.create(name="Other")
        foreign_product = self._product(shop=other_shop)

        with self.assertRaises(PermissionDenied):
            update_product(
                actor=self.owner,
                product_id=foreign_product.pk,
                name=foreign_product.name,
                barcode=foreign_product.barcode,
                sku=foreign_product.sku,
                selling_price=foreign_product.selling_price,
                cost_price=foreign_product.cost_price,
            )

    def test_duplicate_barcode_is_rejected_without_partial_create(self):
        self._product()

        with self.assertRaises(ValidationError):
            create_product(
                actor=self.admin,
                name="Other",
                barcode="00123",
                selling_price="10.00",
            )

        self.assertEqual(Product.objects.count(), 1)

    def test_status_and_review_are_idempotent_and_do_not_touch_stock(self):
        product = self._product(stock_on_hand=-3, needs_review=True)

        product, changed = set_product_active(
            actor=self.admin, product_id=product.pk, is_active=False
        )
        _, repeated = set_product_active(actor=self.admin, product_id=product.pk, is_active=False)
        product, reviewed = mark_product_reviewed(actor=self.owner, product_id=product.pk)
        _, repeated_review = mark_product_reviewed(actor=self.owner, product_id=product.pk)

        self.assertTrue(changed)
        self.assertFalse(repeated)
        self.assertTrue(reviewed)
        self.assertFalse(repeated_review)
        self.assertEqual(product.stock_on_hand, -3)
        self.assertFalse(product.is_active)
        self.assertFalse(product.needs_review)
