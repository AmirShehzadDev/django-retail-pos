from .models import User


def _active_actor(actor):
    return bool(
        actor and getattr(actor, "is_authenticated", False) and actor.is_active and actor.shop_id
    )


def _same_shop(actor, target):
    return bool(_active_actor(actor) and target and actor.shop_id == target.shop_id)


def can_view_user(actor, target):
    if not _same_shop(actor, target):
        return False
    if actor.role == User.Role.OWNER:
        return True
    return actor.role == User.Role.ADMIN and target.role == User.Role.CASHIER


def can_create_role(actor, requested_role):
    if not _active_actor(actor):
        return False
    if actor.role == User.Role.OWNER:
        return requested_role in {User.Role.ADMIN, User.Role.CASHIER}
    return actor.role == User.Role.ADMIN and requested_role == User.Role.CASHIER


def can_edit_user(actor, target):
    if not _same_shop(actor, target) or actor.pk == target.pk:
        return False
    if target.role == User.Role.OWNER:
        return False
    if actor.role == User.Role.OWNER:
        return target.role in {User.Role.ADMIN, User.Role.CASHIER}
    return actor.role == User.Role.ADMIN and target.role == User.Role.CASHIER


def can_change_role(actor, target, requested_role):
    return bool(
        can_edit_user(actor, target)
        and actor.role == User.Role.OWNER
        and requested_role in {User.Role.ADMIN, User.Role.CASHIER}
    )


def can_change_active_state(actor, target):
    return can_edit_user(actor, target)


def can_reset_password(actor, target):
    return can_edit_user(actor, target)


def can_view_shop_settings(actor):
    return bool(_active_actor(actor) and actor.role in {User.Role.OWNER, User.Role.ADMIN})


def can_edit_shop_settings(actor):
    return bool(_active_actor(actor) and actor.role == User.Role.OWNER)
