"""Turn a simulated forecast into rain preparation and recovered water.

One millimetre of rain on one square metre is one litre. The capture share
then keeps part of that volume. Both numbers are scenario settings.
"""

from decimal import Decimal

from django.db import transaction

from apps.actuators.engine import _sync, current_mode, ensure_actuators
from apps.actuators.models import Actuator
from apps.weather.models import (
    CollectionSystem,
    WaterRecovery,
    WeatherAction,
    WeatherHour,
    WeatherTimeline,
)
from apps.weather.scenarios import SCENARIOS

HORIZON = 4
ONE = Decimal('0.1')


def scenario_choices():
    return [(key, value['label']) for key, value in SCENARIOS.items()]


def ensure_collection(home, farm):
    if home is not None:
        defaults = _home_defaults(home)
        lookup = {'home': home}
    elif farm is not None:
        defaults = _farm_defaults(farm)
        lookup = {'farm': farm}
    else:
        raise ValueError('Choose a home or a farm.')
    system, _created = CollectionSystem.objects.get_or_create(**lookup, defaults=defaults)
    return system


def start_timeline(home, farm, scenario):
    if scenario not in SCENARIOS:
        raise ValueError(scenario)
    with transaction.atomic():
        collection = _locked(home, farm)
        timeline = WeatherTimeline.objects.create(
            home=home,
            farm=farm,
            scenario=scenario,
            hour=0,
            source='simulation',
        )
        WeatherHour.objects.bulk_create([
            WeatherHour(timeline=timeline, **row)
            for row in build_series(scenario)
        ])
        actions, recovery = _step(timeline, collection, home, farm, collect=True)
    return timeline, actions, recovery


def advance_timeline(timeline):
    last = timeline.hours.order_by('-hour').values_list('hour', flat=True).first()
    if last is None or timeline.hour >= last:
        return timeline, [], None
    with transaction.atomic():
        timeline = WeatherTimeline.objects.select_for_update().get(pk=timeline.pk)
        collection = _locked(timeline.home, timeline.farm)
        timeline.hour += 1
        timeline.save(update_fields=['hour'])
        actions, recovery = _step(timeline, collection, timeline.home, timeline.farm, collect=True)
    return timeline, actions, recovery


def build_series(scenario):
    rows = []
    for hour, values in enumerate(SCENARIOS[scenario]['hours']):
        temperature, humidity, probability, rain, solar, wind = values
        rows.append({
            'hour': hour,
            'temperature_c': _q(temperature),
            'humidity_percent': humidity,
            'rainfall_probability': probability,
            'rainfall_mm': _q(rain),
            'solar_radiation_wm2': solar,
            'wind_kmh': wind,
        })
    return rows


def rain_eta(hours, current):
    """Hours until the next rainfall, when it falls inside the 4-hour window."""
    for item in hours:
        if item.hour < current:
            continue
        if item.hour > current + HORIZON:
            return None
        if item.rainfall_mm > 0:
            return item.hour - current
    return None


def describe(timeline):
    current = timeline.hours.get(hour=timeline.hour)
    eta = rain_eta(timeline.hours.order_by('hour'), timeline.hour)
    if timeline.mode == WeatherTimeline.Mode.RAIN_PREPARATION and eta:
        unit = 'hour' if eta == 1 else 'hours'
        return f'RAIN PREPARATION MODE. Rain expected in {eta} {unit}.'
    if timeline.mode == WeatherTimeline.Mode.COLLECTING:
        return f'Rain is falling in this simulated hour ({current.rainfall_mm} mm).'
    if current.rainfall_mm > 0:
        return (
            'Simulated rain is falling. The collection system is not prepared, '
            'so the tank was not changed.'
        )
    return 'No rain is expected in the next 4 simulated hours.'


def recovered_label(liters):
    return f'+ {Decimal(liters):.1f} L recovered'


def _step(timeline, collection, home, farm, collect):
    hours = list(timeline.hours.order_by('hour'))
    eta = rain_eta(hours, timeline.hour)
    actions = _prepare(timeline, collection, home, farm, eta)
    recovery = None
    current = hours[timeline.hour]
    if collect and current.rainfall_mm > 0:
        action, recovery = _collect(timeline, collection, current)
        actions.append(action)
    _set_mode(timeline, collection, eta, current)
    return actions, recovery


def _prepare(timeline, collection, home, farm, eta):
    if eta is None:
        return []
    phrase = _phrase(eta)
    if not timeline.preparation_logged:
        actions = [
            _suspend(timeline, home, farm, phrase),
            _ready_path(timeline, collection, phrase),
            _check_tank(timeline, collection, phrase),
            _prepare_system(timeline, collection, phrase),
        ]
        timeline.preparation_logged = True
        timeline.save(update_fields=['preparation_logged'])
        return actions
    if collection.authorized and not collection.prepared:
        return [_prepare_system(timeline, collection, phrase)]
    return []


def _phrase(eta):
    if eta == 0:
        return 'Rain is in this simulated hour.'
    unit = 'hour' if eta == 1 else 'hours'
    return f'Rain expected in {eta} {unit}.'


def _suspend(timeline, home, farm, phrase):
    pump = ensure_actuators(home, farm)[Actuator.Kind.IRRIGATION_PUMP]
    previous = pump.state
    mode = current_mode(home, farm)
    reason = f'{phrase} Suspend unnecessary irrigation.'
    new_state = previous
    if mode == 'assist' or not pump.authorized:
        if mode == 'assist':
            reason += ' Assist mode only alerts. The pump was not changed.'
        else:
            reason += ' The irrigation pump is not authorized. It was not changed.'
    else:
        new_state = 'off'
        if pump.state != 'off':
            pump.state = 'off'
            pump.save(update_fields=['state'])
            _sync(pump)
        else:
            reason += ' Irrigation is already off.'
    return _action(timeline, 'suspend_irrigation', 'irrigation pump', previous, new_state, reason)


def _ready_path(timeline, collection, phrase):
    previous = 'ready' if collection.ready else 'idle'
    collection.ready = True
    collection.save(update_fields=['ready'])
    reason = f'{phrase} Prepare the rainwater collection path from the roof to the tank.'
    return _action(timeline, 'prepare_collection', 'rainwater system', previous, 'ready', reason)


def _check_tank(timeline, collection, phrase):
    free = _q(Decimal(collection.tank_capacity_liters) - collection.tank_liters)
    state = f'{collection.tank_liters:.1f} / {collection.tank_capacity_liters} L'
    reason = (
        f'{phrase} Check tank capacity. The tank holds {collection.tank_liters:.1f} L '
        f'of {collection.tank_capacity_liters} L, with {free:.1f} L free.'
    )
    return _action(timeline, 'check_tank', 'tank', state, state, reason)


def _prepare_system(timeline, collection, phrase):
    previous = 'prepared' if collection.prepared else 'not prepared'
    reason = f'{phrase} Prepare the authorized collection system.'
    new_state = previous
    if collection.authorized:
        collection.prepared = True
        collection.save(update_fields=['prepared'])
        new_state = 'prepared'
    else:
        reason += ' The collection system is not authorized. It was not prepared.'
    return _action(
        timeline,
        'prepare_collection_system',
        'collection system',
        previous,
        new_state,
        reason,
    )


def _collect(timeline, collection, hour):
    before = collection.tank_liters
    state = f'{before:.1f} L'
    if not collection.prepared:
        reason = (
            f'Simulated rain is {hour.rainfall_mm} mm this hour. '
            'The collection system is not prepared, so the tank was not changed.'
        )
        action = _action(timeline, 'collect_rainwater', 'tank', state, state, reason)
        return action, None
    offered = _q(collection.roof_area_m2 * hour.rainfall_mm * collection.capture_share)
    room = _q(Decimal(collection.tank_capacity_liters) - before)
    if room < 0:
        room = Decimal('0.0')
    added = offered if offered < room else room
    after = _q(before + added)
    collection.tank_liters = after
    collection.save(update_fields=['tank_liters'])
    recovery = WaterRecovery.objects.create(
        timeline=timeline,
        hour=hour.hour,
        rainfall_mm=hour.rainfall_mm,
        offered_liters=offered,
        recovered_liters=added,
        tank_before=before,
        tank_after=after,
    )
    leftover = _q(offered - added)
    reason = (
        f'Simulated rain is {hour.rainfall_mm} mm. '
        f'The roof passed {offered:.1f} L into the rainwater system, '
        f'and {added:.1f} L entered the tank.'
    )
    if leftover > 0:
        reason += f' {leftover:.1f} L did not fit.'
    action = _action(
        timeline,
        'collect_rainwater',
        'tank',
        f'{before:.1f} L',
        f'{after:.1f} L',
        reason,
        mode=WeatherTimeline.Mode.COLLECTING,
    )
    return action, recovery


def _set_mode(timeline, collection, eta, current):
    if current.rainfall_mm > 0 and collection.prepared:
        mode = WeatherTimeline.Mode.COLLECTING
    elif eta is not None:
        mode = WeatherTimeline.Mode.RAIN_PREPARATION
    else:
        mode = WeatherTimeline.Mode.STANDBY
    timeline.mode = mode
    timeline.save(update_fields=['mode'])


def _action(timeline, action, actuator, previous, new_state, reason, mode=None):
    return WeatherAction.objects.create(
        timeline=timeline,
        hour=timeline.hour,
        action=action,
        reason=reason,
        actuator=actuator,
        previous_state=previous,
        new_state=new_state,
        mode=mode or WeatherTimeline.Mode.RAIN_PREPARATION,
    )


def _locked(home, farm):
    system = ensure_collection(home, farm)
    return CollectionSystem.objects.select_for_update().get(pk=system.pk)


def _home_defaults(home):
    roof = min(Decimal(home.area_m2), Decimal('200'))
    return _defaults(roof, 2000)


def _farm_defaults(farm):
    capacity = farm.tank_capacity_liters or 5000
    return _defaults(Decimal('80'), capacity)


def _defaults(roof, capacity):
    tank = _q(Decimal(capacity) * Decimal('0.40'))
    return {
        'roof_area_m2': _q(roof),
        'capture_share': Decimal('0.80'),
        'tank_capacity_liters': capacity,
        'tank_liters': tank,
    }


def _q(value):
    return Decimal(str(value)).quantize(ONE)
