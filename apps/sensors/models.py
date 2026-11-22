from django.db import models

from apps.farms.models import Farm
from apps.homes.models import Home


class Sensor(models.Model):
    class Kind(models.TextChoices):
        WATER = 'water', 'Water'
        ENERGY = 'energy', 'Energy'
        SOIL = 'soil', 'Soil moisture'

    home = models.ForeignKey(
        Home,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sensors',
    )
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sensors',
    )
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    unit = models.CharField(max_length=20)

    class Meta:
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(home__isnull=False, farm__isnull=True)
                    | models.Q(home__isnull=True, farm__isnull=False)
                ),
                name='sensor_has_one_placement',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def place_name(self):
        if self.home_id:
            return self.home.name
        if self.farm_id:
            return self.farm.name
        return ''
