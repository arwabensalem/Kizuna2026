"""Resource passports from stored simulation hours and saved site records.

A score is a ratio of those quantities, or it is left blank. Nothing here is
drawn at random.
"""

from django.db.models import Sum

from apps.accounts.permissions import user_is_admin
from apps.crisis.lab import crop_stress
from apps.farms.models import Farm
from apps.farms.simulation import IDEAL_MOISTURE, simulate_farm
from apps.homes.models import Home
from apps.homes.simulation import simulate_home
from apps.marketplace.network import (
    WORKSHOP_DAY_W,
    WORKSHOP_NIGHT_W,
    WORKSHOP_OPEN,
    WORKSHOP_SOLAR_W,
    hour_flows,
)
from apps.simulation import engine
from apps.simulation.models import SimulationStep
from apps.simulation.services import current_state
from apps.weather.models import WaterRecovery

LABEL = (
    'Every score is a ratio of stored simulation hours or of figures saved on that site. '
    'A blank score means that quantity is not in the data. Nothing on this page is random.'
)

HOME_FIELDS = (
    ('water_efficiency', 'Water efficiency'),
    ('energy_efficiency', 'Energy efficiency'),
    ('renewable_production', 'Renewable production'),
    ('water_recovery', 'Water recovery'),
    ('resilience', 'Resilience'),
)
FARM_FIELDS = (
    ('water_productivity', 'Water productivity'),
    ('solar_autonomy', 'Solar autonomy'),
    ('crop_resilience', 'Crop resilience'),
    ('resource_efficiency', 'Resource efficiency'),
)
BUSINESS_FIELDS = (
    ('water_efficiency', 'Water efficiency'),
    ('energy_efficiency', 'Energy efficiency'),
    ('renewable_contribution', 'Renewable contribution'),
    ('recovery', 'Recovery'),
    ('resilience', 'Resilience'),
)


def build_passports(user):
    current_state()
    steps = list(SimulationStep.objects.order_by('hour'))
    totals = _replay(steps)
    period = _period(steps)
    cards = [
        _clock_home(totals, period),
        _clock_farm(totals, period),
        _clock_business(totals, period),
    ]
    cards.extend(_owned(user))
    return {
        'simulated': True,
        'label': LABEL,
        'period': period,
        'passports': cards,
    }


def _replay(steps):
    totals = {
        'home_use_l': 0.0,
        'garden_l': 0.0,
        'captured_l': 0.0,
        'home_solar_wh': 0.0,
        'home_direct_wh': 0.0,
        'home_battery_wh': 0.0,
        'home_grid_wh': 0.0,
        'home_load_wh': 0.0,
        'home_resilience': [],
        'farm_drawn_l': 0.0,
        'farm_mains_l': 0.0,
        'farm_solar_wh': 0.0,
        'farm_battery_wh': 0.0,
        'farm_grid_wh': 0.0,
        'soils': [],
        'stresses': [],
        'biz_solar_wh': 0.0,
        'biz_direct_wh': 0.0,
        'biz_grid_wh': 0.0,
        'biz_load_wh': 0.0,
        'biz_resilience': [],
    }
    previous = None
    for step in steps:
        payload = step.payload
        flows, _status, _totals = hour_flows(payload, previous)
        by_edge = {(item['source'], item['destination'], item['resource']): item['quantity'] for item in flows}
        totals['home_use_l'] += by_edge.get(('tank_a', 'home_a', 'water'), 0)
        totals['garden_l'] += by_edge.get(('tank_a', 'garden_a', 'water'), 0)
        totals['captured_l'] += by_edge.get(('roof_a', 'tank_a', 'water'), 0)
        totals['home_direct_wh'] += by_edge.get(('solar_a', 'home_a', 'energy'), 0)
        totals['home_battery_wh'] += by_edge.get(('battery_a', 'home_a', 'energy'), 0)
        totals['home_grid_wh'] += by_edge.get(('grid', 'home_a', 'energy'), 0)
        totals['home_solar_wh'] += payload['solar']['home_watts']
        totals['home_load_wh'] += payload['consumption']['home_electricity_watts']
        totals['home_resilience'].append(_home_resilience(payload))
        for destination in ('pump_b', 'farm_b'):
            totals['farm_drawn_l'] += by_edge.get(('tank_b', destination, 'water'), 0)
            totals['farm_solar_wh'] += by_edge.get(('solar_b', destination, 'energy'), 0)
            totals['farm_battery_wh'] += by_edge.get(('battery_b', destination, 'energy'), 0)
            totals['farm_grid_wh'] += by_edge.get(('grid', destination, 'energy'), 0)
        totals['farm_mains_l'] += by_edge.get(('mains', 'tank_b', 'water'), 0)
        soil = payload['soil_moisture']
        sensors = payload['sensors']['farm']
        totals['soils'].append(soil)
        totals['stresses'].append(crop_stress(
            soil,
            sensors['temperature']['value'],
            sensors['humidity']['value'],
            sensors['rainfall']['value'],
        ))
        _add_workshop(totals, payload)
        previous = payload
    return totals


def hour_scores(payload):
    """One stored hour, scored the same way as the passports.

    Home resilience is the tank and battery rule. Farm resilience is 100 minus
    the crop-stress formula. Business resilience is the share of the workshop
    load that solar or the grid served. The signals are the hourly inputs a
    neighbourhood weights with its own profile.
    """
    grid_on = payload['sensors']['grid']['grid_availability']['value'] > 0
    battery = payload['batteries']['home_percent']
    energy = battery if not grid_on else battery * 0.5 + 50
    soil = payload['soil_moisture']
    sensors = payload['sensors']['farm']
    temperature = payload['sensors']['home']['temperature']['value']
    clock = payload['hour'] % 24
    load = WORKSHOP_DAY_W if WORKSHOP_OPEN[0] <= clock < WORKSHOP_OPEN[1] else WORKSHOP_NIGHT_W
    solar = WORKSHOP_SOLAR_W * payload['solar']['home_watts'] / engine.HOME_SOLAR_WATTS
    direct = min(solar, load)
    grid = max(0.0, load - direct) if grid_on else 0.0
    return {
        'home': (payload['tanks']['home_percent'] + energy) / 2,
        'farm': max(0.0, min(100.0, 100 - crop_stress(
            soil,
            sensors['temperature']['value'],
            sensors['humidity']['value'],
            sensors['rainfall']['value'],
        ))),
        'business': 100.0 * (direct + grid) / load if load else 100.0,
        'signals': {
            'water': payload['tanks']['home_percent'],
            'energy': energy,
            'agriculture': min(100.0, soil / IDEAL_MOISTURE * 100),
            'climate': max(0.0, min(100.0, 100 - abs(temperature - 24) * 4)),
        },
        'home_use_l': payload['consumption']['home_water_liters_per_hour'],
    }


def _home_resilience(payload):
    grid_on = payload['sensors']['grid']['grid_availability']['value'] > 0
    battery = payload['batteries']['home_percent']
    energy = battery if not grid_on else battery * 0.5 + 50
    return (payload['tanks']['home_percent'] + energy) / 2


def _add_workshop(totals, payload):
    clock = payload['hour'] % 24
    load = WORKSHOP_DAY_W if WORKSHOP_OPEN[0] <= clock < WORKSHOP_OPEN[1] else WORKSHOP_NIGHT_W
    solar = WORKSHOP_SOLAR_W * payload['solar']['home_watts'] / engine.HOME_SOLAR_WATTS
    direct = min(solar, load)
    grid_on = payload['sensors']['grid']['grid_availability']['value'] > 0
    grid = max(0.0, load - direct) if grid_on else 0.0
    served = direct + grid
    totals['biz_solar_wh'] += solar
    totals['biz_direct_wh'] += direct
    totals['biz_grid_wh'] += grid
    totals['biz_load_wh'] += load
    totals['biz_resilience'].append(100.0 * served / load if load else 100.0)


def _clock_home(totals, period):
    on_site = totals['home_direct_wh'] + totals['home_battery_wh']
    served = on_site + totals['home_grid_wh']
    metrics = {
        'water_efficiency': _metric(
            _ratio(totals['home_use_l'], totals['home_use_l'] + totals['garden_l']),
            f"{totals['home_use_l']:.0f} L served the house and {totals['garden_l']:.0f} L went to the garden.",
            'Share of tank water that served the house rather than the garden.',
        ),
        'energy_efficiency': _metric(
            _ratio(on_site, served),
            f"{on_site:.0f} Wh from solar and the battery, {totals['home_grid_wh']:.0f} Wh from the grid.",
            'Share of the served home load that did not come from the grid. The clock stores served watts.',
        ),
        'renewable_production': _metric(
            _ratio(totals['home_solar_wh'], totals['home_load_wh']),
            f"{totals['home_solar_wh'] / 1000:.2f} kWh generated against {totals['home_load_wh'] / 1000:.2f} kWh used.",
            'Home solar over the stored hours, divided by home electricity use, capped at 100.',
        ),
        'water_recovery': _metric(
            _ratio(totals['captured_l'], totals['home_use_l']),
            f"{totals['captured_l']:.0f} L estimated roof capture against {totals['home_use_l']:.0f} L of household use.",
            'Roof capture from the resource network, divided by household use, capped at 100.',
        ),
        'resilience': _metric(
            None if _mean(totals['home_resilience']) is None else _clamp(_mean(totals['home_resilience'])),
            'Each hour is half the home tank and half the home battery, with the grid counted when it is up.',
            'Mean of those hours.',
        ),
    }
    return _card('clock-home', 'home', 'Home A', 'Lafayette · Tunis', 'Shared simulation clock', period, HOME_FIELDS, metrics)


def _clock_farm(totals, period):
    on_site = totals['farm_solar_wh'] + totals['farm_battery_wh']
    served = on_site + totals['farm_grid_wh']
    autonomy = _ratio(on_site, served)
    stored_share = _ratio(totals['farm_drawn_l'], totals['farm_drawn_l'] + totals['farm_mains_l'])
    productivity = _ratio(_mean(totals['soils']) or 0, IDEAL_MOISTURE) if totals['soils'] else None
    if productivity is not None:
        productivity = min(100.0, productivity)
    crop = None if not totals['stresses'] else _clamp(100 - _mean(totals['stresses']))
    parts = [value for value in (autonomy, stored_share) if value is not None]
    efficiency = _clamp(sum(parts) / len(parts)) if parts else None
    mean_soil = _mean(totals['soils'])
    mean_stress = _mean(totals['stresses'])
    soil_text = '—' if mean_soil is None else f'{mean_soil:.1f}'
    stress_text = '—' if mean_stress is None else f'{mean_stress:.1f}'
    metrics = {
        'water_productivity': _metric(
            productivity,
            f"Mean soil {soil_text}% against the {IDEAL_MOISTURE}% ideal. {totals['farm_drawn_l']:.0f} L left the farm tank.",
            'Mean soil moisture divided by the ideal already used in the farm snapshot, capped at 100.',
        ),
        'solar_autonomy': _metric(
            autonomy,
            f"{on_site:.0f} Wh from the farm solar and battery, {totals['farm_grid_wh']:.0f} Wh from the grid.",
            'Share of the served pump and farm load that did not come from the grid.',
        ),
        'crop_resilience': _metric(
            crop,
            f"Mean crop stress {stress_text} from the project crop-stress formula.",
            '100 minus that mean stress.',
        ),
        'resource_efficiency': _metric(
            efficiency,
            'Mean of solar autonomy and the share of farm-tank draw that was not matched by mains refill.',
            'Only those two ratios. No third input.',
        ),
    }
    return _card('clock-farm', 'farm', 'Farm B', 'Lafayette · Tunis', 'Shared simulation clock', period, FARM_FIELDS, metrics)


def _clock_business(totals, period):
    metrics = {
        'water_efficiency': _metric(None, 'The workshop simulation does not record water use.', 'No water series, so no score.'),
        'energy_efficiency': _metric(
            _ratio(totals['biz_direct_wh'], totals['biz_load_wh']),
            f"{totals['biz_direct_wh'] / 1000:.2f} kWh of the load was covered by workshop solar.",
            'Solar used on the load, divided by the workshop load.',
        ),
        'renewable_contribution': _metric(
            _ratio(totals['biz_solar_wh'], totals['biz_solar_wh'] + totals['biz_grid_wh']),
            f"{totals['biz_solar_wh'] / 1000:.2f} kWh solar and {totals['biz_grid_wh'] / 1000:.2f} kWh from the grid.",
            'Workshop solar divided by solar plus grid input.',
        ),
        'recovery': _metric(None, 'No recovery flow is recorded for this workshop.', 'No recovery series, so no score.'),
        'resilience': _metric(
            None if _mean(totals['biz_resilience']) is None else _clamp(_mean(totals['biz_resilience'])),
            'Each hour is the share of the workshop load that solar or the grid could serve.',
            'Mean of those hours. The same workshop rules as the resource network.',
        ),
    }
    return _card(
        'clock-business', 'business', 'Workshop C', 'Lafayette · Tunis',
        'Shared simulation clock', period, BUSINESS_FIELDS, metrics,
    )


def _owned(user):
    homes = Home.objects.all() if user_is_admin(user) else Home.objects.filter(owner=user)
    farms = Farm.objects.all() if user_is_admin(user) else Farm.objects.filter(owner=user)
    cards = []
    for home in homes.prefetch_related('appliances'):
        cards.append(_saved_home(home))
    for farm in farms.prefetch_related('tanks', 'solar_units', 'irrigation_systems', 'farm_sensors'):
        cards.append(_saved_farm(farm))
    return cards


def _saved_home(home):
    snapshot = simulate_home(home)
    load = snapshot['energy_watts']
    solar = snapshot['solar_watts']
    recovered = WaterRecovery.objects.filter(timeline__home=home).aggregate(total=Sum('recovered_liters'))['total']
    recovered_l = float(recovered or 0)
    metrics = {
        'water_efficiency': _metric(
            None,
            f"{snapshot['water_liters_per_hour']} L/h from the appliances saved on this home.",
            'The snapshot has a use, not a separate loss, so efficiency is not scored.',
        ),
        'energy_efficiency': _metric(
            None,
            f"{load} W drawn by saved appliances.",
            'No loss figure is stored beside that load, so efficiency is not scored.',
        ),
        'renewable_production': _metric(
            _ratio(solar, load),
            f"{solar} W solar against {load} W of appliance load.",
            'Solar from the home snapshot divided by appliance load, capped at 100.',
        ),
        'water_recovery': _metric(
            None,
            f"{recovered_l:.0f} L stored on this home's weather timeline." if recovered_l else 'No recovered water is stored for this home.',
            'Recovery liters are shown. There is no paired household total, so recovery is not scored.',
        ),
        'resilience': _metric(
            float(snapshot['resilience_score']),
            f"Tank {snapshot['tank_percent']}%, battery {snapshot['battery_percent']}%.",
            'The resilience figure already returned by the home snapshot.',
        ),
    }
    return _card(
        f'home-{home.pk}', 'home', home.name, 'Registered home',
        'Rooms and appliances saved on this home', 'Current snapshot', HOME_FIELDS, metrics,
    )


def _saved_farm(farm):
    snapshot = simulate_farm(farm)
    productivity = min(100.0, _ratio(snapshot['soil_moisture'], IDEAL_MOISTURE))
    stress = snapshot['crop_stress']
    metrics = {
        'water_productivity': _metric(
            productivity,
            f"Soil {snapshot['soil_moisture']}% and {snapshot['water_liters_per_day']} L/day from the saved farm.",
            'Soil moisture divided by the 45% ideal, capped at 100.',
        ),
        'solar_autonomy': _metric(
            None,
            f"{snapshot['solar_watts']} W from the saved arrays. No farm load is stored beside it.",
            'Autonomy needs a load, so it is not scored.',
        ),
        'crop_resilience': _metric(
            _clamp(100 - stress),
            f"Crop stress {stress} from the farm snapshot. Status {snapshot['crop_status']}.",
            '100 minus that stress.',
        ),
        'resource_efficiency': _metric(
            None,
            'Solar autonomy has no load to divide by, so this mean is not scored.',
            'Needs both solar autonomy and the stored-water share.',
        ),
    }
    return _card(
        f'farm-{farm.pk}', 'farm', farm.name, farm.location or 'Registered farm',
        'Farm, tanks, solar, and irrigation saved on this farm', 'Current snapshot', FARM_FIELDS, metrics,
    )


def _card(card_id, kind, name, place, source, period, fields, metrics):
    return {
        'id': card_id,
        'kind': kind,
        'name': name,
        'place': place,
        'source': source,
        'period': period,
        'metrics': [{'key': key, 'label': label, **metrics[key]} for key, label in fields],
    }


def _metric(score, detail, rule):
    return {'score': score, 'detail': detail, 'rule': rule}


def _period(steps):
    if not steps:
        return 'No stored hour'
    first, last = steps[0], steps[-1]
    return f"Hours {first.hour}–{last.hour} · {last.scenario}"


def _ratio(part, whole):
    if not whole:
        return None
    return _clamp(100 * part / whole)


def _mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def _clamp(value):
    return round(max(0.0, min(100.0, float(value))), 1)
