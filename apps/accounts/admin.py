from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class PosUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("POS access", {"fields": ("shop", "role", "created_by")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("POS access", {"fields": ("shop", "role", "created_by")}),
    )
    list_display = ("username", "shop", "role", "is_active", "is_staff")
    list_filter = UserAdmin.list_filter + ("shop", "role")
