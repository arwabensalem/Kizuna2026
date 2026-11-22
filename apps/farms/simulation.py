"""Deterministic farm snapshot.

These figures are simulated from the farm, crops, tanks, solar arrays,
irrigation systems, and sensors the farmer entered. They are not live
readings and they do not use a trained model.
"""

SOIL_MOISTURE = {
    'sand': 28,
    'loam': 46,
    'silt': 52,
    'clay': 64,
    'rocky': 22,
}

SOIL_WATER_FACTOR = {
    'sand': 1.25,
    'loam': 1,
    'silt': 0.95,
    'clay': 0.8,
    'rocky': 1.15,
}

CROP_LITERS_PER_M2 = {
    'olive': 2.2,
    'tomato': 4.5,
    'wheat': 3.0,
    'pepper': 4.0,
    'barley': 2.8,
    'citrus': 3.4,
    'other': 3.0,
}

IDEAL_MOISTURE = 45


def _clamp(value, low, high):
    return max(low, min(high, value))


def simulate_farm(farm):
    tanks = list(farm.tanks.all())
    solar_units = list(farm.solar_units.all())
    systems = list(farm.irrigation_systems.all())
    sensors = list(farm.farm_sensors.all())

    tank_capacity = sum(item.capacity_liters for item in tanks) or farm.tank_capacity_liters
    solar_capacity = sum(item.capacity_watts for item in solar_units) or farm.solar_capacity_watts
    running = [item for item in systems if item.is_active]
    if systems:
        irrigating = bool(running)
        irrigation_status = 'Running' if irrigating else 'Idle'
    elif farm.irrigation_type != 'none':
        irrigating = True
        irrigation_status = 'Configured'
    else:
        irrigating = False
        irrigation_status = 'Not set'

    moisture = SOIL_MOISTURE.get(farm.soil_type, 46) + (12 if irrigating else -8)
    moisture = int(_clamp(round(moisture), 0, 100))

    area = float(farm.area_m2 or 0)
    liters_per_m2 = CROP_LITERS_PER_M2.get(farm.crop_type, 3.0)
    soil_factor = SOIL_WATER_FACTOR.get(farm.soil_type, 1)
    water_liters = round(area * liters_per_m2 * soil_factor)

    draw = 18 if irrigating else 4
    capacity = tank_capacity or 0
    ratio = (water_liters / capacity) if capacity else 1
    tank_level = 78 - draw - min(20, ratio * 10)
    tank_level = int(_clamp(round(tank_level), 0, 100))

    solar_watts = round(solar_capacity * 0.72)
    stress = abs(moisture - IDEAL_MOISTURE) * 1.5
    if tank_level < 25:
        stress += 15
    stress = int(_clamp(round(stress), 0, 100))
    if stress < 25:
        crop_status = 'Stable'
    elif stress < 55:
        crop_status = 'Watch'
    else:
        crop_status = 'Stressed'

    return {
        'soil_moisture': moisture,
        'crop_status': crop_status,
        'tank_percent': tank_level,
        'solar_watts': solar_watts,
        'irrigation_status': irrigation_status,
        'water_liters_per_day': water_liters,
        'crop_stress': stress,
        'tank_capacity_liters': int(tank_capacity or 0),
        'solar_capacity_watts': int(solar_capacity or 0),
        'sensor_count': len(sensors),
        'active_sensors': [
            {
                'name': item.display_name,
                'kind': item.get_kind_display(),
                'unit': item.unit,
            }
            for item in sensors
            if item.is_active
        ],
    }
