from apps.accounts.models import User

from .models import Order

POS_ROLES = frozenset({User.Role.OWNER, User.Role.ADMIN, User.Role.CASHIER})
MANAGER_ROLES = frozenset({User.Role.OWNER, User.Role.ADMIN})


def can_use_pos(actor):
    return bool(
        actor
        and getattr(actor, "is_authenticated", False)
        and actor.is_active
        and actor.shop_id
        and actor.role in POS_ROLES
        and getattr(actor.shop, "is_active", False)
    )


def _same_workspace(actor, draft, terminal):
    return bool(
        can_use_pos(actor)
        and draft
        and terminal
        and terminal.is_active
        and terminal.shop_id == actor.shop_id
        and draft.shop_id == actor.shop_id
        and draft.terminal_id == terminal.pk
        and draft.created_by.shop_id == actor.shop_id
        and draft.current_cashier.shop_id == actor.shop_id
        and draft.status == Order.Status.DRAFT
    )


def can_view_draft(actor, draft, terminal):
    return _same_workspace(actor, draft, terminal)


def can_create_draft(actor, terminal):
    return bool(
        can_use_pos(actor) and terminal and terminal.is_active and terminal.shop_id == actor.shop_id
    )


def can_edit_draft(actor, draft, terminal):
    return bool(_same_workspace(actor, draft, terminal) and draft.current_cashier_id == actor.pk)


def can_take_over_draft(actor, draft, terminal):
    return bool(_same_workspace(actor, draft, terminal) and draft.current_cashier_id != actor.pk)


def can_quick_create_product(actor):
    return can_use_pos(actor)


def can_complete_draft(actor, draft, terminal):
    return can_edit_draft(actor, draft, terminal)


def can_view_completed_orders(actor):
    return can_use_pos(actor)


def can_process_return(actor, order):
    return bool(
        can_use_pos(actor)
        and order
        and order.shop_id == actor.shop_id
        and order.status in {Order.Status.COMPLETED, Order.Status.PARTIALLY_RETURNED}
    )


def can_void_order(actor, order):
    return bool(
        can_use_pos(actor)
        and actor.role in MANAGER_ROLES
        and order
        and order.shop_id == actor.shop_id
        and order.status == Order.Status.COMPLETED
    )
