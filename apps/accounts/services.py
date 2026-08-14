from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core.audit import record
from apps.core.models import AuditEvent

from .policies import (
    can_change_active_state,
    can_change_role,
    can_create_role,
    can_edit_user,
    can_reset_password,
)


def _lock_active_actor(actor):
    user_model = get_user_model()
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        raise PermissionDenied("An active manager is required.")
    try:
        return user_model.objects.select_for_update().get(pk=actor_id, is_active=True)
    except user_model.DoesNotExist as exc:
        raise PermissionDenied("An active manager is required.") from exc


def _lock_target(target_id):
    user_model = get_user_model()
    return user_model.objects.select_for_update().get(pk=target_id)


def _normalized_identity(*, username, first_name, last_name):
    return {
        "username": (username or "").strip(),
        "first_name": (first_name or "").strip(),
        "last_name": (last_name or "").strip(),
    }


@transaction.atomic
def create_managed_user(*, actor, username, first_name="", last_name="", role, password):
    actor = _lock_active_actor(actor)
    if not can_create_role(actor, role):
        raise PermissionDenied("You cannot create a user with this role.")

    user_model = get_user_model()
    identity = _normalized_identity(
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    user = user_model(
        **identity,
        shop=actor.shop,
        role=role,
        created_by=actor,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    validate_password(password, user=user)
    user.set_password(password)
    user.full_clean()
    user.save()

    record(
        shop=user.shop,
        actor=actor,
        action=AuditEvent.Action.USER_CREATED,
        target_type=AuditEvent.TargetType.USER,
        target_identifier=user.pk,
        after_values={
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_by_id": actor.pk,
        },
    )
    return user, True


@transaction.atomic
def update_managed_user(
    *,
    actor,
    target_id,
    username,
    first_name="",
    last_name="",
    role=None,
):
    actor = _lock_active_actor(actor)
    target = _lock_target(target_id)
    if not can_edit_user(actor, target):
        raise PermissionDenied("You cannot edit this user.")

    requested_role = target.role if role is None else role
    if requested_role != target.role and not can_change_role(actor, target, requested_role):
        raise PermissionDenied("You cannot change this user's role.")

    identity = _normalized_identity(
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    before_profile = {}
    after_profile = {}
    for field, new_value in identity.items():
        old_value = getattr(target, field)
        if old_value != new_value:
            before_profile[field] = old_value
            after_profile[field] = new_value
            setattr(target, field, new_value)

    old_role = target.role
    role_changed = old_role != requested_role
    if role_changed:
        target.role = requested_role

    changed = bool(before_profile or role_changed)
    if not changed:
        return target, False

    target.full_clean()
    update_fields = [*after_profile]
    if role_changed:
        update_fields.append("role")
    target.save(update_fields=update_fields)

    if before_profile:
        record(
            shop=target.shop,
            actor=actor,
            action=AuditEvent.Action.USER_PROFILE_UPDATED,
            target_type=AuditEvent.TargetType.USER,
            target_identifier=target.pk,
            before_values=before_profile,
            after_values=after_profile,
        )
    if role_changed:
        record(
            shop=target.shop,
            actor=actor,
            action=AuditEvent.Action.USER_ROLE_CHANGED,
            target_type=AuditEvent.TargetType.USER,
            target_identifier=target.pk,
            before_values={"role": old_role},
            after_values={"role": target.role},
        )
    return target, True


@transaction.atomic
def set_managed_user_active(*, actor, target_id, active):
    actor = _lock_active_actor(actor)
    target = _lock_target(target_id)
    if not can_change_active_state(actor, target):
        raise PermissionDenied("You cannot change this user's active state.")

    requested_active = bool(active)
    if target.is_active == requested_active:
        return target, False

    old_active = target.is_active
    target.is_active = requested_active
    target.save(update_fields=["is_active"])
    record(
        shop=target.shop,
        actor=actor,
        action=(
            AuditEvent.Action.USER_ACTIVATED
            if requested_active
            else AuditEvent.Action.USER_DEACTIVATED
        ),
        target_type=AuditEvent.TargetType.USER,
        target_identifier=target.pk,
        before_values={"is_active": old_active},
        after_values={"is_active": requested_active},
    )
    return target, True


@transaction.atomic
def reset_managed_user_password(*, actor, target_id, new_password):
    actor = _lock_active_actor(actor)
    target = _lock_target(target_id)
    if not can_reset_password(actor, target):
        raise PermissionDenied("You cannot reset this user's password.")

    validate_password(new_password, user=target)
    target.set_password(new_password)
    target.save(update_fields=["password"])
    record(
        shop=target.shop,
        actor=actor,
        action=AuditEvent.Action.USER_PASSWORD_RESET,
        target_type=AuditEvent.TargetType.USER,
        target_identifier=target.pk,
    )
    return target, True


@transaction.atomic
def change_own_password(*, actor, new_password):
    actor = _lock_active_actor(actor)
    validate_password(new_password, user=actor)
    actor.set_password(new_password)
    actor.save(update_fields=["password"])
    record(
        shop=actor.shop,
        actor=actor,
        action=AuditEvent.Action.USER_PASSWORD_CHANGED,
        target_type=AuditEvent.TargetType.USER,
        target_identifier=actor.pk,
    )
    return actor
