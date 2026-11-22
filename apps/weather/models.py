"""Simulated weather, the rain path, and the actions it records.

The series is authored. A later connection to a real forecast can fill the
same fields. Until then every row stays marked as a simulation.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.weather.scenarios import SCENARIOS


class CollectionSystem(models.Model):
    """Roof, rainwater system, and tank for one home or one farm."""

    home = models.ForeignKey(
        'homes.Home',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='collection_systems',
    )
    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='collection_systems',
    )
    roof_area_m2 = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    capture_share = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default='0.80',
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text='Simulated share of rainfall the system is set to keep. Not a measured efficiency.',
    )
    tank_capacity_liters = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    tank_liters = models.DecimalField(
        max_digits=10,
        decimal_places=1,
        validators=[MinValueValidator(0)],
    )
    ready = models.BooleanField(default=False)
    authorized = models.BooleanField(
        default=False,
        help_text='Rain reaches the tank only after this system is authorized and prepared.',
    )
    prepared = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(home__isnull=False) | models.Q(farm__isnull=False),
                name='collection_has_site',
            ),
            models.UniqueConstraint(
                fields=('home',),
                condition=models.Q(home__isnull=False),
                name='collection_one_home',
            ),
            models.UniqueConstraint(
                fields=('farm',),
                condition=models.Q(farm__isnull=False),
                name='collection_one_farm',
            ),
        ]

    def __str__(self):
        return f'Collection · {self.tank_liters} / {self.tank_capacity_liters} L'


class WeatherTimeline(models.Model):
    class Mode(models.TextChoices):
        STANDBY = 'standby', 'Standby'
        RAIN_PREPARATION = 'rain_preparation', 'Rain preparation'
        COLLECTING = 'collecting', 'Collecting'

    home = models.ForeignKey(
        'homes.Home',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='weather_timelines',
    )
    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='weather_timelines',
    )
    scenario = models.CharField(
        max_length=32,
        choices=[(key, value['label']) for key, value in SCENARIOS.items()],
    )
    hour = models.PositiveSmallIntegerField(default=0)
    mode = models.CharField(max_length=32, choices=Mode.choices, default=Mode.STANDBY)
    source = models.CharField(max_length=16, default='simulation')
    preparation_logged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(home__isnull=False) | models.Q(farm__isnull=False),
                name='weather_timeline_has_site',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.scenario} · hour {self.hour}'


class WeatherHour(models.Model):
    timeline = models.ForeignKey(WeatherTimeline, on_delete=models.CASCADE, related_name='hours')
    hour = models.PositiveSmallIntegerField()
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1)
    humidity_percent = models.PositiveSmallIntegerField()
    rainfall_probability = models.PositiveSmallIntegerField()
    rainfall_mm = models.DecimalField(max_digits=5, decimal_places=1)
    solar_radiation_wm2 = models.PositiveIntegerField()
    wind_kmh = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('timeline', 'hour'), name='weather_hour_once'),
        ]
        ordering = ['hour']

    def __str__(self):
        return f'hour {self.hour}'


class WeatherAction(models.Model):
    timeline = models.ForeignKey(WeatherTimeline, on_delete=models.CASCADE, related_name='actions')
    hour = models.PositiveSmallIntegerField()
    action = models.CharField(max_length=40)
    reason = models.TextField()
    actuator = models.CharField(max_length=40)
    previous_state = models.CharField(max_length=40)
    new_state = models.CharField(max_length=40)
    mode = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.action


class WaterRecovery(models.Model):
    """Water that entered the tank on one simulated rainy hour."""

    timeline = models.ForeignKey(WeatherTimeline, on_delete=models.CASCADE, related_name='recoveries')
    hour = models.PositiveSmallIntegerField()
    rainfall_mm = models.DecimalField(max_digits=5, decimal_places=1)
    offered_liters = models.DecimalField(max_digits=10, decimal_places=1)
    recovered_liters = models.DecimalField(max_digits=10, decimal_places=1)
    tank_before = models.DecimalField(max_digits=10, decimal_places=1)
    tank_after = models.DecimalField(max_digits=10, decimal_places=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['hour', 'created_at']

    def __str__(self):
        return f'+ {self.recovered_liters} L'
