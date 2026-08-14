from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("accounts/", include("apps.accounts.urls")),
    path("products/", include("apps.catalog.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("pos/", include("apps.sales.urls")),
    path("orders/", include("apps.sales.order_urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns.append(path("admin/", admin.site.urls))
