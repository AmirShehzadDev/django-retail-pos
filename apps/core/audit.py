from copy import deepcopy

from django.core.exceptions import ValidationError

from .models import AuditEvent

_ALLOWED_TARGETS = {
    AuditEvent.Action.USER_CREATED: AuditEvent.TargetType.USER,
    AuditEvent.Action.USER_PROFILE_UPDATED: AuditEvent.TargetType.USER,
    AuditEvent.Action.USER_ROLE_CHANGED: AuditEvent.TargetType.USER,
    AuditEvent.Action.USER_ACTIVATED: AuditEvent.TargetType.USER,
    AuditEvent.Action.USER_DEACTIVATED: AuditEvent.TargetType.USER,
    AuditEvent.Action.USER_PASSWORD_RESET: AuditEvent.TargetType.USER,
    AuditEvent.Action.USER_PASSWORD_CHANGED: AuditEvent.TargetType.USER,
    AuditEvent.Action.SHOP_NAME_CHANGED: AuditEvent.TargetType.SHOP,
    AuditEvent.Action.PRODUCT_PRICE_CHANGED: AuditEvent.TargetType.PRODUCT,
    AuditEvent.Action.INVENTORY_ADJUSTED: AuditEvent.TargetType.PRODUCT,
    AuditEvent.Action.PRODUCT_QUICK_CREATED: AuditEvent.TargetType.PRODUCT,
    AuditEvent.Action.DRAFT_TAKEN_OVER: AuditEvent.TargetType.ORDER,
    AuditEvent.Action.DRAFT_DISCARDED: AuditEvent.TargetType.ORDER,
    AuditEvent.Action.ORDER_ROUNDING_APPLIED: AuditEvent.TargetType.ORDER,
    AuditEvent.Action.STOCK_SHORTAGE_ACKNOWLEDGED: AuditEvent.TargetType.ORDER,
    AuditEvent.Action.ORDER_RETURNED: AuditEvent.TargetType.ORDER,
    AuditEvent.Action.ORDER_VOIDED: AuditEvent.TargetType.ORDER,
}
_SENSITIVE_KEY_PARTS = ("password", "hash", "token", "cookie", "session", "csrf")


def _reject_sensitive_keys(value, path="payload"):
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).casefold()
            if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
                raise ValidationError(f"Sensitive audit key is not permitted at {path}.")
            _reject_sensitive_keys(nested_value, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested_value in enumerate(value):
            _reject_sensitive_keys(nested_value, f"{path}[{index}]")


def record(
    *,
    shop,
    actor,
    action,
    target_type,
    target_identifier,
    before_values=None,
    after_values=None,
):
    if not actor or not getattr(actor, "is_authenticated", False) or not actor.is_active:
        raise ValidationError("An active authenticated actor is required.")
    if not shop or not shop.pk or actor.shop_id != shop.pk:
        raise ValidationError("The audit actor must belong to the event shop.")

    expected_target = _ALLOWED_TARGETS.get(action)
    if expected_target is None or target_type != expected_target:
        raise ValidationError("The audit action and target type are not permitted.")

    identifier = str(target_identifier)
    if not identifier or len(identifier) > 64:
        raise ValidationError("A valid target identifier is required.")

    before = deepcopy({} if before_values is None else before_values)
    after = deepcopy({} if after_values is None else after_values)
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValidationError("Audit values must be dictionaries.")
    _reject_sensitive_keys(before, "before_values")
    _reject_sensitive_keys(after, "after_values")

    return AuditEvent.objects.create(
        shop=shop,
        actor=actor,
        action=action,
        target_type=target_type,
        target_identifier=identifier,
        before_values=before,
        after_values=after,
    )
