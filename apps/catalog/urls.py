from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("lookup/", views.product_lookup, name="product_lookup"),
    path("new/", views.product_create, name="product_create"),
    path("<int:product_id>/", views.product_detail, name="product_detail"),
    path("<int:product_id>/edit/", views.product_edit, name="product_edit"),
    path("<int:product_id>/status/", views.product_status, name="product_status"),
    path("<int:product_id>/review/", views.product_review, name="product_review"),
]
