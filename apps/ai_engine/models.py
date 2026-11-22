"""Anomaly events and the log of automatic actions.

Trained forecast files still live under media/models. These tables record
what the home check decided and every valve or alert action that followed.
"""

from django.db import models


class ConsumptionSample(models.Model):
    """One saved home reading used as later history. Not a live meter archive."""

    home = models.ForeignKey('homes.Home', on_delete=models.CASCADE, related_name='consumption_samples')
    hour = models.PositiveSmallIntegerField()
    temperature_c = models.FloatField()
    water_liters_per_hour = models.FloatField()
    energy_watts = models.FloatField()
    tank_percent = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f'{self.home} hour {self.hour}'


class AnomalyEvent(models.Model):
    class Resource(models.TextChoices):
        WATER = 'water', 'Water'
        ENERGY = 'energy', 'Energy'

    class Type(models.TextChoices):
        NORMAL = 'normal', 'Normal consumption'
        HIGH_LEGITIMATE = 'high_legitimate', 'High legitimate consumption'
        TANK_FILLING = 'tank_filling', 'Tank filling'
        POSSIBLE_LEAK = 'possible_leak', 'Possible leak'
        CRITICAL = 'critical_abnormal', 'Critical abnormal consumption'

    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WATCH = 'watch', 'Watch'
        WARNING = 'warning', 'Warning'
        CRITICAL = 'critical', 'Critical'

    class Source(models.TextChoices):
        RULES = 'rules', 'Rules'
        RULES_FOREST = 'rules+isolation_forest', 'Rules and IsolationForest'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        ACKNOWLEDGED = 'acknowledged', 'Acknowledged'
        RESOLVED = 'resolved', 'Resolved'

    home = models.ForeignKey('homes.Home', on_delete=models.CASCADE, related_name='anomaly_events')
    resource = models.CharField(max_length=16, choices=Resource.choices)
    type = models.CharField(max_length=32, choices=Type.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    confidence = models.FloatField()
    detected_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=32, choices=Source.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    summary = models.TextField()
    observed = models.FloatField()
    baseline = models.FloatField()

    class Meta:
        ordering = ['-detected_at']

    def __str__(self):
        return f'{self.get_type_display()} · {self.home}'


class AutomaticAction(models.Model):
    """A recorded alert or valve change. State changes go through this log."""

    class Action(models.TextChoices):
        ALERT = 'alert', 'Alert'
        CLOSE_VALVE = 'close_valve', 'Close water valve'
        OPEN_VALVE = 'open_valve', 'Open water valve'

    class Source(models.TextChoices):
        ALERT = 'alert', 'Alert'
        AUTOPILOT = 'autopilot', 'Autopilot'
        USER = 'user', 'User'

    home = models.ForeignKey('homes.Home', on_delete=models.CASCADE, related_name='automatic_actions')
    event = models.ForeignKey(
        AnomalyEvent,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='actions',
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    source = models.CharField(max_length=16, choices=Source.choices)
    previous_state = models.CharField(max_length=16)
    new_state = models.CharField(max_length=16)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_action_display()} · {self.home}'
