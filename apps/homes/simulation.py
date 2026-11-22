"""Deterministic home snapshot.

These figures are simulated from the rooms and appliances the citizen entered.
They are not meter readings and they do not use a trained model.
"""


def _clamp(value, low, high):
    return max(low, min(high, value))


def simulate_home(home):
    appliances = list(home.appliances.all())
    active = [item for item in appliances if item.is_active]
    energy_watts = sum(item.power_watts for item in active)
    water_liters = sum(float(item.water_liters_per_hour) for item in active)
    area = float(home.area_m2 or 0)
    solar_watts = round(area * 10 + (200 if home.has_garden else 0))
    battery = round(_clamp(60 + (solar_watts - energy_watts) / 50, 5, 100))
    tank = round(_clamp(75 - water_liters * 2 - home.residents, 0, 100))
    solar_covers_half = solar_watts >= energy_watts * 0.5
    resilience = round(0.4 * tank + 0.3 * battery + (30 if solar_covers_half else 12))
    resilience = int(_clamp(resilience, 0, 100))
    return {
        'water_liters_per_hour': round(water_liters, 1),
        'energy_watts': energy_watts,
        'solar_watts': solar_watts,
        'battery_percent': battery,
        'tank_percent': tank,
        'resilience_score': resilience,
        'active_count': len(active),
        'active_appliances': [
            {
                'name': item.display_name,
                'kind': item.get_kind_display(),
                'power_watts': item.power_watts,
                'water_liters_per_hour': float(item.water_liters_per_hour),
                'room': item.room.name if item.room_id else '',
            }
            for item in active
        ],
    }
