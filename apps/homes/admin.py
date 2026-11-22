from django.contrib import admin

from apps.homes.models import Appliance, Home, Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0


class ApplianceInline(admin.TabularInline):
    model = Appliance
    extra = 0


@admin.register(Home)
class HomeAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'residents', 'area_m2', 'autopilot_enabled', 'water_valve_open')
    search_fields = ('name', 'owner__username')
    inlines = (RoomInline, ApplianceInline)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'home')


@admin.register(Appliance)
class ApplianceAdmin(admin.ModelAdmin):
    list_display = ('kind', 'label', 'home', 'room', 'power_watts', 'water_liters_per_hour', 'is_active')
