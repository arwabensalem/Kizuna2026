"""Reproducible synthetic datasets for the demo models.

Every row is generated. Nothing here is a meter reading or an observation
from a real place. The same seed always rebuilds the same frames.

The farm targets reuse the demo crop and soil coefficients already shown on
the farm screen, then add weather and noise. Those coefficients are part of
this demo, not a field study.
"""

import numpy as np
import pandas as pd

from apps.farms.models import Farm
from apps.farms.simulation import CROP_LITERS_PER_M2, IDEAL_MOISTURE, SOIL_WATER_FACTOR

SEED = 20260601
DATASET = 'synthetic_demo'

WATER_FEATURES = [
    'residents',
    'temperature',
    'day_of_week',
    'historical_consumption',
    'appliance_usage',
]
ENERGY_FEATURES = [
    'temperature',
    'appliance_load',
    'solar_production',
    'hour',
    'historical_energy',
]
FARM_FEATURES = [
    'soil_moisture',
    'temperature',
    'humidity',
    'rainfall',
    'crop_type',
    'soil_type',
    'area',
]
ANOMALY_FEATURES = [
    'temperature',
    'humidity',
    'water_consumption',
    'electricity_consumption',
    'soil_moisture',
    'rainfall',
    'tank_level',
    'solar_production',
]

# Liste figée : les modèles déjà entraînés attendent ces 7 cultures.
# Les nouvelles cultures (dattier, vigne…) passent par « other ».
CROP_TYPES = ['olive', 'tomato', 'wheat', 'pepper', 'barley', 'citrus', 'other']
SOIL_TYPES = [value for value, _label in Farm.Soil.choices]

WATER_SPEC = {'numeric': WATER_FEATURES, 'categories': {}}
ENERGY_SPEC = {'numeric': ENERGY_FEATURES, 'categories': {}}
FARM_SPEC = {
    'numeric': ['soil_moisture', 'temperature', 'humidity', 'rainfall', 'area'],
    'categories': {'crop_type': CROP_TYPES, 'soil_type': SOIL_TYPES},
}
ANOMALY_SPEC = {'numeric': ANOMALY_FEATURES, 'categories': {}}


def generator(seed=SEED):
    return np.random.Generator(np.random.PCG64(seed))


def design_matrix(frame, spec):
    """Numeric columns plus one column per category level, in a fixed order."""
    data = {}
    for column in spec['numeric']:
        data[column] = frame[column].astype(float)
    for name, levels in spec['categories'].items():
        for level in levels:
            data[f'{name}_{level}'] = (frame[name] == level).astype(float)
    return pd.DataFrame(data, index=frame.index)


def water_frame(rows, seed=SEED):
    rng = generator(seed)
    residents = rng.integers(1, 9, rows)
    temperature = rng.normal(27, 6, rows).clip(8, 45)
    day_of_week = rng.integers(0, 7, rows)
    historical = rng.uniform(2, 40, rows)
    appliance_usage = rng.uniform(0, 24, rows)
    weekend = (day_of_week >= 5).astype(float)
    noise = rng.normal(0, 1.1, rows)
    target = (
        3.2 * residents
        + 0.28 * np.maximum(temperature - 22, 0)
        + 4.5 * weekend
        + 0.45 * historical
        + 0.7 * appliance_usage
        + noise
    )
    frame = pd.DataFrame({
        'residents': residents,
        'temperature': temperature,
        'day_of_week': day_of_week,
        'historical_consumption': historical,
        'appliance_usage': appliance_usage,
        'water_liters_per_hour': np.clip(target, 0, None),
        'dataset': DATASET,
    })
    return frame


def energy_frame(rows, seed=SEED):
    rng = generator(seed + 1)
    temperature = rng.normal(27, 6, rows).clip(8, 45)
    appliance_load = rng.uniform(80, 3500, rows)
    solar = rng.uniform(0, 3000, rows)
    hour = rng.integers(0, 24, rows)
    historical = rng.uniform(80, 3200, rows)
    evening = np.exp(-((hour - 21) ** 2) / 14)
    morning = np.exp(-((hour - 7) ** 2) / 10)
    noise = rng.normal(0, 35, rows)
    target = (
        0.62 * appliance_load
        + 48 * np.maximum(temperature - 28, 0)
        + 220 * evening
        + 90 * morning
        + 0.22 * historical
        - 0.03 * solar
        + noise
    )
    return pd.DataFrame({
        'temperature': temperature,
        'appliance_load': appliance_load,
        'solar_production': solar,
        'hour': hour,
        'historical_energy': historical,
        'electricity_watts': np.clip(target, 0, None),
        'dataset': DATASET,
    })


def farm_frame(rows, seed=SEED):
    rng = generator(seed + 2)
    crop_type = rng.choice(CROP_TYPES, rows)
    soil_type = rng.choice(SOIL_TYPES, rows)
    soil_moisture = rng.uniform(12, 80, rows)
    temperature = rng.normal(28, 5, rows).clip(8, 45)
    humidity = rng.uniform(20, 90, rows)
    rainfall = rng.choice(
        [0, 0, 0, 0, 1, 4, 12],
        rows,
    ).astype(float) + rng.random(rows)
    area = rng.uniform(200, 8000, rows)
    rate = pd.Series(crop_type).map(CROP_LITERS_PER_M2).to_numpy(dtype=float)
    soil_factor = pd.Series(soil_type).map(SOIL_WATER_FACTOR).to_numpy(dtype=float)
    moisture_factor = 1.15 - (soil_moisture / 100)
    heat = 1 + 0.03 * np.maximum(temperature - 26, 0)
    humidity_factor = 1.05 - (humidity / 250)
    rain_credit = rainfall * area * 0.04
    noise = rng.normal(0, 0.02, rows) * area
    water = rate * soil_factor * area * moisture_factor * heat * humidity_factor - rain_credit + noise
    ideal = float(IDEAL_MOISTURE)
    sandy = (soil_type == 'sand').astype(float)
    rocky = (soil_type == 'rocky').astype(float)
    stress = (
        np.abs(soil_moisture - ideal) * 1.5
        + np.maximum(temperature - 32, 0) * 2
        + np.maximum(40 - humidity, 0) * 0.3
        - rainfall * 1.2
        + sandy * 5
        + rocky * 7
        + rng.normal(0, 1.5, rows)
    )
    return pd.DataFrame({
        'soil_moisture': soil_moisture,
        'temperature': temperature,
        'humidity': humidity,
        'rainfall': rainfall,
        'crop_type': crop_type,
        'soil_type': soil_type,
        'area': area,
        'farm_water_liters_per_day': np.clip(water, 0, None),
        'crop_stress': np.clip(stress, 0, 100),
        'dataset': DATASET,
    })


def anomaly_frame(rows, seed=SEED, anomaly_rate=0.08):
    """Normal demo readings, plus planted outliers marked is_anomaly.

    is_anomaly is a generator label for validation scoring. It is not a
    model feature, and it is not a record of a real fault.
    """
    rng = generator(seed + 3)
    frame = pd.DataFrame({
        'temperature': rng.normal(27, 4, rows).clip(12, 40),
        'humidity': rng.normal(58, 10, rows).clip(25, 90),
        'water_consumption': rng.normal(14, 6, rows).clip(0, 50),
        'electricity_consumption': rng.normal(700, 250, rows).clip(50, 2500),
        'soil_moisture': rng.normal(46, 10, rows).clip(15, 80),
        'rainfall': rng.exponential(1.2, rows).clip(0, 15),
        'tank_level': rng.normal(68, 12, rows).clip(20, 100),
        'solar_production': rng.uniform(0, 2800, rows),
    })
    planted = rng.random(rows) < anomaly_rate
    extreme = {
        'temperature': (55, 70),
        'humidity': (0, 8),
        'water_consumption': (400, 900),
        'electricity_consumption': (12000, 20000),
        'soil_moisture': (0, 4),
        'rainfall': (80, 140),
        'tank_level': (0, 3),
        'solar_production': (9000, 14000),
    }
    indexes = np.flatnonzero(planted)
    for index in indexes:
        columns = rng.choice(ANOMALY_FEATURES, size=int(rng.integers(2, 4)), replace=False)
        for column in columns:
            low, high = extreme[column]
            frame.loc[index, column] = float(rng.uniform(low, high))
    frame['is_anomaly'] = planted.astype(int)
    frame['dataset'] = DATASET
    return frame
