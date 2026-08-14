from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("reports/", views.daily_summary_view, name="daily_summary"),
    path("reports/audit/", views.audit_history, name="audit_history"),
    path("settings/shop/", views.shop_settings, name="shop_settings"),
]
