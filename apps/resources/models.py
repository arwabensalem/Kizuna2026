from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.homes.models import Home


class ResourcePassport(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='passports',
    )
    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name='passports')
    period_label = models.CharField(max_length=80)
    water_used_m3 = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    energy_used_kwh = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f'{self.home}: {self.period_label}'
