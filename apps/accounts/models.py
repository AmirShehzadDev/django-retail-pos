from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import Shop


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "OWNER", _("Owner")
        ADMIN = "ADMIN", _("Admin")
        CASHIER = "CASHIER", _("Cashier")

    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="users")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CASHIER)
    created_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="created_users",
        null=True,
        blank=True,
    )

    REQUIRED_FIELDS = ["shop"]

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["OWNER", "ADMIN", "CASHIER"]),
                name="accounts_user_role_valid",
            ),
            models.UniqueConstraint(
                Lower("username"),
                name="accounts_user_username_ci_unique",
            ),
            models.UniqueConstraint(
                fields=["shop"],
                condition=models.Q(role="OWNER"),
                name="accounts_user_one_owner_per_shop",
            ),
        ]

    def __str__(self):
        return self.get_full_name() or self.username
