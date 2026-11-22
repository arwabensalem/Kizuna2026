from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Home(models.Model):
    class HomeType(models.TextChoices):
        APARTMENT = 'apartment', 'Appartement'
        VILLA = 'villa', 'Villa'
        PATIO = 'patio', 'Maison traditionnelle avec patio'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='homes',
    )
    name = models.CharField(max_length=120)
    home_type = models.CharField(
        'modèle de maison', max_length=16, choices=HomeType.choices, default=HomeType.APARTMENT,
    )
    address = models.CharField(max_length=255, blank=True)
    area_m2 = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        default=80,
        validators=[MinValueValidator(1)],
    )
    residents = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    bedrooms = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(0)])
    bathrooms = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(0)])
    has_kitchen = models.BooleanField(default=False)
    has_living_room = models.BooleanField(default=False)
    has_garden = models.BooleanField(default=False)
    has_pool = models.BooleanField(default=False)
    has_garage = models.BooleanField(default=False)
    has_solar_panels = models.BooleanField('panneaux solaires', default=False)
    has_water_tank = models.BooleanField('réservoir d’eau', default=False)
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
    class Autonomy(models.TextChoices):
        ASSIST = 'assist', 'Assist'
        SMART = 'smart', 'Smart'
        AUTOPILOT = 'autopilot', 'Autopilot'

    autonomy_mode = models.CharField(
        max_length=16,
        choices=Autonomy.choices,
        default=Autonomy.ASSIST,
    )
    autopilot_enabled = models.BooleanField(
        default=False,
        help_text='Kept in step with Smart and Autopilot so a critical leak can close the valve.',
    )
    water_valve_open = models.BooleanField(
        default=True,
        help_text='Stays open until a logged action closes it.',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Room(models.Model):
    class Kind(models.TextChoices):
        BEDROOM = 'bedroom', 'Bedroom'
        BATHROOM = 'bathroom', 'Bathroom'
        KITCHEN = 'kitchen', 'Kitchen'
        LIVING_ROOM = 'living_room', 'Living room'
        GARDEN = 'garden', 'Garden'
        POOL = 'pool', 'Pool'
        GARAGE = 'garage', 'Garage'
        OTHER = 'other', 'Other'

    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=Kind.choices)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Appliance(models.Model):
    class Kind(models.TextChoices):
        AC = 'ac', 'AC'
        TV = 'tv', 'TV'
        REFRIGERATOR = 'refrigerator', 'Refrigerator'
        WASHING_MACHINE = 'washing_machine', 'Washing machine'
        DISHWASHER = 'dishwasher', 'Dishwasher'
        WATER_HEATER = 'water_heater', 'Water heater'
        LIGHTS = 'lights', 'Lights'
        PUMP = 'pump', 'Pump'

    WATER_KINDS = (
        Kind.WASHING_MACHINE,
        Kind.DISHWASHER,
        Kind.WATER_HEATER,
        Kind.PUMP,
    )

    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name='appliances')
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appliances',
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.LIGHTS)
    label = models.CharField(max_length=120, blank=True)
    power_watts = models.PositiveIntegerField(default=0)
    water_liters_per_hour = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)
    temperature_setpoint = models.DecimalField(
        'température réglée (°C)',
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(35)],
        help_text='Pour une climatisation : la température affichée sur la télécommande.',
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
