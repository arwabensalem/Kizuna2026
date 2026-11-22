"""Actuators and the history of every automatic action.

A state change is written here with the mode that allowed it. Assist mode
records an alert and leaves the actuator where it was.
"""

from django.db import models


class Actuator(models.Model):
    class Kind(models.TextChoices):
        WATER_VALVE = 'water_valve', 'Water valve'
        IRRIGATION_PUMP = 'irrigation_pump', 'Irrigation pump'
        BATTERY = 'battery', 'Battery'
        SOLAR_ALLOCATION = 'solar_allocation', 'Solar allocation'
        NON_CRITICAL_LOADS = 'non_critical_loads', 'Non-critical loads'

    home = models.ForeignKey(
        'homes.Home',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='actuators',
    )
    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='actuators',
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    state = models.CharField(max_length=32)
    authorized = models.BooleanField(
        default=False,
        help_text='Smart and Autopilot can move this actuator only after it is authorized.',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('home', 'kind'),
                condition=models.Q(home__isnull=False),
                name='actuator_home_kind',
            ),
            models.UniqueConstraint(
                fields=('farm', 'kind'),
                condition=models.Q(farm__isnull=False),
                name='actuator_farm_kind',
            ),
            models.CheckConstraint(
                check=models.Q(home__isnull=False) | models.Q(farm__isnull=False),
                name='actuator_has_site',
            ),
        ]
        ordering = ['kind']

    def __str__(self):
        return f'{self.get_kind_display()} · {self.state}'


class ActuatorAction(models.Model):
    class Mode(models.TextChoices):
        ASSIST = 'assist', 'Assist'
        SMART = 'smart', 'Smart'
        AUTOPILOT = 'autopilot', 'Autopilot'

    actuator = models.ForeignKey(Actuator, on_delete=models.CASCADE, related_name='actions')
    home = models.ForeignKey(
        'homes.Home',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='actuator_actions',
    )
    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='actuator_actions',
    )
    action = models.CharField(max_length=40)
    reason = models.TextField()
    previous_state = models.CharField(max_length=32)
    new_state = models.CharField(max_length=32)
    mode = models.CharField(max_length=16, choices=Mode.choices)
    rule = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} · {self.get_mode_display()}'
