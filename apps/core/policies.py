from apps.accounts.models import User


def can_view_reports(actor):
    return bool(
        actor
        and getattr(actor, "is_authenticated", False)
        and actor.is_active
        and actor.shop_id
        and actor.role in {User.Role.OWNER, User.Role.ADMIN}
    )
