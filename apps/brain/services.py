"""Read the simulation and control state and describe it in short lines.

Nothing here decides or changes anything. Each line is a value read from the
simulation clock, a weather timeline, or a recorded action, or it is a rule
already applied by those engines.
"""

from datetime import timedelta

from django.db.models import Q

from apps.actuators.models import ActuatorAction
from apps.ai_engine.models import AutomaticAction
from apps.simulation import engine
from apps.simulation.models import SimulationStep
from apps.simulation.services import current_state

TANK_LOW = 25
TANK_MEDIUM = 60
TANK_CONTAINED = 15
BATTERY_RESERVE = 15
SOIL_DRY = 40
SOIL_CONTAINED = 25
SOLAR_HIGH = 0.6
SOLAR_MEDIUM = 0.2
FARM_PUMP_LOAD = 800
TREND_MARGIN = 0.05
SOIL_MARGIN = 0.2
BATCH_WINDOW = timedelta(seconds=2)

STATUS_WORDS = {
    'none': 'NORMAL',
    'watch': 'WATCH',
    'alert': 'ALERT',
    'crisis': 'CRISIS',
}


def build_brain(home=None, farm=None):
    state = current_state()
    previous = _previous(state['hour'])
    weather = _weather(home)
    return {
        'simulated': True,
        'label': (
            'Read from the synthetic simulation clock and the recorded control actions. '
            'Not a live meter reading.'
        ),
        'hour': state['hour'],
        'simulated_at': state['simulated_at'],
        'scenario': state['scenario'],
        'current': _current(state, weather),
        'understanding': _understanding(state, previous),
        'available': _available(state, home),
        'action': _action(state, home, farm, weather),
        'status': _status(state),
    }


def _previous(hour):
    if hour <= 0:
        return None
    step = SimulationStep.objects.filter(hour=hour - 1).first()
    return step.payload if step else None


def _weather(home):
    if home is None:
        return None
    timeline = home.weather_timelines.order_by('-created_at').first()
    if timeline is None:
        return None
    return {
        'timeline': timeline,
        'hour': timeline.hours.filter(hour=timeline.hour).first(),
    }


def _current(state, weather):
    home = state['sensors']['home']
    tank = state['tanks']['home_percent']
    solar = state['solar']['home_watts']
    share = solar / engine.HOME_SOLAR_WATTS if engine.HOME_SOLAR_WATTS else 0
    grid = state['sensors']['grid']['grid_availability']['value'] == 1
    lines = [
        _line('Temperature', f"{home['temperature']['value']}°C", 'simulation clock'),
        _line('Water availability', _level(tank, TANK_LOW, TANK_MEDIUM), 'simulation clock', f'Home tank {tank}%'),
        _line(
            'Solar production',
            _level(share, SOLAR_MEDIUM, SOLAR_HIGH),
            'simulation clock',
            f'{solar} W of {engine.HOME_SOLAR_WATTS} W',
        ),
        _line('Grid', 'AVAILABLE' if grid else 'OUT', 'simulation clock'),
        _line('Soil moisture', f"{state['soil_moisture']}%", 'simulation clock'),
    ]
    hour = weather['hour'] if weather else None
    if hour is not None:
        lines.append(_line('Rain probability', f'{hour.rainfall_probability}%', 'weather scenario'))
    else:
        rainfall = state['sensors']['farm']['rainfall']['value']
        lines.append(_line('Rainfall', f'{rainfall} mm', 'simulation clock', 'No weather timeline for this home'))
    return lines


def _understanding(state, previous):
    if previous is None:
        return [
            _trend('Water demand', None),
            _trend('Energy demand', None),
            _trend('Crop stress', None),
        ]
    water = _direction(
        state['consumption']['home_water_liters_per_hour'],
        previous['consumption']['home_water_liters_per_hour'],
    )
    energy = _direction(
        state['consumption']['home_electricity_watts'],
        previous['consumption']['home_electricity_watts'],
    )
    soil = _points(state['soil_moisture'], previous['soil_moisture'])
    stress = {'up': 'down', 'down': 'up', 'steady': 'steady'}[soil]
    return [
        _trend('Water demand', water, 'Served water against the previous hour'),
        _trend('Energy demand', energy, 'Served electricity against the previous hour'),
        _trend('Crop stress', stress, 'Soil moisture against the previous hour'),
    ]


def _available(state, home):
    solar = state['solar']['home_watts']
    load = state['consumption']['home_electricity_watts']
    battery = state['batteries']['home_percent']
    tank = state['tanks']['home_percent']
    grid = state['sensors']['grid']['grid_availability']['value'] == 1
    items = [
        _resource('Solar surplus', solar > load, f'{solar} W against {load} W'),
        _resource('Battery', battery >= BATTERY_RESERVE, f'{battery}%, reserve {BATTERY_RESERVE}%'),
        _resource('Stored water', tank >= TANK_LOW, f'Home tank {tank}%'),
        _resource('Grid', grid, 'available' if grid else 'out'),
    ]
    collection = home.collection_systems.first() if home is not None else None
    if collection is None:
        items.append(_resource('Rainwater', False, 'No collection system for this home'))
    else:
        stored = float(collection.tank_liters)
        items.append(_resource(
            'Rainwater',
            stored > 0 and collection.authorized,
            f'{collection.tank_liters} L stored, '
            + ('authorized' if collection.authorized else 'not authorized'),
        ))
    return items


def _action(state, home, farm, weather):
    return {
        'flows': _flows(state),
        'recorded': _recorded(home, farm, weather),
    }


def _flows(state):
    grid = state['sensors']['grid']['grid_availability']['value'] == 1
    home_solar = state['solar']['home_watts']
    farm_solar = state['solar']['farm_watts']
    load = state['consumption']['home_electricity_watts']
    farm_battery = state['batteries']['farm_percent']
    flows = []
    if home_solar > 0:
        flows.append(_flow(['Solar', 'Home'], f'{min(home_solar, load):.0f} W from solar'))
    if home_solar > load:
        flows.append(_flow(['Solar', 'Battery'], f'{home_solar - load:.0f} W surplus into the home battery'))
    if not grid and load > home_solar:
        flows.append(_flow(['Battery', 'Home'], 'Grid is out. The home battery covers the rest of the load.'))
    if grid and load > home_solar:
        flows.append(_flow(['Grid', 'Home'], f'{load - home_solar:.0f} W from the grid'))

    if state['pump']['farm'] == 'on':
        if grid:
            flows.append(_flow(['Grid', 'Pump', 'Irrigation'], 'Soil is below 40%, so the engine runs the farm pump.'))
        elif farm_solar >= FARM_PUMP_LOAD:
            flows.append(_flow(['Solar', 'Pump', 'Irrigation'], 'Grid is out. Farm solar covers the pump.'))
            if farm_solar > FARM_PUMP_LOAD:
                flows.append(_flow(['Solar', 'Battery'], 'Farm solar beyond the pump load charges the farm battery.'))
        elif farm_solar > 0:
            flows.append(_flow(
                ['Solar', 'Battery', 'Pump', 'Irrigation'],
                f'Grid is out. Farm solar ({farm_solar} W) and the farm battery ({farm_battery}%) run the pump.',
            ))
        else:
            flows.append(_flow(['Battery', 'Pump', 'Irrigation'], f'Grid is out. The farm battery ({farm_battery}%) runs the pump.'))
    else:
        flows.append(_flow(['Pump off'], _pump_reason(state, grid, farm_solar, farm_battery)))

    if state['valves']['home'] == 'closed':
        flows.append(_flow(['Home valve closed'], 'The engine limits home water use to a quarter of demand.'))
    return flows


def _pump_reason(state, grid, farm_solar, farm_battery):
    if state['scenario'] == 'HEAVY_RAIN':
        return 'Rain scenario. The engine does not irrigate.'
    if state['soil_moisture'] >= SOIL_DRY:
        return f"Soil moisture is {state['soil_moisture']}%, at or above 40%. No irrigation needed."
    if not grid and farm_battery <= 20 and farm_solar <= 150:
        return 'Grid is out and the farm has too little solar or battery to run the pump.'
    return 'The engine left the pump off this hour.'


def _recorded(home, farm, weather):
    rows = []
    rows.extend(_actuator_batch(home, farm))
    rows.extend(_weather_batch(weather))
    if home is not None:
        latest = AutomaticAction.objects.filter(home=home).first()
        if latest is not None:
            rows.append({
                'source': 'Anomaly check',
                'action': latest.action,
                'actuator': 'water valve',
                'previous_state': latest.previous_state,
                'new_state': latest.new_state,
                'mode': latest.source,
                'reason': latest.summary,
                'created_at': latest.created_at.isoformat(),
            })
    return rows


def _actuator_batch(home, farm):
    actions = ActuatorAction.objects.select_related('actuator')
    if home is not None and farm is not None:
        actions = actions.filter(Q(home=home) | Q(farm=farm))
    elif home is not None:
        actions = actions.filter(home=home)
    elif farm is not None:
        actions = actions.filter(farm=farm)
    else:
        return []
    latest = actions.first()
    if latest is None:
        return []
    batch = actions.filter(created_at__gte=latest.created_at - BATCH_WINDOW).order_by('created_at')
    return [
        {
            'source': 'Autopilot',
            'action': item.action,
            'actuator': item.actuator.get_kind_display().lower(),
            'previous_state': item.previous_state,
            'new_state': item.new_state,
            'mode': item.mode,
            'reason': item.reason,
            'created_at': item.created_at.isoformat(),
        }
        for item in batch
    ]


def _weather_batch(weather):
    if weather is None:
        return []
    timeline = weather['timeline']
    latest = timeline.actions.order_by('-created_at').first()
    if latest is None:
        return []
    batch = timeline.actions.filter(hour=latest.hour).order_by('created_at')
    return [
        {
            'source': 'Weather',
            'action': item.action,
            'actuator': item.actuator,
            'previous_state': item.previous_state,
            'new_state': item.new_state,
            'mode': item.mode,
            'reason': item.reason,
            'created_at': item.created_at.isoformat(),
        }
        for item in batch
    ]


def _status(state):
    level = state['crisis_state']
    word = STATUS_WORDS.get(level, level.upper())
    if level not in ('alert', 'crisis'):
        return {
            'level': level,
            'text': word,
            'detail': f"Scenario {state['scenario']}.",
        }
    grid = state['sensors']['grid']['grid_availability']['value'] == 1
    tank_ok = state['tanks']['home_percent'] >= TANK_CONTAINED
    power_ok = grid or state['batteries']['home_percent'] >= BATTERY_RESERVE
    crops_ok = state['soil_moisture'] >= SOIL_CONTAINED or state['pump']['farm'] == 'on'
    contained = tank_ok and power_ok and crops_ok
    checks = [
        f"home tank {'≥' if tank_ok else '<'} {TANK_CONTAINED}%",
        'power reserve available' if power_ok else 'no power reserve',
        'crops watered or soil ≥ 25%' if crops_ok else 'soil < 25% and the pump is off',
    ]
    return {
        'level': level,
        'text': f"{word} {'CONTAINED' if contained else 'ACTIVE'}",
        'detail': f"Scenario {state['scenario']}. " + ', '.join(checks) + '.',
    }


def _level(value, low, high):
    if value < low:
        return 'LOW'
    if value < high:
        return 'MEDIUM'
    return 'HIGH'


def _direction(now, before):
    base = max(abs(before), 1)
    change = (now - before) / base
    if change > TREND_MARGIN:
        return 'up'
    if change < -TREND_MARGIN:
        return 'down'
    return 'steady'


def _points(now, before):
    change = now - before
    if change > SOIL_MARGIN:
        return 'up'
    if change < -SOIL_MARGIN:
        return 'down'
    return 'steady'


def _line(label, value, source, note=''):
    return {'label': label, 'value': value, 'source': source, 'note': note}


def _trend(label, direction, note=''):
    if direction is None:
        return {'label': label, 'direction': 'baseline', 'symbol': '·', 'note': 'Hour 0 has no previous hour.'}
    symbol = {'up': '↑', 'down': '↓', 'steady': '→'}[direction]
    return {'label': label, 'direction': direction, 'symbol': symbol, 'note': note}


def _resource(label, ok, note):
    return {'label': label, 'available': bool(ok), 'symbol': '✓' if ok else '✗', 'note': note}


def _flow(steps, note):
    return {'steps': steps, 'text': ' → '.join(steps), 'note': note}
