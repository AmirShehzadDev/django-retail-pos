from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0004_ordervoid_salesreturn_salesreturnitem_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="salesreturn",
            name="sales_return_reason_not_empty",
        ),
        migrations.AlterField(
            model_name="salesreturn",
            name="reason",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
