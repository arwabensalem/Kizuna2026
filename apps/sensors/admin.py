from django.contrib import admin

from apps.sensors.models import Sensor


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'unit', 'home', 'farm')
