"""KIZUNA Resource Network: water and energy flows on the synthetic clock.

Every flow is derived from one stored SimulationStep and the hour before it,
so the same hour always gives the same flows.

- Local flows restate what the clock did in that hour (solar, batteries,
  tanks, pump, mains refill).
- Exchange flows are the KIZUNA Exchange cooperation layer. They only move
  solar energy the clock would have curtailed because a battery was full,
  and spare home tank water when the farm tank is low. They are not applied
  to the clock's stored levels.

Home D and Workshop C have no clock state of their own. Their load and
solar follow fixed synthetic profiles scaled from the clock's sun and demand.
"""

from apps.simulation import engine
from apps.simulation.models import SimulationClock, SimulationStep
from apps.simulation.services import current_state

LABEL = (
    'KIZUNA Exchange is a simulation of cooperation between resource nodes. '
    'It is not a real electricity or water market, and no money or credit changes hands.'
)
HISTORY_HOURS = 12

ROOF_M2 = 80
CAPTURE = 0.8
GARDEN_L = 40
GARDEN_HOUR = 19
GARDEN_MIN_TANK = 30
PUMP_LPH = 160
FARM_BASE_LPH = 12
PUMP_W = 700
FARM_BASE_W = 100
WORKSHOP_SOLAR_W = 5000
WORKSHOP_DAY_W = 1500
WORKSHOP_NIGHT_W = 150
WORKSHOP_OPEN = (8, 18)
NEIGHBOUR_SHARE = 0.8
WATER_SHARE_L = 150
FARM_TANK_LOW = 30
HOME_TANK_SPARE = 60
MIN_FLOW = 1

NODES = [
    {'key': 'rain', 'label': 'Rain', 'type': 'rain', 'site': 'Weather', 'x': 60, 'y': 70},
    {'key': 'roof_a', 'label': 'Roof A', 'type': 'roof', 'site': 'Home A', 'x': 180, 'y': 70},
    {'key': 'tank_a', 'label': 'Tank A', 'type': 'tank', 'site': 'Home A', 'x': 300, 'y': 70},
    {'key': 'garden_a', 'label': 'Garden A', 'type': 'garden', 'site': 'Home A', 'x': 420, 'y': 70},
    {'key': 'solar_a', 'label': 'Solar A', 'type': 'solar', 'site': 'Home A', 'x': 80, 'y': 250},
    {'key': 'home_a', 'label': 'Home A', 'type': 'home', 'site': 'Home A', 'x': 300, 'y': 250},
    {'key': 'battery_a', 'label': 'Battery A', 'type': 'battery', 'site': 'Home A', 'x': 80, 'y': 420},
    {'key': 'mains', 'label': 'Water network', 'type': 'mains', 'site': 'Utility', 'x': 530, 'y': 170},
    {'key': 'grid', 'label': 'Grid', 'type': 'grid', 'site': 'Utility', 'x': 530, 'y': 330},
    {'key': 'tank_b', 'label': 'Tank B', 'type': 'tank', 'site': 'Farm B', 'x': 680, 'y': 70},
    {'key': 'pump_b', 'label': 'Pump B', 'type': 'pump', 'site': 'Farm B', 'x': 820, 'y': 70},
    {'key': 'farm_b', 'label': 'Farm B', 'type': 'farm', 'site': 'Farm B', 'x': 930, 'y': 200},
    {'key': 'solar_b', 'label': 'Solar B', 'type': 'solar', 'site': 'Farm B', 'x': 680, 'y': 250},
    {'key': 'battery_b', 'label': 'Battery B', 'type': 'battery', 'site': 'Farm B', 'x': 820, 'y': 300},
    {'key': 'home_d', 'label': 'Home D', 'type': 'home', 'site': 'Home D', 'x': 330, 'y': 520},
    {'key': 'business_c', 'label': 'Workshop C', 'type': 'business', 'site': 'Workshop C', 'x': 720, 'y': 520},
    {'key': 'solar_c', 'label': 'Solar C', 'type': 'solar', 'site': 'Workshop C', 'x': 900, 'y': 450},
]
NODE_LABELS = {node['key']: node['label'] for node in NODES}

EDGES = [
    ('rain', 'roof_a', 'water'),
    ('roof_a', 'tank_a', 'water'),
    ('tank_a', 'garden_a', 'water'),
    ('tank_a', 'home_a', 'water'),
    ('mains', 'tank_a', 'water'),
    ('mains', 'tank_b', 'water'),
    ('tank_b', 'pump_b', 'water'),
    ('pump_b', 'farm_b', 'water'),
    ('tank_b', 'farm_b', 'water'),
    ('tank_a', 'tank_b', 'water'),
    ('solar_a', 'home_a', 'energy'),
    ('solar_a', 'battery_a', 'energy'),
    ('battery_a', 'home_a', 'energy'),
    ('grid', 'home_a', 'energy'),
    ('solar_b', 'pump_b', 'energy'),
    ('solar_b', 'farm_b', 'energy'),
    ('solar_b', 'battery_b', 'energy'),
    ('battery_b', 'pump_b', 'energy'),
    ('battery_b', 'farm_b', 'energy'),
    ('grid', 'pump_b', 'energy'),
    ('grid', 'farm_b', 'energy'),
    ('grid', 'home_d', 'energy'),
    ('grid', 'business_c', 'energy'),
    ('solar_c', 'business_c', 'energy'),
    ('home_a', 'farm_b', 'energy'),
    ('home_a', 'home_d', 'energy'),
    ('home_a', 'business_c', 'energy'),
    ('farm_b', 'home_d', 'energy'),
    ('farm_b', 'business_c', 'energy'),
    ('business_c', 'home_d', 'energy'),
    ('business_c', 'farm_b', 'energy'),
]
EXCHANGE_PRIORITY = ('farm_b', 'home_d', 'business_c')

ASSUMPTIONS = [
    'Home A, Farm B, their tanks, batteries, solar and pump follow the shared simulation clock.',
    f'Home D uses {NEIGHBOUR_SHARE:.0%} of Home A demand and has no solar or battery.',
    f'Workshop C has {WORKSHOP_SOLAR_W / 1000:.0f} kW of solar under the same sun as Home A, '
    f'{WORKSHOP_DAY_W} W load from {WORKSHOP_OPEN[0]}:00 to {WORKSHOP_OPEN[1]}:00 and {WORKSHOP_NIGHT_W} W otherwise.',
    'Exchange energy is solar the clock would have curtailed because the battery was already full.',
    f'Exchange water: {WATER_SHARE_L} L from Tank A when Tank B is below {FARM_TANK_LOW}% and Tank A is above {HOME_TANK_SPARE}%.',
    f'Roof capture is estimated as rainfall × {ROOF_M2} m² × {CAPTURE:.0%}. Garden watering is {GARDEN_L} L at {GARDEN_HOUR}:00 on dry hours.',
    'Exchange flows, roof capture, and garden watering are shown on the graph and are not written back into the clock levels.',
]


class NetworkError(ValueError):
    pass


def build_network(hour=None):
    current_state()
    clock = SimulationClock.objects.get(pk=1)
    selected = clock.hour if hour in (None, '') else _hour_value(hour)
    if selected > clock.hour:
        raise NetworkError(f'hour must be between 0 and {clock.hour}.')
    first = max(0, selected - HISTORY_HOURS)
    steps = {
        step.hour: step.payload
        for step in SimulationStep.objects.filter(hour__gte=max(0, first - 1), hour__lte=selected)
    }
    if selected not in steps:
        raise NetworkError(f'hour {selected} is not stored. Reset or advance the simulation.')

    payload = steps[selected]
    flows, status, totals = hour_flows(payload, steps.get(selected - 1))
    history = []
    for value in range(selected, first - 1, -1):
        if value in steps:
            history.extend(hour_flows(steps[value], steps.get(value - 1))[0])

    return {
        'simulated': True,
        'label': LABEL,
        'hour': selected,
        'latest_hour': clock.hour,
        'hours': list(
            SimulationStep.objects.filter(hour__lte=clock.hour).order_by('hour').values_list('hour', flat=True)
        ),
        'timestamp': payload['simulated_at'],
        'scenario': payload['scenario'],
        'crisis_state': payload['crisis_state'],
        'nodes': [dict(node, **status[node['key']]) for node in NODES],
        'edges': [
            {'source': source, 'destination': destination, 'resource': resource, 'exchange': _is_exchange(source, destination)}
            for source, destination, resource in EDGES
        ],
        'flows': flows,
        'totals': totals,
        'history': history,
        'assumptions': ASSUMPTIONS,
    }


def hour_flows(payload, prev):
    hour = payload['hour']
    clock = hour % 24
    timestamp = payload['simulated_at']
    grid_on = payload['sensors']['grid']['grid_availability']['value'] > 0
    rainfall = payload['sensors']['farm']['rainfall']['value']
    pump_on = payload['pump']['farm'] == 'on'
    flows = []

    def add(source, destination, resource, quantity, kind, note):
        if quantity < MIN_FLOW:
            return
        flows.append({
            'id': f'{hour}:{source}:{destination}:{resource}',
            'hour': hour,
            'timestamp': timestamp,
            'resource': resource,
            'source': source,
            'source_label': NODE_LABELS[source],
            'destination': destination,
            'destination_label': NODE_LABELS[destination],
            'quantity': round(quantity),
            'unit': 'Wh' if resource == 'energy' else 'L',
            'kind': kind,
            'note': note,
        })

    home = _energy_split(
        produced=payload['solar']['home_watts'],
        used=payload['consumption']['home_electricity_watts'],
        delta_wh=_delta(payload, prev, 'batteries', 'home_percent', engine.HOME_BATTERY_WH),
        level=payload['batteries']['home_percent'],
        grid_on=grid_on,
    )
    add('solar_a', 'home_a', 'energy', home['direct'], 'local', 'Solar covers the home load.')
    add('solar_a', 'battery_a', 'energy', home['stored'], 'local', 'Solar surplus charges the battery.')
    add('battery_a', 'home_a', 'energy', home['from_battery'], 'local', 'Battery covers the home load.')
    add('grid', 'home_a', 'energy', home['from_grid'], 'utility', 'Battery empty. Grid covers the rest.')

    farm_load = FARM_BASE_W + (PUMP_W if pump_on else 0)
    farm_solar = payload['solar']['farm_watts']
    if not grid_on and prev:
        farm_load = min(farm_load, farm_solar + prev['batteries']['farm_percent'] / 100 * engine.FARM_BATTERY_WH)
    farm = _energy_split(
        produced=farm_solar,
        used=farm_load,
        delta_wh=_delta(payload, prev, 'batteries', 'farm_percent', engine.FARM_BATTERY_WH),
        level=payload['batteries']['farm_percent'],
        grid_on=grid_on,
    )
    load_node = 'pump_b' if pump_on else 'farm_b'
    load_name = 'the pump' if pump_on else 'farm base load'

    workshop_open = WORKSHOP_OPEN[0] <= clock < WORKSHOP_OPEN[1]
    workshop_solar = WORKSHOP_SOLAR_W * payload['solar']['home_watts'] / engine.HOME_SOLAR_WATTS
    workshop_load = WORKSHOP_DAY_W if workshop_open else WORKSHOP_NIGHT_W
    workshop_direct = min(workshop_solar, workshop_load)
    neighbour_load = payload['consumption']['home_electricity_watts'] * NEIGHBOUR_SHARE

    offers = {'home_a': home['spill'], 'farm_b': farm['spill'], 'business_c': workshop_solar - workshop_direct}
    needs = {
        'farm_b': farm['from_battery'] + farm['from_grid'],
        'home_d': neighbour_load,
        'business_c': workshop_load - workshop_direct,
    }
    received = {key: 0.0 for key in needs}
    for taker in EXCHANGE_PRIORITY:
        for giver in ('home_a', 'farm_b', 'business_c'):
            if giver == taker or needs[taker] < MIN_FLOW or offers[giver] < MIN_FLOW:
                continue
            amount = min(offers[giver], needs[taker])
            offers[giver] -= amount
            needs[taker] -= amount
            received[taker] += amount
            add(giver, taker, 'energy', amount, 'exchange',
                f'Simulated energy surplus from {NODE_LABELS[giver]} (battery full) shared with {NODE_LABELS[taker]}.')

    farm_battery_draw = max(0.0, farm['from_battery'] - received['farm_b'])
    farm_grid_draw = max(0.0, farm['from_grid'] - max(0.0, received['farm_b'] - farm['from_battery']))
    add('solar_b', load_node, 'energy', farm['direct'], 'local', f'Solar powers {load_name}.')
    add('solar_b', 'battery_b', 'energy', farm['stored'], 'local', 'Solar surplus charges the farm battery.')
    add('battery_b', load_node, 'energy', farm_battery_draw, 'local', f'Battery powers {load_name}.')
    add('grid', load_node, 'energy', farm_grid_draw, 'utility', f'Battery empty. Grid powers {load_name}.')

    add('solar_c', 'business_c', 'energy', workshop_direct, 'local', 'Workshop solar covers its load.')
    neighbour_short = needs['home_d']
    workshop_short = needs['business_c']
    if grid_on:
        add('grid', 'home_d', 'energy', neighbour_short, 'utility', 'Grid covers the neighbour load.')
        add('grid', 'business_c', 'energy', workshop_short, 'utility', 'Grid covers the workshop load.')
    unmet = 0.0 if grid_on else neighbour_short + workshop_short

    home_water = payload['consumption']['home_water_liters_per_hour']
    home_tank = payload['tanks']['home_percent']
    farm_tank = payload['tanks']['farm_percent']
    farm_draw = PUMP_LPH if pump_on else FARM_BASE_LPH
    home_refill = _refill(payload, prev, 'home_percent', engine.HOME_TANK_LITERS, home_water)
    farm_refill = _refill(payload, prev, 'farm_percent', engine.FARM_TANK_LITERS, farm_draw)
    add('mains', 'tank_a', 'water', home_refill, 'utility', 'Water network refills the home tank.')
    add('mains', 'tank_b', 'water', farm_refill, 'utility', 'Water network refills the farm tank.')
    add('tank_a', 'home_a', 'water', home_water, 'local', 'Household water use.')
    if pump_on:
        add('tank_b', 'pump_b', 'water', PUMP_LPH, 'local', 'Pump draws from the farm tank.')
        add('pump_b', 'farm_b', 'water', PUMP_LPH, 'local', 'Irrigation reaches the field.')
    else:
        add('tank_b', 'farm_b', 'water', FARM_BASE_LPH, 'local', 'Farm base water use.')

    captured = 0.0
    if rainfall > 0:
        on_roof = rainfall * ROOF_M2
        room = max(0.0, (100 - home_tank) / 100 * engine.HOME_TANK_LITERS)
        captured = min(on_roof * CAPTURE, room)
        add('rain', 'roof_a', 'water', on_roof, 'local', f'{rainfall} mm of rain on the roof (estimate).')
        add('roof_a', 'tank_a', 'water', captured, 'local', 'Roof capture into the home tank (estimate).')
    garden = GARDEN_L if clock == GARDEN_HOUR and rainfall == 0 and home_tank >= GARDEN_MIN_TANK else 0
    add('tank_a', 'garden_a', 'water', garden, 'local', 'Evening garden watering from the tank.')

    shared_water = WATER_SHARE_L if farm_tank < FARM_TANK_LOW and home_tank > HOME_TANK_SPARE else 0
    add('tank_a', 'tank_b', 'water', shared_water, 'exchange',
        f'Tank B below {FARM_TANK_LOW}% and Tank A above {HOME_TANK_SPARE}%. Spare water shared.')

    curtailed = sum(offers.values())
    status = _status(
        payload, grid_on, rainfall, pump_on, home, farm, workshop_solar, workshop_load,
        neighbour_load, received, captured, garden, home_refill + farm_refill,
    )
    totals = {
        'energy_local_wh': round(sum(f['quantity'] for f in flows if f['resource'] == 'energy' and f['kind'] == 'local')),
        'energy_exchanged_wh': round(sum(f['quantity'] for f in flows if f['resource'] == 'energy' and f['kind'] == 'exchange')),
        'energy_grid_wh': round(sum(f['quantity'] for f in flows if f['resource'] == 'energy' and f['kind'] == 'utility')),
        'water_moved_l': round(sum(f['quantity'] for f in flows if f['resource'] == 'water' and f['source'] != 'rain')),
        'water_exchanged_l': round(shared_water),
        'rain_captured_l': round(captured),
        'curtailed_wh': round(curtailed),
        'unmet_wh': round(unmet),
        'flow_count': len(flows),
    }
    return flows, status, totals


def _energy_split(produced, used, delta_wh, level, grid_on):
    direct = min(produced, used)
    surplus = produced - direct
    deficit = used - direct
    if delta_wh is None:
        stored = 0.0 if level >= 100 else surplus
        from_battery = 0.0 if level <= 0 else deficit
    else:
        stored = min(surplus, max(0.0, delta_wh))
        from_battery = min(deficit, max(0.0, -delta_wh))
    shortfall = deficit - from_battery
    return {
        'direct': direct,
        'stored': stored,
        'spill': surplus - stored,
        'from_battery': from_battery,
        'from_grid': shortfall if grid_on else 0.0,
        'unmet': 0.0 if grid_on else shortfall,
    }


def _delta(payload, prev, group, key, capacity):
    if prev is None:
        return None
    return (payload[group][key] - prev[group][key]) / 100 * capacity


def _refill(payload, prev, key, capacity, drawn):
    if prev is None:
        return 0.0
    change = (payload['tanks'][key] - prev['tanks'][key]) / 100 * capacity
    return max(0.0, change + drawn)


def _status(payload, grid_on, rainfall, pump_on, home, farm, workshop_solar, workshop_load,
            neighbour_load, received, captured, garden, refill):
    tank_a = payload['tanks']['home_percent']
    tank_b = payload['tanks']['farm_percent']
    battery_a = payload['batteries']['home_percent']
    battery_b = payload['batteries']['farm_percent']
    soil = payload['soil_moisture']
    stress = payload['sensors']['grid']['grid_stress']['value']
    workshop_net = workshop_solar - workshop_load
    return {
        'rain': _state(f'{rainfall} mm', 'ok' if rainfall > 0 else 'idle', 'Rainfall this hour.'),
        'roof_a': _state(f'{captured:.0f} L', 'ok' if captured else 'idle', 'Estimated roof capture.'),
        'tank_a': _state(f'{tank_a:.0f}%', _low(tank_a, 25, 40), f'{tank_a / 100 * engine.HOME_TANK_LITERS:.0f} L of {engine.HOME_TANK_LITERS} L.'),
        'garden_a': _state('watered' if garden else 'dry hour' if rainfall == 0 else 'rain', 'ok' if garden or rainfall else 'idle', 'Garden watering.'),
        'solar_a': _state(f"{payload['solar']['home_watts']:.0f} W", 'ok' if payload['solar']['home_watts'] > 0 else 'idle', f'{engine.HOME_SOLAR_WATTS} W roof array.'),
        'home_a': _state(
            f"{payload['consumption']['home_electricity_watts']:.0f} W",
            'alert' if home['unmet'] >= MIN_FLOW else 'ok',
            f"{payload['consumption']['home_water_liters_per_hour']:.0f} L/h water. Valve {payload['valves']['home']}.",
        ),
        'battery_a': _state(f'{battery_a:.0f}%', _low(battery_a, 15, 30), 'Full: surplus goes to the Exchange.' if battery_a >= 100 else f'{engine.HOME_BATTERY_WH / 1000:.0f} kWh battery.'),
        'mains': _state(f'{refill:.0f} L', 'ok' if refill >= MIN_FLOW else 'idle', 'Refill into Tank A and Tank B this hour.'),
        'grid': _state(
            'available' if grid_on else 'outage',
            'alert' if not grid_on else 'watch' if stress >= 50 else 'ok',
            f'Grid stress {stress:.0f}%.',
        ),
        'tank_b': _state(f'{tank_b:.0f}%', _low(tank_b, 25, 40), f'{tank_b / 100 * engine.FARM_TANK_LITERS:.0f} L of {engine.FARM_TANK_LITERS} L.'),
        'pump_b': _state('on' if pump_on else 'off', 'ok' if pump_on else 'idle', f'{PUMP_LPH} L/h at {PUMP_W} W when on.'),
        'farm_b': _state(
            f'soil {soil:.0f}%',
            _low(soil, 25, 40),
            f"Received {received['farm_b']:.0f} Wh from the Exchange." if received['farm_b'] >= MIN_FLOW else 'Soil moisture.',
        ),
        'solar_b': _state(f"{payload['solar']['farm_watts']:.0f} W", 'ok' if payload['solar']['farm_watts'] > 0 else 'idle', f'{engine.FARM_SOLAR_WATTS} W field array.'),
        'battery_b': _state(f'{battery_b:.0f}%', _low(battery_b, 15, 30), 'Full: surplus goes to the Exchange.' if battery_b >= 100 else f'{engine.FARM_BATTERY_WH / 1000:.0f} kWh battery.'),
        'home_d': _state(
            f'{neighbour_load:.0f} W',
            'alert' if not grid_on and neighbour_load - received['home_d'] >= MIN_FLOW else 'ok',
            f"Received {received['home_d']:.0f} Wh from the Exchange." if received['home_d'] >= MIN_FLOW else 'Synthetic neighbour, no solar.',
        ),
        'business_c': _state(
            f'{"+" if workshop_net >= 0 else ""}{workshop_net:.0f} W',
            'alert' if not grid_on and workshop_net < 0 and received['business_c'] < -workshop_net else 'ok',
            f'Synthetic workshop. Load {workshop_load} W.',
        ),
        'solar_c': _state(f'{workshop_solar:.0f} W', 'ok' if workshop_solar > 0 else 'idle', f'{WORKSHOP_SOLAR_W} W workshop roof.'),
    }


def _state(value, level, detail):
    return {'value': value, 'level': level, 'detail': detail}


def _low(value, alert, watch):
    if value < alert:
        return 'alert'
    if value < watch:
        return 'watch'
    return 'ok'


def _is_exchange(source, destination):
    if (source, destination) == ('tank_a', 'tank_b'):
        return True
    givers = ('home_a',) + EXCHANGE_PRIORITY
    return source in givers and destination in EXCHANGE_PRIORITY and source != destination


def _hour_value(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise NetworkError('hour must be a whole number.') from None
    if value < 0:
        raise NetworkError('hour must be 0 or more.')
    return value
