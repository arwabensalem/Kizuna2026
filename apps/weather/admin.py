from django.contrib import admin

from apps.weather.models import CollectionSystem, WaterRecovery, WeatherAction, WeatherHour, WeatherTimeline


@admin.register(CollectionSystem)
class CollectionSystemAdmin(admin.ModelAdmin):
    list_display = ('home', 'farm', 'tank_liters', 'tank_capacity_liters', 'authorized', 'prepared')


@admin.register(WeatherTimeline)
class WeatherTimelineAdmin(admin.ModelAdmin):
    list_display = ('scenario', 'hour', 'mode', 'source', 'home', 'farm', 'created_at')
    list_filter = ('scenario', 'mode', 'source')


@admin.register(WeatherHour)
class WeatherHourAdmin(admin.ModelAdmin):
    list_display = (
        'timeline',
        'hour',
        'temperature_c',
        'humidity_percent',
        'rainfall_probability',
        'rainfall_mm',
        'solar_radiation_wm2',
        'wind_kmh',
    )


@admin.register(WeatherAction)
class WeatherActionAdmin(admin.ModelAdmin):
    list_display = ('action', 'actuator', 'mode', 'previous_state', 'new_state', 'created_at')
    list_filter = ('mode', 'action')


@admin.register(WaterRecovery)
class WaterRecoveryAdmin(admin.ModelAdmin):
    list_display = ('timeline', 'hour', 'recovered_liters', 'tank_before', 'tank_after')
