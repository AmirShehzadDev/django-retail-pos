from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.policies import can_edit_shop_settings

from .audit import record
from .models import AuditEvent, Shop


@transaction.atomic
def update_shop_name(*, actor, name):
    user_model = get_user_model()
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        raise PermissionDenied("An active owner is required.")
    try:
        actor = user_model.objects.select_for_update().get(pk=actor_id, is_active=True)
    except user_model.DoesNotExist as exc:
        raise PermissionDenied("An active owner is required.") from exc
    if not can_edit_shop_settings(actor):
        raise PermissionDenied("Only the owner can edit shop settings.")

    shop = Shop.objects.select_for_update().get(pk=actor.shop_id)
    normalized_name = (name or "").strip()
    if shop.name == normalized_name:
        return shop, False

    old_name = shop.name
    shop.name = normalized_name
    shop.full_clean()
    shop.save(update_fields=["name", "updated_at"])
    record(
        shop=shop,
        actor=actor,
        action=AuditEvent.Action.SHOP_NAME_CHANGED,
        target_type=AuditEvent.TargetType.SHOP,
        target_identifier=shop.pk,
        before_values={"name": old_name},
        after_values={"name": shop.name},
    )
    return shop, True
