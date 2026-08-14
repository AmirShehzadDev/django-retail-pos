from django.core.exceptions import ValidationError

from .models import DocumentSequence

POSTGRESQL_POSITIVE_BIGINT_MAX = 9_223_372_036_854_775_807


def _allocate(shop_id, document_type, prefix, label):
    sequence = DocumentSequence.objects.select_for_update(of=("self",)).get(
        shop_id=shop_id,
        document_type=document_type,
    )
    if sequence.next_number >= POSTGRESQL_POSITIVE_BIGINT_MAX:
        raise ValidationError(f"The {label} number sequence is exhausted.")
    number = sequence.next_number
    sequence.next_number = number + 1
    sequence.save(update_fields=["next_number", "updated_at"])
    return f"{prefix}-{number:06d}"


def allocate_order_number(shop_id):
    """Allocate an order number inside the caller's transaction."""
    return _allocate(shop_id, DocumentSequence.DocumentType.ORDER, "ORD", "order")


def allocate_return_number(shop_id):
    """Allocate a return number inside the caller's transaction."""
    return _allocate(shop_id, DocumentSequence.DocumentType.RETURN, "RET", "return")
