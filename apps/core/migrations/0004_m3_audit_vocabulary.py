from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_alter_auditevent_action_alter_auditevent_target_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("USER_CREATED", "User created"),
                    ("USER_PROFILE_UPDATED", "User profile updated"),
                    ("USER_ROLE_CHANGED", "User role changed"),
                    ("USER_ACTIVATED", "User activated"),
                    ("USER_DEACTIVATED", "User deactivated"),
                    ("USER_PASSWORD_RESET", "User password reset"),
                    ("USER_PASSWORD_CHANGED", "User password changed"),
                    ("SHOP_NAME_CHANGED", "Shop name changed"),
                    ("PRODUCT_PRICE_CHANGED", "Product price changed"),
                    ("INVENTORY_ADJUSTED", "Inventory adjusted"),
                    ("PRODUCT_QUICK_CREATED", "Product quick created"),
                    ("DRAFT_TAKEN_OVER", "Draft taken over"),
                    ("DRAFT_DISCARDED", "Draft discarded"),
                ],
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="target_type",
            field=models.CharField(
                choices=[
                    ("USER", "User"),
                    ("SHOP", "Shop"),
                    ("PRODUCT", "Product"),
                    ("ORDER", "Order"),
                ],
                max_length=64,
            ),
        ),
    ]
