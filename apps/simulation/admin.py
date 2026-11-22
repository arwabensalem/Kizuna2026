from django.contrib import admin

from apps.simulation.models import (
    SimulatedActuator,
    SimulatedSensor,
    SimulationClock,
    SimulationStep,
    SimulationStock,
)


@admin.register(SimulationClock)
class SimulationClockAdmin(admin.ModelAdmin):
    list_display = ('hour', 'scenario', 'seed', 'crisis_state')


@admin.register(SimulatedSensor)
class SimulatedSensorAdmin(admin.ModelAdmin):
    list_display = ('group', 'key', 'value_text', 'unit', 'hour')


@admin.register(SimulationStock)
class SimulationStockAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'hour')


@admin.register(SimulatedActuator)
class SimulatedActuatorAdmin(admin.ModelAdmin):
    list_display = ('key', 'state', 'hour')


@admin.register(SimulationStep)
class SimulationStepAdmin(admin.ModelAdmin):
    list_display = ('hour', 'scenario', 'crisis_state', 'created_at')
