from django.contrib import admin

from apps.farms.models import (
    Crop,
    Farm,
    FarmSensor,
    FarmSolar,
    FarmTank,
    Irrigation,
    IrrigationSystem,
)


class CropInline(admin.TabularInline):
    model = Crop
    extra = 0


class FarmSensorInline(admin.TabularInline):
    model = FarmSensor
    extra = 0


class IrrigationSystemInline(admin.TabularInline):
    model = IrrigationSystem
    extra = 0


class FarmTankInline(admin.TabularInline):
    model = FarmTank
    extra = 0


class FarmSolarInline(admin.TabularInline):
    model = FarmSolar
    extra = 0


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'owner',
        'location',
        'crop_type',
        'soil_type',
        'area_m2',
        'latitude',
        'longitude',
    )
    search_fields = ('name', 'owner__username', 'location')
    inlines = (
        CropInline,
        FarmSensorInline,
        IrrigationSystemInline,
        FarmTankInline,
        FarmSolarInline,
    )


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ('name', 'farm', 'stage', 'area_m2')


@admin.register(Irrigation)
class IrrigationAdmin(admin.ModelAdmin):
    list_display = ('farm', 'crop', 'method', 'water_m3')


@admin.register(IrrigationSystem)
class IrrigationSystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'farm', 'method', 'flow_liters_per_hour', 'is_active')


@admin.register(FarmSensor)
class FarmSensorAdmin(admin.ModelAdmin):
    list_display = ('kind', 'label', 'farm', 'is_active')


@admin.register(FarmTank)
class FarmTankAdmin(admin.ModelAdmin):
    list_display = ('name', 'farm', 'capacity_liters')


@admin.register(FarmSolar)
class FarmSolarAdmin(admin.ModelAdmin):
    list_display = ('name', 'farm', 'capacity_watts')
