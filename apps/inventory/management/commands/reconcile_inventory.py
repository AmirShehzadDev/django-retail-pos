from django.core.management.base import BaseCommand, CommandError
from django.db.models import BigIntegerField, Sum, Value
from django.db.models.functions import Coalesce

from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Compare every product's cached stock with its immutable movement ledger."

    def handle(self, *args, **options):
        products = Product.objects.select_related("shop").annotate(
            ledger_stock=Coalesce(
                Sum("movements__quantity_change"),
                Value(0),
                output_field=BigIntegerField(),
            )
        )
        mismatches = []
        for product in products.order_by("shop_id", "id"):
            if product.stock_on_hand != product.ledger_stock:
                mismatches.append(product)
                self.stdout.write(
                    "Mismatch: "
                    f"shop={product.shop_id} product={product.pk} name={product.name!r} "
                    f"cached={product.stock_on_hand} ledger={product.ledger_stock}"
                )

        if mismatches:
            raise CommandError(f"Inventory reconciliation found {len(mismatches)} mismatch(es).")
        self.stdout.write(
            self.style.SUCCESS(f"Inventory reconciled: {products.count()} product(s).")
        )
