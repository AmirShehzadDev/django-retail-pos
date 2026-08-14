from django.db import transaction
from django.test import TestCase

from apps.core.models import DocumentSequence, Shop
from apps.core.sequences import allocate_order_number


class DocumentSequenceTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Sequence shop")
        self.sequence = DocumentSequence.objects.create(
            shop=self.shop,
            document_type=DocumentSequence.DocumentType.ORDER,
        )

    def test_order_number_has_minimum_width_without_truncation(self):
        self.sequence.next_number = 1_000_000
        self.sequence.save(update_fields=["next_number"])

        self.assertEqual(allocate_order_number(self.shop.pk), "ORD-1000000")
        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.next_number, 1_000_001)

    def test_allocation_rolls_back_with_caller_transaction(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.assertEqual(allocate_order_number(self.shop.pk), "ORD-000001")
                raise RuntimeError("cancel transaction")

        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.next_number, 1)
