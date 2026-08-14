from django.contrib import admin

from .models import Shop, Terminal


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "currency", "timezone", "is_active")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "shop", "is_active")
    list_filter = ("shop", "is_active")
    readonly_fields = ("created_at", "updated_at")
