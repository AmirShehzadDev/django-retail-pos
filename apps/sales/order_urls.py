from django.urls import path

from . import history_views

app_name = "order_history"

urlpatterns = [
    path("", history_views.order_list, name="list"),
    path("<str:order_number>/return/", history_views.return_order, name="return"),
    path("<str:order_number>/void/", history_views.void_order_view, name="void"),
    path("<str:order_number>/", history_views.order_detail, name="detail"),
]
