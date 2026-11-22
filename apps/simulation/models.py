from django.db import models

from apps.simulation.engine import SCENARIOS


class SimulationClock(models.Model):
    """The single synthetic clock. One step is one simulated hour."""

    hour = models.PositiveIntegerField(default=0)
    scenario = models.CharField(
        max_length=32,
        choices=[(name, name) for name in SCENARIOS],
        default='NORMAL',
    )
    seed = models.PositiveIntegerField(default=20260601)
    crisis_state = models.CharField(max_length=16, default='none')

    def __str__(self):
        return f'hour {self.hour} · {self.scenario}'


class SimulatedSensor(models.Model):
    group = models.CharField(max_length=16)
    key = models.CharField(max_length=40)
    label = models.CharField(max_length=80)
    value_text = models.CharField(max_length=40)
    unit = models.CharField(max_length=16, blank=True)
    hour = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('group', 'key'), name='simulated_sensor_channel'),
        ]
        ordering = ['group', 'key']

    def __str__(self):
        return f'{self.group}.{self.key}'


class SimulationStock(models.Model):
    key = models.CharField(max_length=40, unique=True)
    value = models.FloatField()
    hour = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.key


class SimulatedActuator(models.Model):
    key = models.CharField(max_length=40, unique=True)
    state = models.CharField(max_length=16)
    hour = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.key} {self.state}'


class SimulationStep(models.Model):
    """One stored hour of the synthetic series."""

    hour = models.PositiveIntegerField(unique=True)
    scenario = models.CharField(max_length=32)
    crisis_state = models.CharField(max_length=16)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['hour']

    def __str__(self):
        return f'hour {self.hour}'
