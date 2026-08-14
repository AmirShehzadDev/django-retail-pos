from django.db import migrations, models
from django.db.models.functions import Lower


def check_case_insensitive_username_duplicates(apps, schema_editor):
    user_model = apps.get_model("accounts", "User")
    duplicates = (
        user_model.objects.using(schema_editor.connection.alias)
        .annotate(normalized_username=Lower("username"))
        .values("normalized_username")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
        .order_by("normalized_username")
    )
    duplicate = duplicates.first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot add case-insensitive username uniqueness: existing usernames conflict "
            f"for normalized value {duplicate['normalized_username']!r}."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            check_case_insensitive_username_duplicates,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("username"),
                name="accounts_user_username_ci_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(role="OWNER"),
                fields=("shop",),
                name="accounts_user_one_owner_per_shop",
            ),
        ),
    ]
