from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class KizunaUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('KIZUNA', {'fields': ('role', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('KIZUNA', {'fields': ('role',)}),
    )
    list_display = ('username', 'email', 'phone', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')
