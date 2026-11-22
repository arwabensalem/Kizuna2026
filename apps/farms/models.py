from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Farm(models.Model):
    class Soil(models.TextChoices):
        SAND = 'sand', 'Sand'
        LOAM = 'loam', 'Loam'
        SILT = 'silt', 'Silt'
        CLAY = 'clay', 'Clay'
        ROCKY = 'rocky', 'Rocky'

    class IrrigationType(models.TextChoices):
        DRIP = 'drip', 'Drip'
        SPRINKLER = 'sprinkler', 'Sprinkler'
        FURROW = 'furrow', 'Furrow'
        NONE = 'none', 'None'

    class CropType(models.TextChoices):
        OLIVE = 'olive', 'Olive'
        TOMATO = 'tomato', 'Tomato'
        WHEAT = 'wheat', 'Wheat'
        PEPPER = 'pepper', 'Pepper'
        BARLEY = 'barley', 'Barley'
        CITRUS = 'citrus', 'Citrus'
        DATE = 'date', 'Date palm'
        ALMOND = 'almond', 'Almond'
        GRAPE = 'grape', 'Grape'
        POTATO = 'potato', 'Potato'
        FIG = 'fig', 'Fig'
        OTHER = 'other', 'Other'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farms',
    )
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    area_m2 = models.DecimalField(
        max_digits=12,
        decimal_places=1,
        validators=[MinValueValidator(0)],
    )
    soil_type = models.CharField(max_length=20, choices=Soil.choices, default=Soil.LOAM)
    irrigation_type = models.CharField(
        max_length=20,
        choices=IrrigationType.choices,
        default=IrrigationType.DRIP,
    )
    crop_type = models.CharField(max_length=20, choices=CropType.choices, default=CropType.OLIVE)
    tank_capacity_liters = models.PositiveIntegerField(default=5000)
    solar_capacity_watts = models.PositiveIntegerField(default=0)

    class Autonomy(models.TextChoices):
        ASSIST = 'assist', 'Assist'
        SMART = 'smart', 'Smart'
        AUTOPILOT = 'autopilot', 'Autopilot'

    autonomy_mode = models.CharField(
        max_length=16,
        choices=Autonomy.choices,
        default=Autonomy.ASSIST,
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Crop(models.Model):
    class Stage(models.TextChoices):
        SEEDLING = 'seedling', 'Seedling'
        VEGETATIVE = 'vegetative', 'Vegetative'
        FLOWERING = 'flowering', 'Flowering'
        FRUITING = 'fruiting', 'Fruiting'
        HARVEST = 'harvest', 'Harvest'

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='crops')
    kind = models.CharField(
        'culture', max_length=20, choices=Farm.CropType.choices, default=Farm.CropType.OTHER,
    )
    name = models.CharField(max_length=120)
    area_m2 = models.DecimalField(
        max_digits=12,
        decimal_places=1,
        validators=[MinValueValidator(0)],
    )
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.VEGETATIVE)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Irrigation(models.Model):
    """Earlier water-application note. New farms use IrrigationSystem."""

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='irrigation_events')
    crop = models.ForeignKey(
        Crop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='irrigation_events',
    )
    method = models.CharField(max_length=120)
    water_m3 = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        ordering = ['farm__name', 'method']

    def __str__(self):
        return f'{self.farm}: {self.method}'


class IrrigationSystem(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='irrigation_systems')
    name = models.CharField(max_length=120)
    method = models.CharField(max_length=20, choices=Farm.IrrigationType.choices)
    flow_liters_per_hour = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        default=0,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FarmTank(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='tanks')
    name = models.CharField(max_length=120)
    capacity_liters = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FarmSolar(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='solar_units')
    name = models.CharField(max_length=120)
    capacity_watts = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FarmSensor(models.Model):
    class Kind(models.TextChoices):
        SOIL_MOISTURE = 'soil_moisture', 'Soil moisture'
        TEMPERATURE = 'temperature', 'Temperature'
        HUMIDITY = 'humidity', 'Humidity'
        RAINFALL = 'rainfall', 'Rainfall'
        TANK_LEVEL = 'tank_level', 'Tank level'
        SOLAR_PRODUCTION = 'solar_production', 'Solar production'
        SOIL_MOISTURE_DEEP = 'soil_moisture_deep', 'Soil moisture 40 cm'
        PUMP_FLOW = 'pump_flow', 'Pump flow meter'
        WEATHER_STATION = 'weather_station', 'Weather station'

    UNITS = {
        Kind.SOIL_MOISTURE: '%',
        Kind.TEMPERATURE: '°C',
        Kind.HUMIDITY: '%',
        Kind.RAINFALL: 'mm',
        Kind.TANK_LEVEL: '%',
        Kind.SOLAR_PRODUCTION: 'W',
        Kind.SOIL_MOISTURE_DEEP: '%',
        Kind.PUMP_FLOW: 'm³/h',
        Kind.WEATHER_STATION: '',
    }

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='farm_sensors')
    kind = models.CharField(max_length=32, choices=Kind.choices)
    label = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    shared_with_neighbors = models.BooleanField(
        default=False,
        help_text='Une petite station météo peut servir à plusieurs fermes voisines.',
    )

    class Meta:
        ordering = ['kind', 'label']

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        if self.label:
            return self.label
        return self.get_kind_display()

    @property
    def unit(self):
        return self.UNITS.get(self.kind, '')
