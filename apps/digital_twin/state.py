"""Build the living twin from one home's stored simulation state.

The numbers come from the home, its appliances, its actuators, and the
simulated weather tank. They are not measurements of a real building.
"""

from apps.actuators.models import Actuator
from apps.homes.models import Appliance
from apps.homes.simulation import simulate_home

# A clear hour in the authored weather series is about 700 W/m².
# This only scales the home's own solar figure. It is not a weather claim.
CLEAR_SUN_WM2 = 700
PUMP_FALLBACK_LPH = 120
INDOOR = {'bedroom', 'bathroom', 'kitchen', 'living_room', 'other'}
GARDEN = {'garden', 'pool'}


def build_twin_state(home):
    appliances = list(home.appliances.select_related('room'))
    rooms = _rooms(home)
    actuators = {item.kind: item for item in home.actuators.all()}
    snapshot = simulate_home(home)
    collection = home.collection_systems.order_by('pk').first()
    timeline = home.weather_timelines.order_by('-created_at').first()
    hour = None
    if timeline is not None:
        hour = timeline.hours.filter(hour=timeline.hour).first()

    solar_watts = _solar(snapshot['solar_watts'], hour)
    energy_watts = snapshot['energy_watts']
    valve_open = home.water_valve_open
    pump_running = _pump_running(actuators, appliances)
    battery_state = _battery_state(actuators, solar_watts, energy_watts)
    allocation = _allocation(actuators)
    tank = _tank(collection, snapshot)
    weather = _weather(hour, collection)
    flows = _flows(
        solar_watts,
        energy_watts,
        allocation,
        battery_state,
        snapshot['battery_percent'],
        pump_running,
        valve_open,
        appliances,
        weather,
    )
    return {
        'simulated': True,
        'label': (
            'Living digital twin for this home. '
            'Rooms, appliances, the valve, actuators, and the simulated weather tank drive the scene. '
            'This is not a measurement of a real building.'
        ),
        'home': {
            'id': home.pk,
            'name': home.name,
            'has_garden': home.has_garden,
            'has_pool': home.has_pool,
        },
        'rooms': [
            {
                'id': room['id'],
                'name': room['name'],
                'kind': room['kind'],
                'stored': room['stored'],
                'lights_on': _lights_on(room, appliances),
            }
            for room in rooms
        ],
        'appliances': [
            {
                'id': item.pk,
                'name': item.display_name,
                'kind': item.kind,
                'room_id': item.room_id,
                'active': item.is_active,
                'power_watts': item.power_watts,
                'water_liters_per_hour': float(item.water_liters_per_hour),
            }
            for item in appliances
        ],
        'valve': {'open': valve_open},
        'pump': {'running': pump_running},
        'tank': tank,
        'battery': {
            'percent': snapshot['battery_percent'],
            'state': battery_state,
        },
        'solar': {
            'watts': solar_watts,
            'allocation': allocation,
        },
        'loads': {'watts': energy_watts},
        'weather': weather,
        'flows': flows,
    }


def _rooms(home):
    stored = [
        {'id': room.pk, 'name': room.name, 'kind': room.kind, 'stored': True}
        for room in home.rooms.all()
    ]
    if stored:
        return stored
    implied = []
    for index in range(home.bedrooms):
        implied.append(_implied('bedroom', 'Bedroom', index))
    for index in range(home.bathrooms):
        implied.append(_implied('bathroom', 'Bathroom', index))
    if home.has_kitchen:
        implied.append(_implied('kitchen', 'Kitchen', 0))
    if home.has_living_room:
        implied.append(_implied('living_room', 'Living room', 0))
    if home.has_garden:
        implied.append(_implied('garden', 'Garden', 0))
    if home.has_pool:
        implied.append(_implied('pool', 'Pool', 0))
    if home.has_garage:
        implied.append(_implied('garage', 'Garage', 0))
    if not implied:
        implied.append(_implied('living_room', 'Living room', 0))
    return implied


def _implied(kind, name, index):
    suffix = f'-{index + 1}' if index else ''
    return {
        'id': f'implied-{kind}{suffix}',
        'name': name if index == 0 else f'{name} {index + 1}',
        'kind': kind,
        'stored': False,
    }


def _lights_on(room, appliances):
    assigned = [
        item for item in appliances
        if item.room_id == room['id'] and item.kind == Appliance.Kind.LIGHTS
    ]
    if assigned:
        return any(item.is_active for item in assigned)
    if room['kind'] not in INDOOR:
        return False
    return any(
        item.is_active and item.room_id is None and item.kind == Appliance.Kind.LIGHTS
        for item in appliances
    )


def _solar(base, hour):
    if hour is None:
        return base
    factor = min(1.3, float(hour.solar_radiation_wm2) / CLEAR_SUN_WM2)
    return max(0, round(base * factor))


def _pump_running(actuators, appliances):
    pump = actuators.get(Actuator.Kind.IRRIGATION_PUMP)
    if pump is not None and pump.state == 'on':
        return True
    return any(item.is_active and item.kind == Appliance.Kind.PUMP for item in appliances)


def _battery_state(actuators, solar_watts, energy_watts):
    battery = actuators.get(Actuator.Kind.BATTERY)
    if battery is not None:
        return battery.state
    if solar_watts > energy_watts + 50:
        return 'charging'
    if energy_watts > solar_watts + 50:
        return 'discharging'
    return 'idle'


def _allocation(actuators):
    solar = actuators.get(Actuator.Kind.SOLAR_ALLOCATION)
    if solar is None:
        return 'essential'
    return solar.state


def _tank(collection, snapshot):
    household = snapshot['tank_percent']
    if collection is None:
        return {
            'liters': round(20 * household, 1),
            'capacity_liters': 2000,
            'percent': household,
            'household_percent': household,
            'source': 'household',
        }
    capacity = collection.tank_capacity_liters or 1
    liters = float(collection.tank_liters)
    percent = round(liters / capacity * 100, 1)
    return {
        'liters': round(liters, 1),
        'capacity_liters': capacity,
        'percent': percent,
        'household_percent': household,
        'source': 'collection',
    }


def _weather(hour, collection):
    prepared = bool(collection and collection.prepared)
    if hour is None:
        return {
            'raining': False,
            'rainfall_mm': 0,
            'collecting': False,
            'prepared': prepared,
        }
    rainfall = float(hour.rainfall_mm)
    return {
        'raining': rainfall > 0,
        'rainfall_mm': rainfall,
        'collecting': rainfall > 0 and prepared,
        'prepared': prepared,
    }


def _flows(solar, energy, allocation, battery_state, battery_percent, pump, valve, appliances, weather):
    if solar <= 0:
        to_home = 0
    elif energy > 0:
        to_home = min(solar, energy)
    elif allocation == 'battery':
        to_home = 0
    else:
        to_home = solar
    surplus = max(0, solar - to_home)
    to_battery = surplus if allocation == 'battery' or battery_state == 'charging' else 0
    bathroom = _bathroom_water(appliances, valve)
    garden = _garden_water(appliances, valve, pump)
    return [
        _flow('solar_home', 'energy', 'solar', 'home', to_home > 0, to_home),
        _flow('solar_battery', 'energy', 'solar', 'battery', to_battery > 0, to_battery),
        _flow('battery_pump', 'energy', 'battery', 'pump', pump and battery_percent > 0, 120 if pump else 0),
        _flow('water_bathroom', 'water', 'tank', 'bathroom', bathroom > 0, bathroom),
        _flow('water_garden', 'water', 'tank', 'garden', garden > 0, garden),
        _flow('rain_roof', 'water', 'rain', 'roof', weather['raining'], weather['rainfall_mm']),
        _flow('roof_tank', 'water', 'roof', 'tank', weather['collecting'], weather['rainfall_mm'] if weather['collecting'] else 0),
    ]


def _bathroom_water(appliances, valve_open):
    if not valve_open:
        return 0
    total = 0
    for item in appliances:
        if not item.is_active:
            continue
        if item.kind == Appliance.Kind.PUMP:
            continue
        if item.room is not None and item.room.kind in GARDEN:
            continue
        domestic = item.kind in Appliance.WATER_KINDS or (
            item.room is not None and item.room.kind == 'bathroom'
        )
        if domestic:
            total += float(item.water_liters_per_hour)
    return round(total, 1)


def _garden_water(appliances, valve_open, pump_running):
    if not valve_open:
        return 0
    total = 0.0
    pump_rate = 0.0
    for item in appliances:
        if not item.is_active:
            continue
        if item.kind == Appliance.Kind.PUMP:
            pump_rate += float(item.water_liters_per_hour)
        elif item.room is not None and item.room.kind in GARDEN:
            total += float(item.water_liters_per_hour)
    if pump_running:
        total += pump_rate or PUMP_FALLBACK_LPH
    return round(total, 1)


def _flow(key, kind, origin, target, active, amount):
    return {
        'id': key,
        'kind': kind,
        'from': origin,
        'to': target,
        'active': bool(active),
        'amount': round(float(amount), 1),
    }
