"""Load and store the synthetic clock.

`advance_simulation` is the one-hour step. It writes sensors, stocks,
actuators, and the crisis flag, and keeps each hour in SimulationStep.
"""

from django.db import transaction

from apps.simulation import engine
from apps.simulation.models import (
    SimulatedActuator,
    SimulatedSensor,
    SimulationClock,
    SimulationStep,
    SimulationStock,
)

LABEL = (
    'Synthetic simulation. Not a live meter reading and not a record of a real place.'
)
MAX_STEPS = 48


class SimulationError(ValueError):
    pass


def current_state():
    with transaction.atomic():
        _ensure()
        return _latest()


def advance_simulation(steps=1, scenario=None):
    """Move the synthetic clock forward by `steps` hours."""
    count = _steps(steps)
    chosen = _scenario(scenario)
    with transaction.atomic():
        clock = _ensure(lock=True)
        if chosen:
            clock.scenario = chosen
            clock.save(update_fields=['scenario'])
        stocks = _stocks()
        public = None
        for _ in range(count):
            raw = engine.advance_one(clock.seed, clock.hour, clock.scenario, stocks)
            stocks = raw.pop('stocks')
            public = _decorate(raw)
            _write(public, stocks)
            clock.hour = public['hour']
        return public


def reset_simulation(seed=None, scenario=None):
    """Return the clock to hour 0 for this seed and scenario."""
    chosen_seed = 20260601 if seed is None else _seed(seed)
    chosen_scenario = _scenario(scenario) or 'NORMAL'
    with transaction.atomic():
        clock = _ensure(lock=True)
        clock.seed = chosen_seed
        clock.scenario = chosen_scenario
        clock.save(update_fields=['seed', 'scenario'])
        SimulationStep.objects.all().delete()
        raw = engine.baseline(chosen_seed, chosen_scenario)
        stocks = raw.pop('stocks')
        public = _decorate(raw)
        _write(public, stocks)
        return public


def _ensure(lock=False):
    queryset = SimulationClock.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    clock, _created = queryset.get_or_create(
        pk=1,
        defaults={'hour': 0, 'scenario': 'NORMAL', 'seed': 20260601, 'crisis_state': 'none'},
    )
    if not SimulationStep.objects.exists():
        raw = engine.baseline(clock.seed, clock.scenario)
        stocks = raw.pop('stocks')
        _write(_decorate(raw), stocks)
        clock.refresh_from_db()
    return clock


def _latest():
    clock = SimulationClock.objects.get(pk=1)
    step = SimulationStep.objects.get(hour=clock.hour)
    return step.payload


def _decorate(raw):
    payload = dict(raw)
    payload['simulated'] = True
    payload['label'] = LABEL
    payload['step_hours'] = 1
    payload['simulated_at'] = engine.clock_time(payload['hour']).isoformat()
    return payload


def _write(public, stocks):
    clock = SimulationClock.objects.get(pk=1)
    clock.hour = public['hour']
    clock.scenario = public['scenario']
    clock.seed = public['seed']
    clock.crisis_state = public['crisis_state']
    clock.save()

    kept = []
    for group, sensors in public['sensors'].items():
        for key, sensor in sensors.items():
            row, _created = SimulatedSensor.objects.update_or_create(
                group=group,
                key=key,
                defaults={
                    'label': sensor['label'],
                    'value_text': str(sensor['value']),
                    'unit': sensor['unit'],
                    'hour': public['hour'],
                },
            )
            kept.append(row.pk)
    SimulatedSensor.objects.exclude(pk__in=kept).delete()

    for key, value in stocks.items():
        SimulationStock.objects.update_or_create(
            key=key,
            defaults={'value': value, 'hour': public['hour']},
        )

    actuators = {
        'farm_pump': public['pump']['farm'],
        'home_valve': public['valves']['home'],
        'farm_valve': public['valves']['farm'],
    }
    for key, state in actuators.items():
        SimulatedActuator.objects.update_or_create(
            key=key,
            defaults={'state': state, 'hour': public['hour']},
        )

    SimulationStep.objects.update_or_create(
        hour=public['hour'],
        defaults={
            'scenario': public['scenario'],
            'crisis_state': public['crisis_state'],
            'payload': public,
        },
    )


def _stocks():
    found = {row.key: row.value for row in SimulationStock.objects.all()}
    stocks = dict(engine.INITIAL_STOCKS)
    stocks.update(found)
    return stocks


def _steps(value):
    if value in (None, ''):
        return 1
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise SimulationError('steps must be a whole number.') from exc
    if count < 1 or count > MAX_STEPS:
        raise SimulationError(f'steps must be from 1 to {MAX_STEPS}.')
    return count


def _scenario(value):
    if value in (None, ''):
        return None
    if value not in engine.SCENARIOS:
        allowed = ', '.join(engine.SCENARIOS)
        raise SimulationError(f'Unknown scenario. Choose one of: {allowed}.')
    return value


def _seed(value):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SimulationError('seed must be a whole number.') from exc
    if number < 0 or number > 2_000_000_000:
        raise SimulationError('seed must be from 0 to 2000000000.')
    return number
