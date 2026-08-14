from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("scan/", views.scan, name="scan"),
    path("products/<int:product_id>/receive/", views.receive, name="receive"),
    path("products/<int:product_id>/adjust/", views.adjust, name="adjust"),
    path("movements/", views.movement_list, name="movement_list"),
]
