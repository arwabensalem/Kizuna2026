"""Synthetic hourly sensor series.

Values are a fixed function of the seed, the hour, and the scenario.
They are not measurements and they are not a claim about a real place.
"""

import math
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SCENARIOS = (
    'NORMAL',
    'HEATWAVE',
    'DROUGHT',
    'HEAVY_RAIN',
    'POWER_OUTAGE',
    'COMBINED_CRISIS',
)

ORIGIN = datetime(2026, 6, 1, 0, 0, tzinfo=ZoneInfo('Africa/Tunis'))

HOME_TANK_LITERS = 1500
FARM_TANK_LITERS = 8000
HOME_BATTERY_WH = 8000
FARM_BATTERY_WH = 10000
HOME_SOLAR_WATTS = 3000
FARM_SOLAR_WATTS = 4000

INITIAL_STOCKS = {
    'home_tank': 78.0,
    'farm_tank': 70.0,
    'home_battery': 65.0,
    'farm_battery': 60.0,
    'soil_moisture': 48.0,
}

_REFILL = {
    'NORMAL': 0.6,
    'HEATWAVE': 0.2,
    'DROUGHT': 0.0,
    'HEAVY_RAIN': 1.8,
    'POWER_OUTAGE': 0.4,
    'COMBINED_CRISIS': 0.0,
}


def clock_time(hour):
    return ORIGIN + timedelta(hours=hour)


def baseline(seed, scenario):
    """Hour 0. Stocks stay at the synthetic starting levels."""
    stocks = dict(INITIAL_STOCKS)
    weather = _weather(seed, 0, scenario)
    actuators = _decide(stocks, weather, scenario)
    served = _served(stocks, weather, actuators, scenario)
    return _pack(0, seed, scenario, stocks, served, actuators)


def advance_one(seed, hour, scenario, stocks):
    """One simulated hour. `stocks` are the levels at the start of the hour."""
    nxt = hour + 1
    weather = _weather(seed, nxt, scenario)
    actuators = _decide(stocks, weather, scenario)
    served = _served(stocks, weather, actuators, scenario)
    updated = _integrate(stocks, served, actuators, scenario)
    return _pack(nxt, seed, scenario, updated, served, actuators)


def _pack(hour, seed, scenario, stocks, served, actuators):
    sensors = _sensors(served, stocks, actuators)
    crisis = _crisis(scenario, stocks, served['grid_availability'])
    return {
        'hour': hour,
        'scenario': scenario,
        'seed': int(seed),
        'crisis_state': crisis,
        'sensors': sensors,
        'tanks': {
            'home_percent': stocks['home_tank'],
            'farm_percent': stocks['farm_tank'],
        },
        'batteries': {
            'home_percent': stocks['home_battery'],
            'farm_percent': stocks['farm_battery'],
        },
        'solar': {
            'home_watts': served['home_solar'],
            'farm_watts': served['farm_solar'],
        },
        'consumption': {
            'home_water_liters_per_hour': served['water'],
            'home_electricity_watts': served['electricity'],
        },
        'soil_moisture': stocks['soil_moisture'],
        'pump': {'farm': actuators['farm_pump']},
        'valves': {
            'home': actuators['home_valve'],
            'farm': actuators['farm_valve'],
        },
        'stocks': stocks,
    }


def _unit_interval(seed, hour, channel):
    rng = random.Random((int(seed) + 1) * 1_000_003 + int(hour) * 9_176 + int(channel) * 97)
    return rng.random()


def _jitter(seed, hour, channel, scale):
    return (_unit_interval(seed, hour, channel) * 2 - 1) * scale


def _clamp(value, low, high):
    return max(low, min(high, value))


def _r(value):
    return round(float(value), 2)


def _reading(value, unit, label):
    return {'value': value, 'unit': unit, 'label': label}


def _solar_fraction(hour):
    clock = hour % 24
    if clock <= 6 or clock >= 19:
        return 0.0
    return max(0.0, math.sin((clock - 6) / 13 * math.pi))


def _solar_factor(scenario):
    if scenario == 'HEAVY_RAIN':
        return 0.35
    if scenario == 'HEATWAVE':
        return 1.08
    if scenario == 'DROUGHT':
        return 1.05
    if scenario == 'COMBINED_CRISIS':
        return 0.9
    return 1.0


def _outage(scenario):
    return scenario in ('POWER_OUTAGE', 'COMBINED_CRISIS')


def _weather(seed, hour, scenario):
    clock = hour % 24
    wave = math.cos((clock - 15) / 24 * 2 * math.pi)
    temperature = 27 + 6 * wave
    if scenario in ('HEATWAVE', 'COMBINED_CRISIS'):
        temperature += 8
    if scenario == 'DROUGHT':
        temperature += 2
    if scenario == 'HEAVY_RAIN':
        temperature -= 3
    temperature += _jitter(seed, hour, 1, 0.6)
    temperature = _r(_clamp(temperature, 5, 50))

    farm_temperature = _r(_clamp(temperature + 1.2 + _jitter(seed, hour, 2, 0.4), 5, 52))

    humidity = 62 - (temperature - 24) * 1.3
    if scenario == 'HEATWAVE':
        humidity -= 10
    if scenario in ('DROUGHT', 'COMBINED_CRISIS'):
        humidity -= 14
    if scenario == 'HEAVY_RAIN':
        humidity += 20
    humidity = _r(_clamp(humidity + _jitter(seed, hour, 3, 1.5), 8, 100))
    farm_humidity = _r(_clamp(humidity - 4 + _jitter(seed, hour, 4, 1.5), 8, 100))

    if scenario == 'HEAVY_RAIN':
        rainfall = 8 + 3 * math.sin(hour / 3) + _jitter(seed, hour, 5, 1.0)
        rainfall = _r(_clamp(rainfall, 3, 16))
    elif scenario in ('DROUGHT', 'COMBINED_CRISIS'):
        rainfall = 0.0
    else:
        rainfall = _r(max(0.0, _jitter(seed, hour, 5, 0.45) - 0.28))

    morning = math.exp(-((clock - 7) ** 2) / 6)
    evening_water = math.exp(-((clock - 20) ** 2) / 8)
    water = 8 + 16 * morning + 12 * evening_water
    if scenario in ('HEATWAVE', 'COMBINED_CRISIS'):
        water *= 1.55
    elif scenario == 'DROUGHT':
        water *= 1.25
    elif scenario == 'HEAVY_RAIN':
        water *= 0.8
    water = _r(max(0.0, water + _jitter(seed, hour, 6, 0.7)))

    evening_load = math.exp(-((clock - 21) ** 2) / 10)
    electricity = 380 + 700 * evening_load
    if temperature > 30:
        electricity += (temperature - 30) * 80
    if scenario == 'HEATWAVE':
        electricity *= 1.35
    elif scenario == 'COMBINED_CRISIS':
        electricity *= 1.2
    electricity = _r(max(0.0, electricity + _jitter(seed, hour, 7, 15)))

    fraction = _solar_fraction(hour) * _solar_factor(scenario)
    home_solar = _r(_clamp(
        HOME_SOLAR_WATTS * fraction + _jitter(seed, hour, 8, 40 * fraction),
        0,
        HOME_SOLAR_WATTS,
    ))
    farm_solar = _r(_clamp(
        FARM_SOLAR_WATTS * fraction + _jitter(seed, hour, 9, 50 * fraction),
        0,
        FARM_SOLAR_WATTS,
    ))

    if _outage(scenario):
        availability = 0
        stress = 100.0 if scenario == 'COMBINED_CRISIS' else 92.0
    else:
        availability = 1
        stress = 18 + 10 * max(0.0, math.sin((clock - 8) / 24 * 2 * math.pi))
        if scenario == 'HEATWAVE':
            stress += 28
        elif scenario == 'DROUGHT':
            stress += 12
        elif scenario == 'HEAVY_RAIN':
            stress += 8
        stress = _clamp(stress + _jitter(seed, hour, 10, 2), 0, 100)

    return {
        'home_temperature': temperature,
        'farm_temperature': farm_temperature,
        'home_humidity': humidity,
        'farm_humidity': farm_humidity,
        'rainfall': rainfall,
        'water_demand': water,
        'electricity_demand': electricity,
        'home_solar': home_solar,
        'farm_solar': farm_solar,
        'grid_availability': availability,
        'grid_stress': _r(stress),
    }


def _decide(stocks, weather, scenario):
    raining = scenario == 'HEAVY_RAIN'
    outage = weather['grid_availability'] == 0
    wants_water = stocks['soil_moisture'] < 40 and not raining
    power_ok = (not outage) or stocks['farm_battery'] > 20 or weather['farm_solar'] > 150
    pump = 'on' if wants_water and power_ok else 'off'
    if scenario == 'COMBINED_CRISIS' or stocks['home_tank'] < 20:
        home_valve = 'closed'
    else:
        home_valve = 'open'
    return {
        'farm_pump': pump,
        'farm_valve': 'open' if pump == 'on' else 'closed',
        'home_valve': home_valve,
    }


def _served(stocks, weather, actuators, scenario):
    water = weather['water_demand']
    if actuators['home_valve'] == 'closed':
        water = _r(water * 0.25)
    electricity = weather['electricity_demand']
    if weather['grid_availability'] == 0:
        available = weather['home_solar'] + max(0.0, stocks['home_battery']) / 100 * HOME_BATTERY_WH
        electricity = _r(min(electricity, available))
    served = dict(weather)
    served['water'] = water
    served['electricity'] = electricity
    served['outage'] = scenario in ('POWER_OUTAGE', 'COMBINED_CRISIS')
    return served


def _integrate(stocks, served, actuators, scenario):
    refill = _REFILL[scenario]
    home_draw = served['water'] / HOME_TANK_LITERS * 100
    farm_draw = (160 if actuators['farm_pump'] == 'on' else 12) / FARM_TANK_LITERS * 100
    home_tank = _r(_clamp(stocks['home_tank'] - home_draw + refill, 0, 100))
    farm_tank = _r(_clamp(stocks['farm_tank'] - farm_draw + refill * 0.5, 0, 100))

    home_net = served['home_solar'] - served['electricity']
    home_battery = _r(_clamp(
        stocks['home_battery'] + home_net / HOME_BATTERY_WH * 100,
        0,
        100,
    ))
    farm_load = 100 + (700 if actuators['farm_pump'] == 'on' else 0)
    if served['grid_availability'] == 0:
        available = served['farm_solar'] + max(0.0, stocks['farm_battery']) / 100 * FARM_BATTERY_WH
        farm_load = min(farm_load, available)
    farm_battery = _r(_clamp(
        stocks['farm_battery'] + (served['farm_solar'] - farm_load) / FARM_BATTERY_WH * 100,
        0,
        100,
    ))

    soil_delta = -0.3
    if scenario in ('HEATWAVE', 'COMBINED_CRISIS'):
        soil_delta -= 0.9
    if scenario in ('DROUGHT', 'COMBINED_CRISIS'):
        soil_delta -= 0.8
    if scenario == 'HEAVY_RAIN':
        soil_delta += served['rainfall'] * 0.9
    if actuators['farm_pump'] == 'on':
        soil_delta += 2.2
    soil = _r(_clamp(stocks['soil_moisture'] + soil_delta, 0, 100))
    return {
        'home_tank': home_tank,
        'farm_tank': farm_tank,
        'home_battery': home_battery,
        'farm_battery': farm_battery,
        'soil_moisture': soil,
    }


def _sensors(served, stocks, actuators):
    return {
        'home': {
            'temperature': _reading(served['home_temperature'], '°C', 'Temperature'),
            'humidity': _reading(served['home_humidity'], '%', 'Humidity'),
            'water_consumption': _reading(served['water'], 'L/h', 'Water consumption'),
            'electricity_consumption': _reading(served['electricity'], 'W', 'Electricity consumption'),
            'tank_level': _reading(stocks['home_tank'], '%', 'Tank level'),
            'solar_production': _reading(served['home_solar'], 'W', 'Solar production'),
        },
        'farm': {
            'soil_moisture': _reading(stocks['soil_moisture'], '%', 'Soil moisture'),
            'temperature': _reading(served['farm_temperature'], '°C', 'Temperature'),
            'humidity': _reading(served['farm_humidity'], '%', 'Humidity'),
            'rainfall': _reading(served['rainfall'], 'mm', 'Rainfall'),
            'tank_level': _reading(stocks['farm_tank'], '%', 'Tank level'),
            'solar_production': _reading(served['farm_solar'], 'W', 'Solar production'),
            'pump_status': _reading(actuators['farm_pump'], '', 'Pump status'),
        },
        'grid': {
            'grid_availability': _reading(served['grid_availability'], '', 'Grid availability'),
            'grid_stress': _reading(served['grid_stress'], '%', 'Grid stress'),
        },
    }


def _crisis(scenario, stocks, availability):
    if scenario == 'COMBINED_CRISIS':
        return 'crisis'
    if availability == 0 and (stocks['home_tank'] < 25 or stocks['soil_moisture'] < 25):
        return 'crisis'
    if availability == 0 or stocks['home_tank'] < 15 or stocks['soil_moisture'] < 15:
        return 'alert'
    if scenario in ('HEATWAVE', 'DROUGHT', 'HEAVY_RAIN'):
        return 'watch'
    return 'none'
