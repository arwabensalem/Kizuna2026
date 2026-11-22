"""KIZUNA Crisis Day: one fixed day, played from 10:00 to 20:00.

Every beat is a step of the crisis-lab rules on a fixed hourly series.
KIZUNA's rules switch on at 14:25. Rain is not visible to those rules until
15:00, which is when this series predicts it. No weather service is called.
The crop-stress formula is the lab formula, not a trained model file.
"""

import copy
import math

from apps.actuators.engine import STRESS_HIGH
from apps.brain.services import SOIL_DRY, SOLAR_HIGH, SOLAR_MEDIUM, TANK_LOW, TANK_MEDIUM
from apps.crisis.lab import (
    CAPTURE,
    CRISIS_ENERGY,
    CRISIS_WATER,
    FARM_ROOF_M2,
    FARM_SOLAR_W,
    FARM_TANK_L,
    HOME_ROOF_M2,
    HOME_SOLAR_W,
    HOME_TANK_L,
    _initial,
    _run,
    crop_stress,
)

LABEL = (
    'Deterministic demo. The same series runs every time, from the crisis-lab rules. '
    'It does not call a weather service, and it does not change the shared simulation clock.'
)

# clock, title, kind
BEATS = (
    (10, 0, 'NORMAL'),
    (12, 0, 'HEATWAVE BEGINS'),
    (13, 0, 'ENERGY DEMAND RISES'),
    (14, 0, 'GRID INSTABILITY'),
    (14, 15, 'PUMPS STOP'),
    (14, 20, 'CROP STRESS BEGINS'),
    (14, 25, 'KIZUNA ACTIVATES'),
    (14, 26, 'SOLAR → BATTERY → PUMP → IRRIGATION'),
    (15, 0, 'RAIN PREDICTED'),
    (15, 1, 'RAIN PREPARATION MODE'),
    (18, 0, 'RAIN'),
    (18, 1, 'RAINWATER COLLECTION'),
    (20, 0, 'CRISIS CONTAINED'),
)


def build_crisis_day():
    drivers = _drivers()
    start = _initial({'water': 70, 'soil': 22})
    off_stocks = dict(start)
    on_stocks = dict(start)
    off_hours = []
    on_hours = []
    actions = []
    for index, driver in enumerate(drivers):
        reveal = driver['clock'] >= 15
        off_hour, off_events = _step(off_stocks, drivers, index, False, reveal)
        off_hours.append(off_hour)
        if driver['clock'] < 14:
            on_stocks = copy.deepcopy(off_stocks)
            on_hours.append(off_hour)
        else:
            on_hour, on_events = _step(on_stocks, drivers, index, True, reveal)
            on_hours.append(on_hour)
            for event in on_events:
                if event['action'] not in {item['action'] for item in actions}:
                    actions.append({
                        'time': _stamp(driver['clock'], 0),
                        'action': event['action'],
                        'text': event['reason'],
                    })
    frames = []
    for clock, minute, title in BEATS:
        index = clock - 10
        controls = (clock, minute) >= (14, 26)
        hour = (on_hours if controls else off_hours)[index]
        driver = drivers[index]
        frames.append(_frame(clock, minute, title, hour, driver, controls, actions, on_hours[index]))
    summary = _summary(off_hours, on_hours, drivers)
    frames[-1]['summary'] = summary
    frames[-1]['headline'] = summary['headline']
    return {
        'simulated': True,
        'label': LABEL,
        'beats': frames,
        'summary': summary,
    }


def _drivers():
    rows = []
    for clock in range(10, 21):
        if clock <= 11:
            temperature, rain, farm_grid, home_grid, stress = 30, 0.0, True, True, 22
        elif clock <= 13:
            temperature, rain, farm_grid, home_grid, stress = 45, 0.0, True, True, 70
        elif clock == 14:
            temperature, rain, farm_grid, home_grid, stress = 45, 0.0, False, True, 92
        elif clock <= 17:
            temperature, rain, farm_grid, home_grid, stress = 44, 0.0, False, True, 88
        elif clock == 18:
            temperature, rain, farm_grid, home_grid, stress = 24, 12.0, True, True, 30
        else:
            temperature, rain, farm_grid, home_grid, stress = 26, 0.0, True, True, 24
        rows.append(_driver(clock, temperature, rain, farm_grid, home_grid, stress))
    return rows


def _driver(clock, temperature, rain_mm, farm_grid, home_grid, grid_stress):
    daylight = 0.0 if clock <= 6 or clock >= 19 else math.sin((clock - 6) / 13 * math.pi)
    humidity = round(min(100, max(8, 62 - (temperature - 24) * 1.3 + (25 if rain_mm else 0))), 1)
    cloud = 0.45 if rain_mm else 1.0
    evening = math.exp(-((clock - 21) ** 2) / 10)
    demand = 380 + 700 * evening + max(0.0, temperature - 28) * 90
    reference = 380 + 700 * evening
    morning = math.exp(-((clock - 7) ** 2) / 6)
    evening_water = math.exp(-((clock - 20) ** 2) / 8)
    water = (8 + 16 * morning + 12 * evening_water) * (1 + max(0.0, temperature - 30) * 0.03)
    grid_on = True
    return {
        'hour': clock,
        'clock': clock,
        'temperature': temperature,
        'humidity': humidity,
        'daylight': round(daylight, 3),
        'rain_mm': rain_mm,
        'home_solar': round(HOME_SOLAR_W * daylight * cloud, 1),
        'farm_solar': round(FARM_SOLAR_W * daylight * cloud, 1),
        'grid_on': grid_on,
        'grid_stress': grid_stress,
        'home_grid': home_grid,
        'farm_grid': farm_grid,
        'demand_w': round(demand, 1),
        'reference_w': round(reference, 1),
        'water_l': round(water, 2),
        'refill_home': 28.0 if grid_on else 0.0,
        'refill_farm': 14.0,
        'et': round(0.25 + max(0.0, temperature - 25) * 0.04 + daylight * 0.3, 3),
    }


def _step(stocks, drivers, index, kizuna, reveal_rain):
    window = drivers[index:]
    if not reveal_rain:
        window = [item for item in window if item['clock'] < 18]
        if not window:
            window = drivers[index:index + 1]
    out = _run(window, stocks, kizuna, _formula, limit=1)
    return out['hours'][0], out['events']


def _formula(rows):
    return [
        crop_stress(row['soil_moisture'], row['temperature'], row['humidity'], row['rainfall'])
        for row in rows
    ]


def _frame(clock, minute, title, hour, driver, controls, actions, on_hour):
    extra = round(driver['demand_w'] - driver['reference_w'], 1)
    aware = (clock, minute) >= (14, 25)
    flows = _flows(hour, driver, on_hour if controls else hour, minute)
    shown_actions = [item for item in actions if _reached(item['time'], clock, minute)]
    brain = _brain(hour, driver, aware, extra)
    propagation = _propagation(clock, minute, hour, driver, extra)
    solar_share = driver['home_solar'] / HOME_SOLAR_W if HOME_SOLAR_W else 0
    return {
        'time': _stamp(clock, minute),
        'title': title,
        'sample': _stamp(clock, 0),
        'note': _sample_note(clock, minute),
        'kizuna': aware,
        'twin': {
            'temperature': driver['temperature'],
            'home_tank_percent': hour['home_tank_percent'],
            'farm_tank_percent': hour['farm_tank_percent'],
            'home_battery_percent': hour['home_battery_percent'],
            'farm_battery_percent': hour['farm_battery_percent'],
            'solar_w': driver['home_solar'],
            'farm_solar_w': driver['farm_solar'],
            'pump': hour['pump'],
            'soil': hour['soil'],
            'rain_mm': driver['rain_mm'],
        },
        'flows': flows,
        'propagation': propagation,
        'brain': brain,
        'actions': shown_actions,
        'chart': {
            'crop_stress': hour['crop_stress'],
            'water_stress': hour['water_stress'],
            'energy_stress': hour['energy_stress'],
            'demand_extra_w': extra,
        },
        'tunisia': _tunisia(hour, driver, solar_share),
        'headline': title,
    }


def _flows(hour, driver, active, minute):
    flows = []
    pump = active['pump']
    if pump in {'solar', 'solar+battery', 'battery'}:
        flows.append(_flow('solar', 'pump', 'energy', driver['farm_solar'], 'W', 'Farm solar this hour.'))
        if pump == 'solar':
            surplus = driver['farm_solar'] - 800
            flows.append(_flow('solar', 'battery', 'energy', surplus, 'W', 'Solar left after the pump charges the battery.'))
        if pump == 'solar+battery':
            flows.append(_flow('battery', 'pump', 'energy', max(0, 800 - driver['farm_solar']), 'W', 'Battery covers the rest of the pump.'))
        flows.append(_flow('pump', 'irrigation', 'water', 300, 'L', 'One pump hour from the lab rule.'))
    elif pump == 'grid':
        flows.append(_flow('grid', 'pump', 'energy', 800, 'W', 'The timer runs the pump on the grid.'))
        flows.append(_flow('pump', 'irrigation', 'water', 300, 'L', 'One pump hour from the lab rule.'))
    if driver['home_solar'] > 0:
        flows.append(_flow('solar', 'home', 'energy', driver['home_solar'], 'W', 'Home array this hour.'))
    show_rain = active['recovered_l'] > 0 and not (driver['clock'] == 18 and minute < 1)
    if show_rain:
        flows.append(_flow('rain', 'tank', 'water', active['recovered_l'], 'L', 'Roof capture for this hour of rain.'))
    return [item for item in flows if item['quantity'] > 0]


def _flow(source, destination, resource, quantity, unit, note):
    return {
        'source': source,
        'destination': destination,
        'resource': resource,
        'quantity': round(float(quantity), 1),
        'unit': unit,
        'note': note,
    }


def _brain(hour, driver, kizuna, extra):
    tank = hour['home_tank_percent']
    solar = driver['home_solar'] / HOME_SOLAR_W if HOME_SOLAR_W else 0
    grid = 'LIMITED' if not driver['farm_grid'] else 'AVAILABLE'
    lines = [
        {'label': 'Temperature', 'value': f"{driver['temperature']}°C"},
        {'label': 'Water', 'value': _level(tank, TANK_LOW, TANK_MEDIUM), 'note': f"Home tank {tank}%"},
        {'label': 'Solar', 'value': _level(solar, SOLAR_MEDIUM, SOLAR_HIGH), 'note': f"{driver['home_solar']} W"},
        {'label': 'Grid', 'value': grid, 'note': f"Stress {driver['grid_stress']}"},
        {'label': 'Soil', 'value': f"{hour['soil']}%", 'note': 'Dry' if hour['soil'] < SOIL_DRY else 'Holding'},
        {'label': 'Crop stress', 'value': f"{hour['crop_stress']}/100"},
        {'label': 'Cooling load', 'value': f"+{extra:.0f} W" if extra else 'Baseline'},
        {'label': 'KIZUNA', 'value': 'ON' if kizuna else 'OFF'},
        {'label': 'Pump', 'value': hour['pump']},
    ]
    if driver['clock'] >= 15 and driver['clock'] < 18:
        lines.append({'label': 'Rain', 'value': 'In this series at 18:00'})
    elif driver['rain_mm']:
        lines.append({'label': 'Rain', 'value': f"{driver['rain_mm']} mm this hour"})
    return lines


def _propagation(clock, minute, hour, driver, extra):
    stamp = (clock, minute)
    steps = [
        ('Heat', stamp >= (12, 0), f"{driver['temperature']}°C" if stamp >= (12, 0) else '—'),
        ('Demand', stamp >= (13, 0) and extra >= 200, f"+{extra / 1000:.1f} kW" if extra >= 200 else '—'),
        ('Grid', stamp >= (14, 0), f"{driver['grid_stress']} stress"),
        ('Pumps', stamp >= (14, 15), 'Stopped' if hour['pump'] == 'off' else hour['pump']),
        ('Crops', hour['crop_stress'] >= STRESS_HIGH, f"{hour['crop_stress']}/100"),
        ('KIZUNA', stamp >= (14, 25), 'ON' if stamp >= (14, 25) else 'OFF'),
        ('Rain', stamp >= (15, 0), _rain_label(stamp, driver)),
    ]
    return [{'label': label, 'on': on, 'value': value} for label, on, value in steps]


def _tunisia(hour, driver, solar_share):
    water = round((hour['home_tank_percent'] + hour['farm_tank_percent']) / 2, 1)
    battery = (hour['home_battery_percent'] + hour['farm_battery_percent']) / 2
    energy = round(battery if not driver['home_grid'] else battery * 0.5 + 50, 1)
    agriculture = round(max(0.0, min(100.0, hour['soil'])), 1)
    climate = round(max(0.0, min(100.0, 100 - abs(driver['temperature'] - 24) * 4)), 1)
    overall = round((water + energy + agriculture + climate) / 4, 1)
    return {
        'place': 'Tunis',
        'water': water,
        'energy': energy,
        'agriculture': agriculture,
        'climate': climate,
        'overall': overall,
        'note': 'Tunis score from this hour’s tanks, batteries, soil, and temperature. Not the national dataset.',
    }


def _summary(off_hours, on_hours, drivers):
    final = on_hours[-1]
    contained = (
        final['water_stress'] < CRISIS_WATER
        and final['energy_stress'] < CRISIS_ENERGY
        and final['crop_stress'] < STRESS_HIGH
    )
    rain_off = sum(item['recovered_l'] for item in off_hours)
    rain_on = sum(item['recovered_l'] for item in on_hours)
    energy_recovered = round(_solar_kept(on_hours, drivers) - _solar_kept(off_hours, drivers), 1)
    protected = sum(1 for item in on_hours if item['crop_stress'] < STRESS_HIGH)
    home_ok = final['water_stress'] < CRISIS_WATER and final['energy_stress'] < CRISIS_ENERGY
    water_recovered = round(rain_on, 1)
    water_saved = round(max(0.0, rain_on - rain_off), 1)
    return {
        'headline': 'CRISIS CONTAINED' if contained else 'CRISIS NOT CONTAINED',
        'contained': contained,
        'water_saved_l': water_saved,
        'energy_recovered_wh': energy_recovered,
        'crops_protected': protected,
        'crops_hours': len(on_hours),
        'homes_stabilized': 1 if home_ok else 0,
        'water_recovered_l': water_recovered,
        'rules': {
            'water_saved_l': 'Rainwater the controlled run collected, minus the uncontrolled run. The uncontrolled run does not open the roof.',
            'energy_recovered_wh': 'Farm solar the controlled run used for the pump or stored, minus the same figure for the uncontrolled run. Counted from 14:00, when KIZUNA is controlling.',
            'crops_protected': f'Hours in this series with crop stress under {STRESS_HIGH}.',
            'homes_stabilized': '1 when the simulated home ends under the lab water and energy crisis lines, otherwise 0.',
            'water_recovered_l': f'Roof area × rain × {CAPTURE:.0%} capture, added by the controlled run.',
        },
        'capture_note': (
            f'Home roof {HOME_ROOF_M2} m² and farm roof {FARM_ROOF_M2} m². '
            f'Tanks {HOME_TANK_L:.0f} L and {FARM_TANK_L:.0f} L.'
        ),
        'final': {
            'crop_stress': final['crop_stress'],
            'water_stress': final['water_stress'],
            'energy_stress': final['energy_stress'],
            'soil': final['soil'],
        },
    }


def _solar_kept(hours, drivers):
    total = 0.0
    for hour, driver in zip(hours, drivers):
        if driver['clock'] < 14:
            continue
        if hour['pump'] in {'solar', 'solar+battery', 'battery'}:
            total += driver['farm_solar']
    return total


def _rain_label(stamp, driver):
    if driver['rain_mm']:
        return f"{driver['rain_mm']} mm"
    if stamp >= (18, 1):
        return 'Collected'
    if stamp >= (15, 0):
        return 'Predicted'
    return '—'


def _sample_note(clock, minute):
    """Minutes inside one lab hour reuse that hour's sample."""
    if (clock, minute) == (14, 26):
        return 'Controlled sample of the 14:00 hour. The pump source changes here.'
    if (clock, minute) == (18, 1):
        return 'Same stocks as 18:00. Roof capture is counted on this beat.'
    if minute:
        return (
            f"Lab hour {clock:02d}:00. This title marks the chain. "
            'Tank, soil, and stress stay this hour’s sample.'
        )
    return ''


def _stamp(clock, minute):
    return f'{clock:02d}:{minute:02d}'


def _reached(stamp, clock, minute):
    hour_text, minute_text = stamp.split(':')
    return (clock, minute) >= (int(hour_text), int(minute_text))


def _level(value, low, high):
    if value < low:
        return 'LOW'
    if value < high:
        return 'MEDIUM'
    return 'HIGH'
