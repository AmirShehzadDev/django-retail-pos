import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_management_constraints"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("USER_CREATED", "User created"),
                            ("USER_PROFILE_UPDATED", "User profile updated"),
                            ("USER_ROLE_CHANGED", "User role changed"),
                            ("USER_ACTIVATED", "User activated"),
                            ("USER_DEACTIVATED", "User deactivated"),
                            ("USER_PASSWORD_RESET", "User password reset"),
                            ("USER_PASSWORD_CHANGED", "User password changed"),
                            ("SHOP_NAME_CHANGED", "Shop name changed"),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    "target_type",
                    models.CharField(
                        choices=[("USER", "User"), ("SHOP", "Shop")],
                        max_length=64,
                    ),
                ),
                ("target_identifier", models.CharField(max_length=64)),
                ("before_values", models.JSONField(default=dict)),
                ("after_values", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "shop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to="core.shop",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["shop", "-created_at"],
                        name="core_audit_shop_created_idx",
                    ),
                    models.Index(
                        fields=["shop", "action", "-created_at"],
                        name="core_audit_shop_action_idx",
                    ),
                    models.Index(
                        fields=["target_type", "target_identifier"],
                        name="core_audit_target_idx",
                    ),
                ],
            },
        ),
    ]
