"""KIZUNA Crisis Lab: one synthetic what-if, run twice.

Both runs share the same hourly drivers and the same starting stocks.
WITHOUT KIZUNA nothing reacts: irrigation keeps a fixed 10:00-13:00 timer on
the grid, solar surplus is not stored, loads are not shed, and rain is not
collected. WITH KIZUNA the control rules from the autopilot act every hour,
the crop-stress model forecasts the next three hours, and the simulated
series supplies the rain forecast.

Every figure is synthetic. It is not a forecast for a real place.
"""

import math

from apps.actuators.engine import BATTERY_RESERVE, STRESS_HIGH
from apps.farms.simulation import IDEAL_MOISTURE

SCENARIOS = {
    'NORMAL': {
        'temperature': 30, 'rainfall': 0, 'grid': 100, 'solar': 100,
        'water': 70, 'soil': 45, 'duration': 24,
    },
    'HEATWAVE': {
        'temperature': 45, 'rainfall': 0, 'grid': 85, 'solar': 105,
        'water': 55, 'soil': 34, 'duration': 36,
    },
    'DROUGHT': {
        'temperature': 38, 'rainfall': 0, 'grid': 100, 'solar': 100,
        'water': 20, 'soil': 22, 'duration': 48,
    },
    'POWER_OUTAGE': {
        'temperature': 31, 'rainfall': 0, 'grid': 30, 'solar': 100,
        'water': 65, 'soil': 40, 'duration': 36,
    },
    'HEAVY_RAIN': {
        'temperature': 24, 'rainfall': 45, 'grid': 90, 'solar': 35,
        'water': 60, 'soil': 50, 'duration': 24,
    },
    'COMBINED_CRISIS': {
        'temperature': 45, 'rainfall': 0, 'grid': 35, 'solar': 90,
        'water': 25, 'soil': 26, 'duration': 36,
    },
}

LIMITS = {
    'temperature': (10, 50),
    'rainfall': (0, 150),
    'grid': (0, 100),
    'solar': (0, 120),
    'water': (0, 100),
    'soil': (0, 100),
    'duration': (6, 72),
}

HOME_TANK_L = 1500
FARM_TANK_L = 8000
HOME_BATTERY_WH = 8000
FARM_BATTERY_WH = 10000
HOME_SOLAR_W = 3000
FARM_SOLAR_W = 4000
CRITICAL_W = 450
PUMP_W = 800
PUMP_LPH = 300
SOIL_PER_LITER = 0.008
HOME_ROOF_M2 = 80
FARM_ROOF_M2 = 120
CAPTURE = 0.8
GRID_CUT_FARM = 85
GRID_CUT_HOME = 95
HOT = 35
RAIN_HORIZON = 4
FORECAST_HOURS = 3
FORECAST_TRIGGER = 30
EMERGENCY = 55
DRY_MARGIN = 6
COOL_WINDOW = 6
CONSERVE_TANK = 30
ESSENTIAL_SHARE = 0.7
CRISIS_WATER = 50
CRISIS_ENERGY = 50

NODES = (
    ('grid', 'Grid'),
    ('home_power', 'Home power'),
    ('battery', 'Battery'),
    ('home_water', 'Home water'),
    ('pump', 'Pump'),
    ('irrigation', 'Irrigation'),
    ('crops', 'Crops'),
)


class LabError(ValueError):
    pass


def clean_inputs(raw):
    if not isinstance(raw, dict):
        raise LabError('Send a JSON object.')
    scenario = str(raw.get('scenario', 'NORMAL'))
    if scenario not in SCENARIOS:
        raise LabError(f'scenario must be one of: {", ".join(SCENARIOS)}.')
    values = {'scenario': scenario}
    for name, (low, high) in LIMITS.items():
        value = raw.get(name, SCENARIOS[scenario][name])
        if isinstance(value, bool):
            raise LabError(f'{name} must be a number.')
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise LabError(f'{name} must be a number.')
        if number != number or number < low or number > high:
            raise LabError(f'{name} must be between {low} and {high}.')
        values[name] = number
    if int(values['duration']) != values['duration']:
        raise LabError('duration must be a whole number of hours.')
    values['duration'] = int(values['duration'])
    return values


def run_lab(inputs, forecaster=None):
    forecast = forecaster or CropForecaster()
    drivers = build_drivers(inputs)
    start = _initial(inputs)
    without = _run(drivers, dict(start), kizuna=False, forecast=None)
    with_kizuna = _run(drivers, dict(start), kizuna=True, forecast=forecast)
    base = _metrics(without, inputs)
    smart = _metrics(with_kizuna, inputs)
    timer_loss = _timer_loss_rate(drivers)
    return {
        'simulated': True,
        'label': 'Synthetic what-if. Both runs start from the same conditions. Not a forecast for a real place.',
        'inputs': inputs,
        'initial': start,
        'ai': forecast.describe(),
        'drivers': [
            {key: driver[key] for key in ('hour', 'clock', 'temperature', 'rain_mm', 'grid_on', 'grid_stress')}
            for driver in drivers
        ],
        'without': {'metrics': base, 'hours': without['hours'], 'events': without['events']},
        'with': {'metrics': smart, 'hours': with_kizuna['hours'], 'events': with_kizuna['events']},
        'comparison': _comparison(base, smart, timer_loss),
        'propagation': _propagation(inputs, drivers, without, base),
        'response': _response(with_kizuna, base, smart),
        'nodes': [{'key': key, 'label': label} for key, label in NODES],
    }


class CropForecaster:
    """Forecast crop stress with the trained model, or say plainly that it is missing."""

    def __init__(self):
        self.used = None
        self.note = ''

    def __call__(self, rows):
        if self.used is not False:
            try:
                from apps.ai_engine.services import PredictionError, predict_crop_stress_rows
                try:
                    values = predict_crop_stress_rows(rows)
                    self.used = True
                    return values
                except PredictionError as exc:
                    self.used = False
                    self.note = str(exc)
            except ImportError:
                self.used = False
        return [crop_stress(row['soil_moisture'], row['temperature'], row['humidity'], row['rainfall']) for row in rows]

    def describe(self):
        if self.used:
            return {
                'used': True,
                'model': 'crop_stress',
                'note': 'The trained crop-stress model forecast the next 3 hours before each irrigation decision.',
            }
        if self.used is None:
            return {
                'used': False,
                'model': None,
                'note': 'No irrigation decision needed a crop-stress forecast in this run (soil stayed wet or rain was expected).',
            }
        return {
            'used': False,
            'model': None,
            'note': (
                'The crop-stress model is not on disk, so the synthetic stress formula was used for the forecast. '
                + (self.note or 'Run: python manage.py train_models')
            ),
        }


def crop_stress(soil, temperature, humidity, rain_mm):
    stress = (
        abs(soil - IDEAL_MOISTURE) * 1.5
        + max(temperature - 32, 0) * 2
        + max(40 - humidity, 0) * 0.3
        - rain_mm * 1.2
    )
    return round(min(100.0, max(0.0, stress)), 1)


def build_drivers(inputs):
    duration = inputs['duration']
    peak = inputs['temperature']
    solar_share = inputs['solar'] / 100
    water_share = inputs['water'] / 100
    outage_hours = round(duration * (1 - inputs['grid'] / 100))
    outage_start = round(duration * 0.25) if outage_hours < duration else 0
    rain_day = inputs['rainfall']
    drivers = []
    for hour in range(duration):
        clock = hour % 24
        wave = (math.cos((clock - 15) / 24 * 2 * math.pi) + 1) / 2
        temperature = round(peak - 8 * (1 - wave), 1)
        humidity = round(min(100, max(8, 62 - (temperature - 24) * 1.3 + (25 if rain_day and 14 <= clock <= 19 else 0))), 1)
        daylight = 0.0 if clock <= 6 or clock >= 19 else math.sin((clock - 6) / 13 * math.pi)
        rain_mm = round(rain_day / 6, 2) if rain_day and 14 <= clock <= 19 else 0.0
        cloud = 0.45 if rain_mm else 1.0
        grid_on = not (outage_start <= hour < outage_start + outage_hours)
        evening = math.exp(-((clock - 21) ** 2) / 10)
        stress = 20 + max(0.0, temperature - 30) * 5 + 15 * evening
        grid_stress = 100.0 if not grid_on else round(min(100.0, stress), 1)
        demand = 380 + 700 * evening + max(0.0, temperature - 28) * 90
        reference = 380 + 700 * evening
        morning = math.exp(-((clock - 7) ** 2) / 6)
        evening_water = math.exp(-((clock - 20) ** 2) / 8)
        water = (8 + 16 * morning + 12 * evening_water) * (1 + max(0.0, temperature - 30) * 0.03)
        drivers.append({
            'hour': hour,
            'clock': clock,
            'temperature': temperature,
            'humidity': humidity,
            'daylight': round(daylight, 3),
            'rain_mm': rain_mm,
            'home_solar': round(HOME_SOLAR_W * daylight * solar_share * cloud, 1),
            'farm_solar': round(FARM_SOLAR_W * daylight * solar_share * cloud, 1),
            'grid_on': grid_on,
            'grid_stress': grid_stress,
            'home_grid': grid_on and grid_stress < GRID_CUT_HOME,
            'farm_grid': grid_on and grid_stress < GRID_CUT_FARM,
            'demand_w': round(demand, 1),
            'reference_w': round(reference, 1),
            'water_l': round(water, 2),
            'refill_home': 40 * water_share if grid_on else 0.0,
            'refill_farm': 20 * water_share,
            'et': round(0.25 + max(0.0, temperature - 25) * 0.04 + daylight * 0.3, 3),
        })
    return drivers


def _initial(inputs):
    share = inputs['water'] / 100
    return {
        'home_tank_l': round(HOME_TANK_L * share, 1),
        'farm_tank_l': round(FARM_TANK_L * share, 1),
        'home_battery_wh': HOME_BATTERY_WH * 0.6,
        'farm_battery_wh': FARM_BATTERY_WH * 0.55,
        'soil': inputs['soil'],
    }


def _run(drivers, stocks, kizuna, forecast, limit=None):
    hours = []
    events = []
    totals = {
        'rain_recovered_l': 0.0,
        'water_lost_l': 0.0,
        'irrigation_l': 0.0,
        'solar_stored_wh': 0.0,
        'solar_curtailed_wh': 0.0,
        'solar_pump_wh': 0.0,
        'battery_pump_wh': 0.0,
        'grid_pump_wh': 0.0,
        'pump_hours': 0,
        'pump_outage_hours': 0,
        'tank_empty_hours': 0,
        'shed_hours': 0,
        'rain_suspend_hours': 0,
        'conserve_hours': 0,
        'deferred_irrigation_hours': 0,
    }
    flags = {'pump': 'off', 'shed': False, 'suspend': False, 'conserve': False, 'collect': False}

    for index, d in enumerate(drivers):
        if limit is not None and index >= limit:
            break
        h = d['hour']
        recovered = 0.0
        if kizuna and d['rain_mm'] > 0:
            home_in = min(HOME_ROOF_M2 * d['rain_mm'] * CAPTURE, HOME_TANK_L - stocks['home_tank_l'])
            farm_in = min(FARM_ROOF_M2 * d['rain_mm'] * CAPTURE, FARM_TANK_L - stocks['farm_tank_l'])
            stocks['home_tank_l'] += max(0.0, home_in)
            stocks['farm_tank_l'] += max(0.0, farm_in)
            recovered = max(0.0, home_in) + max(0.0, farm_in)
            totals['rain_recovered_l'] += recovered
            if not flags['collect']:
                flags['collect'] = True
                events.append(_event(h, 'collect_rainwater', 'Rain is falling. Roof → rainwater system → tanks.'))
        elif flags['collect'] and d['rain_mm'] == 0:
            flags['collect'] = False

        want, reason = _irrigation_wish(drivers, index, stocks, kizuna, forecast)
        if kizuna:
            if reason == 'rain':
                totals['rain_suspend_hours'] += 1
                if not flags['suspend']:
                    flags['suspend'] = True
                    events.append(_event(h, 'suspend_irrigation', 'Rain expected within 4 hours. Irrigation is not needed.'))
            elif flags['suspend']:
                flags['suspend'] = False
            if reason == 'deferred':
                totals['deferred_irrigation_hours'] += 1

        source = None
        solar_for_pump = 0.0
        no_power = False
        if want and stocks['farm_tank_l'] < PUMP_LPH:
            totals['tank_empty_hours'] += 1
        elif want:
            source, solar_for_pump = _pump_power(d, stocks, kizuna)
            if source is None:
                no_power = True
                totals['pump_outage_hours'] += 1

        gain = 0.0
        if source:
            totals['pump_hours'] += 1
            stocks['farm_tank_l'] -= PUMP_LPH
            totals['irrigation_l'] += PUMP_LPH
            efficiency = 0.6 if _sunny_and_hot(d) else 0.9
            totals['water_lost_l'] += PUMP_LPH if d['rain_mm'] > 0 else PUMP_LPH * (1 - efficiency)
            gain = PUMP_LPH * efficiency * SOIL_PER_LITER
            if source == 'grid':
                totals['grid_pump_wh'] += PUMP_W
            else:
                totals['solar_pump_wh'] += solar_for_pump
                battery_part = PUMP_W - solar_for_pump
                if battery_part > 0:
                    stocks['farm_battery_wh'] -= battery_part
                    totals['battery_pump_wh'] += battery_part
        pump_state = source or 'off'
        if kizuna and pump_state != flags['pump']:
            events.append(_event(h, 'pump_' + ('on' if source else 'off'), _pump_reason(source, d, reason)))
        flags['pump'] = pump_state

        farm_surplus = d['farm_solar'] - solar_for_pump
        if farm_surplus > 0:
            if kizuna:
                stored = min(farm_surplus, FARM_BATTERY_WH - stocks['farm_battery_wh'])
                stocks['farm_battery_wh'] += stored
                totals['solar_stored_wh'] += stored
                totals['solar_curtailed_wh'] += farm_surplus - stored
            else:
                totals['solar_curtailed_wh'] += farm_surplus

        stocks['soil'] = max(0.0, min(100.0, stocks['soil'] + gain + d['rain_mm'] * 0.6 - d['et']))
        stocks['farm_tank_l'] = min(FARM_TANK_L, stocks['farm_tank_l'] + d['refill_farm'])

        energy = _home_energy(d, stocks, kizuna, kizuna and _must_shed(drivers, index, stocks), totals)
        if kizuna and energy['shed'] != flags['shed']:
            flags['shed'] = energy['shed']
            if energy['shed']:
                events.append(_event(
                    h,
                    'shed_non_critical',
                    'Home grid supply is cut and the battery cannot carry every load until it returns. '
                    'Non-critical loads off; critical loads stay on.',
                ))
            else:
                events.append(_event(h, 'restore_loads', 'The battery or the grid can carry every load again. Non-critical loads restored.'))

        water = _home_water(d, stocks, kizuna, totals)
        if kizuna and water['conserve'] != flags['conserve']:
            flags['conserve'] = water['conserve']
            if water['conserve']:
                events.append(_event(h, 'conserve_water', f'Home tank below {CONSERVE_TANK}%. Essential water only.'))
            else:
                events.append(_event(h, 'end_conservation', 'Home tank recovered. Normal water use.'))

        stress = crop_stress(stocks['soil'], d['temperature'], d['humidity'], d['rain_mm'])
        hours.append({
            'hour': h,
            'soil': round(stocks['soil'], 2),
            'crop_stress': stress,
            'water_stress': water['stress'],
            'energy_stress': energy['stress'],
            'home_tank_percent': round(stocks['home_tank_l'] / HOME_TANK_L * 100, 1),
            'farm_tank_percent': round(stocks['farm_tank_l'] / FARM_TANK_L * 100, 1),
            'home_battery_percent': round(stocks['home_battery_wh'] / HOME_BATTERY_WH * 100, 1),
            'farm_battery_percent': round(stocks['farm_battery_wh'] / FARM_BATTERY_WH * 100, 1),
            'pump': pump_state,
            'pump_wanted': bool(want),
            'pump_no_power': no_power,
            'critical_unmet_w': energy['critical_unmet'],
            'grid_limited': not d['farm_grid'],
            'recovered_l': round(recovered, 1),
        })
    return {'hours': hours, 'events': events, 'totals': totals}


def _irrigation_wish(drivers, index, stocks, kizuna, forecast):
    d = drivers[index]
    if not kizuna:
        return 10 <= d['clock'] <= 13, 'timer'
    if any(item['rain_mm'] > 0 for item in drivers[index:index + RAIN_HORIZON + 1]):
        needs = stocks['soil'] < IDEAL_MOISTURE
        return False, 'rain' if needs else 'wet'
    if stocks['soil'] >= IDEAL_MOISTURE:
        return False, 'wet'
    ahead = drivers[index + 1:index + 1 + FORECAST_HOURS] or [d]
    soil = stocks['soil']
    rows = []
    for item in ahead:
        soil = max(0.0, soil - item['et'])
        rows.append({
            'soil_moisture': soil,
            'temperature': item['temperature'],
            'humidity': item['humidity'],
            'rainfall': item['rain_mm'],
            'area': 2000.0,
            'crop_type': 'olive',
            'soil_type': 'loam',
        })
    predicted = max(forecast(rows))
    if predicted < FORECAST_TRIGGER and stocks['soil'] >= IDEAL_MOISTURE - DRY_MARGIN:
        return False, 'calm'
    if _sunny_and_hot(d) and predicted < EMERGENCY:
        cooler = drivers[index + 1:index + 1 + COOL_WINDOW]
        if any(not _sunny_and_hot(item) for item in cooler):
            return False, 'deferred'
    return True, 'forecast'


def _sunny_and_hot(d):
    return d['daylight'] > 0 and d['temperature'] >= HOT


def _pump_power(d, stocks, kizuna):
    if d['farm_grid']:
        return 'grid', 0.0
    if not kizuna:
        return None, 0.0
    if d['farm_solar'] >= PUMP_W:
        return 'solar', float(PUMP_W)
    reserve = FARM_BATTERY_WH * BATTERY_RESERVE / 100
    if d['farm_solar'] + stocks['farm_battery_wh'] - reserve >= PUMP_W:
        source = 'solar+battery' if d['farm_solar'] > 0 else 'battery'
        return source, float(d['farm_solar'])
    return None, 0.0


def _pump_reason(source, d, reason):
    if source == 'grid':
        return 'Crop stress forecast is high. Pump runs on the grid.'
    if source == 'solar':
        return 'Grid cannot serve the pump. Farm solar runs it.'
    if source == 'solar+battery':
        return 'Grid cannot serve the pump. Farm solar and the battery run it.'
    if source == 'battery':
        return 'Grid cannot serve the pump. The farm battery runs it.'
    return {
        'rain': 'Rain expected within 4 hours. Pump stopped.',
        'wet': 'Soil moisture is at the target. Pump stopped.',
        'calm': 'Crop stress forecast is below the trigger. Pump stopped.',
        'deferred': 'Hot hour. Irrigation waits for a cooler hour to cut evaporation.',
    }.get(reason, 'No power or water for the pump.')


def _must_shed(drivers, index, stocks):
    """Shed only when the battery cannot carry every load until the grid returns."""
    if drivers[index]['home_grid']:
        return False
    needed = 0.0
    for item in drivers[index:]:
        if item['home_grid']:
            break
        needed += max(0.0, item['demand_w'] - item['home_solar'])
    return stocks['home_battery_wh'] < needed


def _home_energy(d, stocks, kizuna, shed, totals):
    demand = d['demand_w']
    critical = min(CRITICAL_W, demand)
    load = critical if shed else demand
    from_solar = min(d['home_solar'], load)
    remaining = load - from_solar
    if remaining > 0 and not d['home_grid']:
        from_battery = min(remaining, max(0.0, stocks['home_battery_wh']))
        stocks['home_battery_wh'] -= from_battery
        remaining -= from_battery
    elif remaining > 0:
        remaining = 0.0
    surplus = d['home_solar'] - from_solar
    if surplus > 0:
        if kizuna:
            stored = min(surplus, HOME_BATTERY_WH - stocks['home_battery_wh'])
            stocks['home_battery_wh'] += stored
            totals['solar_stored_wh'] += stored
            totals['solar_curtailed_wh'] += surplus - stored
        else:
            totals['solar_curtailed_wh'] += surplus
    if shed:
        totals['shed_hours'] += 1
        critical_unmet = remaining
        noncritical_unmet = demand - critical
    else:
        critical_unmet = remaining * critical / load if load else 0.0
        noncritical_unmet = remaining - critical_unmet
    noncritical = max(demand - critical, 1.0)
    stress = 80 * (critical_unmet / critical if critical else 0) + 20 * (noncritical_unmet / noncritical)
    return {
        'shed': shed,
        'critical_unmet': round(critical_unmet, 1),
        'stress': round(min(100.0, stress), 1),
    }


def _home_water(d, stocks, kizuna, totals):
    demand = d['water_l']
    percent = stocks['home_tank_l'] / HOME_TANK_L * 100
    conserve = kizuna and percent < CONSERVE_TANK
    target = demand * ESSENTIAL_SHARE if conserve else demand
    deferred = demand - target
    drawn = min(target, stocks['home_tank_l'])
    stocks['home_tank_l'] -= drawn
    unmet = target - drawn
    stocks['home_tank_l'] = min(HOME_TANK_L, stocks['home_tank_l'] + d['refill_home'])
    if conserve:
        totals['conserve_hours'] += 1
    level = stocks['home_tank_l'] / HOME_TANK_L * 100
    stress = 60 * (unmet / demand) + 15 * (deferred / demand) + 40 * max(0.0, (CONSERVE_TANK - level) / CONSERVE_TANK)
    return {'conserve': conserve, 'stress': round(min(100.0, stress), 1)}


def _metrics(run, inputs):
    hours = run['hours']
    totals = run['totals']
    count = len(hours) or 1
    crisis = [
        item['water_stress'] >= CRISIS_WATER
        or item['energy_stress'] >= CRISIS_ENERGY
        or item['crop_stress'] >= STRESS_HIGH
        for item in hours
    ]
    recovery, ongoing = _recovery(crisis)
    affected = _affected(hours, totals)
    return {
        'water_stress': _mean(hours, 'water_stress'),
        'water_stress_peak': _peak(hours, 'water_stress'),
        'energy_stress': _mean(hours, 'energy_stress'),
        'energy_stress_peak': _peak(hours, 'energy_stress'),
        'crop_stress': _mean(hours, 'crop_stress'),
        'crop_stress_peak': _peak(hours, 'crop_stress'),
        'pump_outage_hours': totals['pump_outage_hours'],
        'tank_empty_hours': totals['tank_empty_hours'],
        'pump_hours': totals['pump_hours'],
        'water_lost_l': round(totals['water_lost_l'], 1),
        'rain_recovered_l': round(totals['rain_recovered_l'], 1),
        'irrigation_l': round(totals['irrigation_l'], 1),
        'solar_stored_wh': round(totals['solar_stored_wh'], 1),
        'solar_curtailed_wh': round(totals['solar_curtailed_wh'], 1),
        'solar_pump_wh': round(totals['solar_pump_wh'], 1),
        'battery_pump_wh': round(totals['battery_pump_wh'], 1),
        'grid_pump_wh': round(totals['grid_pump_wh'], 1),
        'energy_recovered_wh': round(totals['solar_stored_wh'] + totals['solar_pump_wh'], 1),
        'crop_protection': round(sum(1 for item in hours if item['crop_stress'] < STRESS_HIGH) / count * 100, 1),
        'crisis_hours': sum(crisis),
        'recovery_hours': recovery,
        'recovery_ongoing': ongoing,
        'affected': affected,
        'affected_count': sum(1 for item in affected.values() if item['affected']),
        'shed_hours': totals['shed_hours'],
        'rain_suspend_hours': totals['rain_suspend_hours'],
        'conserve_hours': totals['conserve_hours'],
        'deferred_irrigation_hours': totals['deferred_irrigation_hours'],
        'critical_unmet_wh': round(sum(item['critical_unmet_w'] for item in hours), 1),
        'soil_min': min(item['soil'] for item in hours),
        'duration': inputs['duration'],
    }


def _recovery(crisis):
    if not any(crisis):
        return 0, False
    first = crisis.index(True)
    last = len(crisis) - 1 - crisis[::-1].index(True)
    if last == len(crisis) - 1:
        return None, True
    return last - first + 1, False


def _affected(hours, totals):
    def first(test):
        for item in hours:
            if test(item):
                return item['hour']
        return None

    checks = {
        'grid': first(lambda item: item['grid_limited']),
        'home_power': first(lambda item: item['critical_unmet_w'] > 0),
        'battery': first(lambda item: min(item['home_battery_percent'], item['farm_battery_percent']) < BATTERY_RESERVE),
        'home_water': first(lambda item: item['water_stress'] >= CRISIS_WATER),
        'pump': first(lambda item: item['pump_no_power']),
        'irrigation': first(lambda item: item['soil'] < 30),
        'crops': first(lambda item: item['crop_stress'] >= STRESS_HIGH),
    }
    return {key: {'affected': hour is not None, 'first_hour': hour} for key, hour in checks.items()}


def _timer_loss_rate(drivers):
    """Share of irrigation water the fixed 10:00-13:00 timer loses in these hours."""
    losses = []
    for d in drivers:
        if 10 <= d['clock'] <= 13:
            if d['rain_mm'] > 0:
                losses.append(1.0)
            else:
                losses.append(0.4 if _sunny_and_hot(d) else 0.1)
    return sum(losses) / len(losses) if losses else 0.1


def _comparison(base, smart, timer_loss):
    def better_lower(key, unit, label):
        return {
            'key': key,
            'label': label,
            'unit': unit,
            'without': base[key],
            'with': smart[key],
            'lower_is_better': True,
        }

    rows = [
        better_lower('water_stress', '/100', 'Water stress'),
        better_lower('energy_stress', '/100', 'Energy stress'),
        better_lower('crop_stress', '/100', 'Crop stress'),
        better_lower('pump_outage_hours', 'h', 'Pump outage'),
        better_lower('affected_count', 'nodes', 'Affected nodes'),
        {
            'key': 'crop_protection',
            'label': 'Crop protection',
            'unit': '%',
            'without': base['crop_protection'],
            'with': smart['crop_protection'],
            'lower_is_better': False,
        },
    ]
    evaporation_avoided = max(0.0, smart['irrigation_l'] * timer_loss - smart['water_lost_l'])
    rain = smart['rain_recovered_l'] - base['rain_recovered_l']
    water_saved = round(evaporation_avoided + rain, 1)
    energy_recovered = round(smart['energy_recovered_wh'] - base['energy_recovered_wh'], 1)
    return {
        'rows': rows,
        'water_saved_l': water_saved,
        'water_saved_parts': {
            'rain_recovered_l': round(rain, 1),
            'evaporation_avoided_l': round(evaporation_avoided, 1),
        },
        'water_saved_rule': (
            'Rainwater recovered, plus irrigation water not lost to evaporation compared with '
            'the same volume on the 10:00-13:00 timer.'
        ),
        'energy_recovered_wh': energy_recovered,
        'energy_recovered_rule': 'Solar energy stored in batteries or used by the pump instead of being curtailed.',
        'recovery': {
            'without': base['recovery_hours'],
            'without_ongoing': base['recovery_ongoing'],
            'with': smart['recovery_hours'],
            'with_ongoing': smart['recovery_ongoing'],
        },
    }


def _propagation(inputs, drivers, run, metrics):
    peak_extra_w = max(d['demand_w'] - d['reference_w'] for d in drivers)
    grid_peak = max(d['grid_stress'] for d in drivers)
    outage = sum(1 for d in drivers if not d['grid_on'])
    tank_min = min(item['home_tank_percent'] for item in run['hours'])
    steps = [
        {'key': 'scenario', 'label': inputs['scenario'].replace('_', ' '), 'value': f"{inputs['temperature']:.0f}°C peak", 'triggered': True},
        {
            'key': 'energy_demand',
            'label': 'Energy demand ↑',
            'value': f'+{peak_extra_w / 1000:.1f} kW cooling at peak',
            'triggered': peak_extra_w >= 200,
        },
        {
            'key': 'grid_stress',
            'label': 'Grid stress',
            'value': f'{outage} h outage' if outage else f'{grid_peak:.0f}% peak',
            'triggered': grid_peak >= 75 or outage > 0,
        },
        {
            'key': 'water',
            'label': 'Water availability ↓',
            'value': f'home tank min {tank_min:.0f}%',
            'triggered': inputs['water'] < 40 or tank_min < CONSERVE_TANK,
        },
        {
            'key': 'pump',
            'label': 'Pump availability ↓',
            'value': f"{metrics['pump_outage_hours']} h without power",
            'triggered': metrics['pump_outage_hours'] > 0,
        },
        {
            'key': 'irrigation',
            'label': 'Irrigation ↓',
            'value': f"{metrics['pump_hours']} h delivered",
            'triggered': metrics['pump_outage_hours'] > 0 or metrics['soil_min'] < 30,
        },
        {
            'key': 'soil',
            'label': 'Soil moisture ↓',
            'value': f"min {metrics['soil_min']:.0f}%",
            'triggered': metrics['soil_min'] < min(inputs['soil'], IDEAL_MOISTURE) - 3,
        },
        {
            'key': 'crop',
            'label': 'Crop stress ↑',
            'value': f"peak {metrics['crop_stress_peak']:.0f}/100",
            'triggered': metrics['crop_stress_peak'] >= STRESS_HIGH,
        },
    ]
    shown = [step for step in steps if step['triggered']]
    return {
        'steps': shown,
        'cascade': len(shown) > 1,
        'note': 'Each step is a value from the run without KIZUNA. Steps that did not happen are left out.',
    }


def _response(run, base, smart):
    totals = run['totals']
    pump = {'label': 'Pump', 'value': f"{totals['pump_hours']} h"}
    irrigation = {'label': 'Irrigation', 'value': f"{totals['irrigation_l']:.0f} L"}
    chains = []
    harvested = totals['solar_pump_wh'] + totals['solar_stored_wh']
    off_grid = totals['solar_pump_wh'] + totals['battery_pump_wh']
    solar = [{'label': 'Solar', 'value': f'{_kwh(harvested)} harvested'}] if harvested > 0 else []
    if totals['solar_stored_wh'] > 0 or totals['battery_pump_wh'] > 0:
        solar.append({'label': 'Battery', 'value': f"{_kwh(totals['solar_stored_wh'])} stored"})
    if off_grid > 0:
        pump['value'] = f"{totals['pump_hours']} h · {_kwh(off_grid)} off-grid"
        chains.append(solar + [pump, irrigation])
    else:
        if solar:
            chains.append(solar)
        if totals['grid_pump_wh'] > 0:
            chains.append([{'label': 'Grid', 'value': _kwh(totals['grid_pump_wh'])}, pump, irrigation])
    if totals['rain_recovered_l'] > 0:
        chains.append([
            {'label': 'Rain', 'value': ''},
            {'label': 'Roof', 'value': ''},
            {'label': 'Tank', 'value': f"+{totals['rain_recovered_l']:.0f} L"},
        ])
    side = []
    if totals['shed_hours']:
        side.append(f"Non-critical loads shed for {totals['shed_hours']} h")
    if totals['rain_suspend_hours']:
        side.append(f"Irrigation suspended for rain: {totals['rain_suspend_hours']} h")
    if totals['conserve_hours']:
        side.append(f"Essential water only: {totals['conserve_hours']} h")
    if totals['deferred_irrigation_hours']:
        side.append(f"Irrigation moved to cooler hours: {totals['deferred_irrigation_hours']} h")

    if base['crisis_hours'] == 0 and smart['crisis_hours'] == 0:
        status, level = 'NO CRISIS', 'calm'
    elif not smart['recovery_ongoing']:
        status, level = 'CRISIS CONTAINED', 'contained'
    elif smart['crisis_hours'] < base['crisis_hours'] or (
        smart['affected_count'] < base['affected_count']
        and _load(smart) < _load(base) * 0.9
    ):
        status, level = 'CRISIS REDUCED', 'reduced'
    else:
        status, level = 'CRISIS NOT CONTAINED', 'active'
    return {
        'chains': chains,
        'side': side,
        'status': status,
        'level': level,
        'rule': (
            'Contained: no water, energy, or crop metric is in its crisis range at the end of the run. '
            'Reduced: still in crisis at the end, but for fewer hours than without KIZUNA, '
            'or with fewer affected nodes and at least 10% less combined stress.'
        ),
    }


def _kwh(wh):
    return f'{wh / 1000:.1f} kWh'


def _load(metrics):
    return metrics['water_stress'] + metrics['energy_stress'] + metrics['crop_stress']


def _event(hour, action, reason):
    return {'hour': hour, 'action': action, 'reason': reason}


def _mean(hours, key):
    return round(sum(item[key] for item in hours) / (len(hours) or 1), 1)


def _peak(hours, key):
    return round(max(item[key] for item in hours), 1)
