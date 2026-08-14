from apps.accounts.models import User


def _active_catalog_user(actor):
    return bool(
        actor
        and getattr(actor, "is_authenticated", False)
        and actor.is_active
        and actor.shop_id
        and actor.role in {User.Role.OWNER, User.Role.ADMIN, User.Role.CASHIER}
    )


def can_view_catalog(actor):
    return _active_catalog_user(actor)


def _active_manager(actor):
    return bool(_active_catalog_user(actor) and actor.role in {User.Role.OWNER, User.Role.ADMIN})


def can_manage_catalog(actor):
    return _active_manager(actor)


def _same_shop_viewer(actor, product):
    return bool(can_view_catalog(actor) and product and actor.shop_id == product.shop_id)


def _same_shop_manager(actor, product):
    return bool(can_manage_catalog(actor) and product and actor.shop_id == product.shop_id)


def can_view_product(actor, product):
    return _same_shop_viewer(actor, product)


def can_edit_product(actor, product):
    return _same_shop_manager(actor, product)


def can_change_product_stock(actor, product):
    return _same_shop_manager(actor, product)
