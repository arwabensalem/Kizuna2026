from django.contrib import admin

from apps.ai_engine.models import AnomalyEvent, AutomaticAction, ConsumptionSample


@admin.register(ConsumptionSample)
class ConsumptionSampleAdmin(admin.ModelAdmin):
    list_display = ('home', 'hour', 'water_liters_per_hour', 'energy_watts', 'tank_percent', 'recorded_at')


@admin.register(AnomalyEvent)
class AnomalyEventAdmin(admin.ModelAdmin):
    list_display = ('home', 'resource', 'type', 'severity', 'confidence', 'source', 'status', 'detected_at')
    list_filter = ('type', 'severity', 'status', 'resource')


@admin.register(AutomaticAction)
class AutomaticActionAdmin(admin.ModelAdmin):
    list_display = ('home', 'action', 'source', 'previous_state', 'new_state', 'created_at')
    list_filter = ('action', 'source')
