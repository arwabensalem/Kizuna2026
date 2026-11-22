"""Household anomaly check.

The baseline is built for one home from its residents, rooms and outdoor
features, active appliances, saved readings, the hour, and the temperature.
Cuts are ratios of that baseline. There is no single liter or watt limit
shared by every household.

IsolationForest runs only when this home has enough saved readings. It can
support a rule decision. It does not replace the class the rules chose.
"""

import math

import numpy as np
from django.db import transaction

from apps.ai_engine.models import AnomalyEvent, AutomaticAction, ConsumptionSample
from apps.homes.models import Appliance

HISTORY_LIMIT = 72
FOREST_MIN_ROWS = 24
SAME_HOUR = 2


def evaluate_home(home, reading):
    """Classify water and energy, then alert or close the valve in the open.

    The new reading is stored after the decision, so it does not set its own baseline.
    """
    samples = list(
        ConsumptionSample.objects.filter(home=home).order_by('-recorded_at')[:HISTORY_LIMIT]
    )
    reading = dict(reading)
    reading['history_count'] = len(samples)
    appliances = list(home.appliances.all())
    water = _water_decision(home, appliances, samples, reading)
    energy = _energy_decision(home, appliances, samples, reading)
    forest_outlier = _forest_outlier(samples, reading)
    if forest_outlier:
        for decision in (water, energy):
            if decision['type'] != AnomalyEvent.Type.NORMAL:
                decision['source'] = AnomalyEvent.Source.RULES_FOREST
                decision['confidence'] = _clamp(decision['confidence'] + 0.06, 0.5, 0.95)

    with transaction.atomic():
        locked = home.__class__.objects.select_for_update().get(pk=home.pk)
        events = []
        actions = []
        for decision in (water, energy):
            if decision['type'] == AnomalyEvent.Type.NORMAL:
                continue
            event = AnomalyEvent.objects.create(
                home=locked,
                resource=decision['resource'],
                type=decision['type'],
                severity=decision['severity'],
                confidence=decision['confidence'],
                source=decision['source'],
                summary=decision['summary'],
                observed=decision['observed'],
                baseline=decision['baseline'],
            )
            events.append(event)
            actions.append(_respond(locked, event, decision))
        ConsumptionSample.objects.create(
            home=locked,
            hour=reading['hour'],
            temperature_c=reading['temperature_c'],
            water_liters_per_hour=reading['water_liters_per_hour'],
            energy_watts=reading['energy_watts'],
            tank_percent=reading['tank_percent'],
        )
        locked.save(update_fields=['water_valve_open'])

    home.water_valve_open = locked.water_valve_open
    return {
        'water': water,
        'energy': energy,
        'events': events,
        'actions': actions,
        'valve_open': locked.water_valve_open,
        'autopilot': locked.autopilot_enabled,
        'forest_used': len(samples) >= FOREST_MIN_ROWS,
        'forest_outlier': forest_outlier,
        'history_count': len(samples),
    }


def record_valve_choice(home, want_open):
    """Apply an explicit user valve change and write it in the action log."""
    previous = 'open' if home.water_valve_open else 'closed'
    home.water_valve_open = want_open
    home.save(update_fields=['water_valve_open'])
    new_state = 'open' if want_open else 'closed'
    if want_open:
        summary = 'You opened the water valve. Autopilot did not do this.'
        action = AutomaticAction.Action.OPEN_VALVE
    else:
        summary = 'You closed the water valve. Autopilot did not do this.'
        action = AutomaticAction.Action.CLOSE_VALVE
    from apps.actuators.models import Actuator

    Actuator.objects.filter(home=home, kind=Actuator.Kind.WATER_VALVE).update(state=new_state)
    return AutomaticAction.objects.create(
        home=home,
        action=action,
        source=AutomaticAction.Source.USER,
        previous_state=previous,
        new_state=new_state,
        summary=summary,
    )


def _respond(home, event, decision):
    previous = 'open' if home.water_valve_open else 'closed'
    critical_leak = (
        decision['resource'] == AnomalyEvent.Resource.WATER
        and decision['type'] == AnomalyEvent.Type.CRITICAL
    )
    if critical_leak and home.autopilot_enabled:
        home.water_valve_open = False
        summary = (
            'Autopilot closed the water valve because this home has a critical water leak. '
            f'The valve was {previous}.'
        )
        return AutomaticAction.objects.create(
            home=home,
            event=event,
            action=AutomaticAction.Action.CLOSE_VALVE,
            source=AutomaticAction.Source.AUTOPILOT,
            previous_state=previous,
            new_state='closed',
            summary=summary,
        )
    if critical_leak:
        summary = (
            'Critical water leak. Autopilot is off, so this is an alert only. '
            f'The water valve stays {previous}.'
        )
    else:
        summary = (
            f"{decision['summary']} Alert only. The water valve stays {previous}."
        )
    return AutomaticAction.objects.create(
        home=home,
        event=event,
        action=AutomaticAction.Action.ALERT,
        source=AutomaticAction.Source.ALERT,
        previous_state=previous,
        new_state=previous,
        summary=summary,
    )


def _water_decision(home, appliances, samples, reading):
    structural = _structural_water(home)
    morning, evening = _peaks(reading['hour'])
    time_factor = 0.45 + 0.85 * morning + 0.75 * evening
    temp_extra = 0.12 * home.residents * max(0.0, reading['temperature_c'] - 28)
    appliance_water = sum(
        float(item.water_liters_per_hour)
        for item in appliances
        if item.is_active
    )
    quiet = structural * time_factor + temp_extra
    expected = quiet + appliance_water
    expected = _blend(expected, samples, 'water_liters_per_hour', reading['hour'])
    observed = reading['water_liters_per_hour']
    ratio = observed / max(expected, 0.4)
    unexplained = max(0.0, observed - appliance_water - temp_extra)
    tank_delta = reading['tank_percent'] - reading['tank_previous_percent']
    pump_on = any(item.is_active and item.kind == Appliance.Kind.PUMP for item in appliances)
    explained = appliance_water > 0 or temp_extra >= 0.4
    kind = AnomalyEvent.Type.NORMAL
    if tank_delta >= 5 and observed >= max(quiet, 0.4) * 1.2:
        kind = AnomalyEvent.Type.TANK_FILLING
    elif ratio <= 1.25:
        kind = AnomalyEvent.Type.NORMAL
    elif ratio <= 2.0 and explained and unexplained <= max(quiet * 1.8, appliance_water + temp_extra + quiet):
        kind = AnomalyEvent.Type.HIGH_LEGITIMATE
    elif ratio >= 3.5 and tank_delta < 5:
        kind = AnomalyEvent.Type.CRITICAL
    else:
        kind = AnomalyEvent.Type.POSSIBLE_LEAK
    return _pack(
        AnomalyEvent.Resource.WATER,
        kind,
        observed,
        expected,
        ratio,
        _water_summary(kind, observed, expected, pump_on),
        reading,
    )


def _energy_decision(home, appliances, samples, reading):
    standing = 60 + 20 * home.residents + (25 if home.has_kitchen else 0)
    morning, evening = _peaks(reading['hour'])
    peak_load = standing * (0.25 * morning + 0.55 * evening)
    active = [item for item in appliances if item.is_active]
    appliance_watts = sum(item.power_watts for item in active)
    appliance_draw = appliance_watts * (0.7 + 0.3 * evening)
    ac_on = any(item.kind == Appliance.Kind.AC for item in active)
    hot = max(0.0, reading['temperature_c'] - 28)
    cooling = hot * (6 * home.residents + 0.15 * float(home.area_m2)) * (1.6 if ac_on else 0.25)
    expected = standing + peak_load + appliance_draw + cooling
    expected = _blend(expected, samples, 'energy_watts', reading['hour'])
    observed = reading['energy_watts']
    ratio = observed / max(expected, 1)
    explained = appliance_watts >= 50 or cooling >= 20
    if ratio <= 1.35:
        kind = AnomalyEvent.Type.NORMAL
    elif ratio < 2.5 and explained:
        kind = AnomalyEvent.Type.HIGH_LEGITIMATE
    elif ratio >= 2.5 and not explained:
        kind = AnomalyEvent.Type.CRITICAL
    elif ratio >= 3.5:
        kind = AnomalyEvent.Type.CRITICAL
    elif explained:
        kind = AnomalyEvent.Type.HIGH_LEGITIMATE
    else:
        kind = AnomalyEvent.Type.CRITICAL
    summary = _energy_summary(kind, observed, expected)
    return _pack(AnomalyEvent.Resource.ENERGY, kind, observed, expected, ratio, summary, reading)


def _pack(resource, kind, observed, expected, ratio, summary, reading):
    severity = {
        AnomalyEvent.Type.NORMAL: AnomalyEvent.Severity.INFO,
        AnomalyEvent.Type.HIGH_LEGITIMATE: AnomalyEvent.Severity.INFO,
        AnomalyEvent.Type.TANK_FILLING: AnomalyEvent.Severity.WATCH,
        AnomalyEvent.Type.POSSIBLE_LEAK: AnomalyEvent.Severity.WARNING,
        AnomalyEvent.Type.CRITICAL: AnomalyEvent.Severity.CRITICAL,
    }[kind]
    confidence = _confidence(kind, ratio, reading)
    return {
        'resource': resource,
        'type': kind,
        'severity': severity,
        'confidence': confidence,
        'source': AnomalyEvent.Source.RULES,
        'summary': summary,
        'observed': round(float(observed), 2),
        'baseline': round(float(expected), 2),
        'ratio': round(float(ratio), 2),
    }


def _confidence(kind, ratio, reading):
    if kind == AnomalyEvent.Type.NORMAL:
        return 0.0
    if kind == AnomalyEvent.Type.HIGH_LEGITIMATE:
        value = 0.62
    elif kind == AnomalyEvent.Type.TANK_FILLING:
        value = 0.74
    elif kind == AnomalyEvent.Type.POSSIBLE_LEAK:
        value = 0.58 + min(0.2, max(0.0, ratio - 1.6) * 0.08)
    else:
        value = 0.78 + min(0.14, max(0.0, ratio - 3.5) * 0.03)
    if reading.get('history_count', 0) >= 8:
        value += 0.04
    return round(_clamp(value, 0.5, 0.93), 2)


def _water_summary(kind, observed, expected, pump_on):
    observed_text = f'{observed:.1f} L/h'
    baseline_text = f'{expected:.1f} L/h'
    if kind == AnomalyEvent.Type.NORMAL:
        return f'Water {observed_text} is inside this home baseline of {baseline_text}.'
    if kind == AnomalyEvent.Type.HIGH_LEGITIMATE:
        return (
            f'Water {observed_text} is above a quiet hour, and it fits this home baseline '
            f'of {baseline_text} once appliances, time, and temperature are included.'
        )
    if kind == AnomalyEvent.Type.TANK_FILLING:
        pump = ' The pump is on.' if pump_on else ''
        return (
            f'Water {observed_text} is high and the tank level is rising, against a baseline '
            f'of {baseline_text}. Treated as tank filling, not a leak.{pump}'
        )
    if kind == AnomalyEvent.Type.POSSIBLE_LEAK:
        return (
            f'Water {observed_text} is above this home baseline of {baseline_text} '
            'and is not explained by appliances or by tank filling. Possible leak.'
        )
    return (
        f'Water {observed_text} is far above this home baseline of {baseline_text} '
        'and the tank is not filling. Critical abnormal consumption.'
    )


def _energy_summary(kind, observed, expected):
    observed_text = f'{observed:.0f} W'
    baseline_text = f'{expected:.0f} W'
    if kind == AnomalyEvent.Type.NORMAL:
        return f'Energy {observed_text} is inside this home baseline of {baseline_text}.'
    if kind == AnomalyEvent.Type.HIGH_LEGITIMATE:
        return (
            f'Energy {observed_text} is high and still fits this home baseline of {baseline_text} '
            'for the appliances, hour, and temperature.'
        )
    return (
        f'Energy {observed_text} is far above this home baseline of {baseline_text}. '
        'Critical abnormal consumption.'
    )


def _structural_water(home):
    return (
        2.0 * home.residents
        + 0.6 * home.bathrooms
        + (1.2 if home.has_kitchen else 0)
        + (1.0 if home.has_garden else 0)
        + (2.5 if home.has_pool else 0)
        + 0.004 * float(home.area_m2)
    )


def _peaks(hour):
    morning = math.exp(-((hour - 7) ** 2) / 6)
    evening = math.exp(-((hour - 20) ** 2) / 8)
    return morning, evening


def _blend(expected, samples, field, hour):
    window = [
        getattr(sample, field)
        for sample in samples
        if _hour_distance(sample.hour, hour) <= SAME_HOUR
    ]
    if len(window) < 8:
        return expected
    return 0.4 * expected + 0.6 * float(np.mean(window))


def _hour_distance(left, right):
    gap = abs(int(left) - int(right)) % 24
    return min(gap, 24 - gap)


def _forest_outlier(samples, reading):
    if len(samples) < FOREST_MIN_ROWS:
        return False
    from sklearn.ensemble import IsolationForest

    rows = [
        [
            sample.water_liters_per_hour,
            sample.energy_watts,
            sample.hour,
            sample.temperature_c,
            sample.tank_percent,
        ]
        for sample in samples
    ]
    model = IsolationForest(
        n_estimators=80,
        contamination=0.08,
        random_state=20260601,
        n_jobs=1,
    )
    model.fit(rows)
    point = [[
        reading['water_liters_per_hour'],
        reading['energy_watts'],
        reading['hour'],
        reading['temperature_c'],
        reading['tank_percent'],
    ]]
    return int(model.predict(point)[0]) == -1


def _clamp(value, low, high):
    return max(low, min(high, value))
