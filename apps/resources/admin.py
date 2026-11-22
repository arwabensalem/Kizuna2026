from django.contrib import admin

from apps.resources.models import ResourcePassport


@admin.register(ResourcePassport)
class ResourcePassportAdmin(admin.ModelAdmin):
    list_display = ('home', 'owner', 'period_label', 'water_used_m3', 'energy_used_kwh')
