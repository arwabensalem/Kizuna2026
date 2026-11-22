from django.contrib import admin

from apps.actuators.models import Actuator, ActuatorAction


@admin.register(Actuator)
class ActuatorAdmin(admin.ModelAdmin):
    list_display = ('kind', 'state', 'authorized', 'home', 'farm')
    list_filter = ('kind', 'authorized')


@admin.register(ActuatorAction)
class ActuatorActionAdmin(admin.ModelAdmin):
    list_display = ('action', 'actuator', 'mode', 'previous_state', 'new_state', 'created_at')
    list_filter = ('mode', 'rule', 'action')
