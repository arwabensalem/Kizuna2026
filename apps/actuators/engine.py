"""Apply the autopilot rules and record every result.

Assist alerts and does not move an actuator.
Smart may run the predefined safe actions: close a valve on a critical leak,
suspend irrigation when rain is expected or the grid is out, and shed
non-critical loads during an outage.
Autopilot may also start irrigation, steer solar, and use the battery.
Nothing moves unless that actuator is authorized.
"""

from django.db import transaction

from apps.actuators.models import Actuator, ActuatorAction
from apps.homes.models import Appliance

STRESS_HIGH = 55
TANK_AVAILABLE = 25
TANK_STORED = 85
BATTERY_RESERVE = 15
SURPLUS_MARGIN = 150

SAFE_RULES = {'leak', 'rain', 'outage_pump', 'outage_loads'}
NON_CRITICAL = (
    Appliance.Kind.TV,
    Appliance.Kind.DISHWASHER,
    Appliance.Kind.WASHING_MACHINE,
)
RANK = {'assist': 0, 'smart': 1, 'autopilot': 2}

DEFAULT_STATE = {
    Actuator.Kind.WATER_VALVE: 'open',
    Actuator.Kind.IRRIGATION_PUMP: 'off',
    Actuator.Kind.BATTERY: 'idle',
    Actuator.Kind.SOLAR_ALLOCATION: 'essential',
    Actuator.Kind.NON_CRITICAL_LOADS: 'on',
}


def current_mode(home, farm):
    modes = []
    if home is not None:
        modes.append(home.autonomy_mode)
    if farm is not None:
        modes.append(farm.autonomy_mode)
    if not modes:
        return 'assist'
    return min(modes, key=lambda mode: RANK[mode])


def ensure_actuators(home, farm):
    """Create the five actuators once. Existing states are left alone."""
    found = {}
    if home is not None:
        valve = 'open' if home.water_valve_open else 'closed'
        found[Actuator.Kind.WATER_VALVE] = _one(home=home, kind=Actuator.Kind.WATER_VALVE, state=valve)
        for kind in (
            Actuator.Kind.BATTERY,
            Actuator.Kind.SOLAR_ALLOCATION,
            Actuator.Kind.NON_CRITICAL_LOADS,
        ):
            found[kind] = _one(home=home, kind=kind, state=DEFAULT_STATE[kind])
        if farm is None:
            found[Actuator.Kind.IRRIGATION_PUMP] = _one(
                home=home,
                kind=Actuator.Kind.IRRIGATION_PUMP,
                state=DEFAULT_STATE[Actuator.Kind.IRRIGATION_PUMP],
            )
    if farm is not None:
        found[Actuator.Kind.IRRIGATION_PUMP] = _one(
            farm=farm,
            kind=Actuator.Kind.IRRIGATION_PUMP,
            state=DEFAULT_STATE[Actuator.Kind.IRRIGATION_PUMP],
        )
        if home is None:
            for kind, state in DEFAULT_STATE.items():
                if kind == Actuator.Kind.IRRIGATION_PUMP:
                    continue
                found[kind] = _one(farm=farm, kind=kind, state=state)
    return found


def run_rules(home, farm, situation):
    mode = current_mode(home, farm)
    actuators = ensure_actuators(home, farm)
    plans = _plans(situation, actuators)
    with transaction.atomic():
        return [_apply(plan, mode) for plan in plans]


def _one(kind, state, home=None, farm=None):
    lookup = {'kind': kind}
    if home is not None:
        lookup['home'] = home
    else:
        lookup['farm'] = farm
    actuator, _created = Actuator.objects.get_or_create(**lookup, defaults={'state': state})
    return actuator


def _plans(situation, actuators):
    plans = []
    leak = situation['critical_leak']
    stress = situation['crop_stress']
    tank = situation['tank_percent']
    rain = situation['rain_expected']
    grid = situation['grid_available']
    solar = situation['solar_watts']
    essential = situation['essential_watts']
    battery_percent = situation['battery_percent']
    stressed = stress >= STRESS_HIGH
    water_ready = tank >= TANK_AVAILABLE

    if leak:
        plans.append(_plan(
            actuators[Actuator.Kind.WATER_VALVE],
            'closed',
            'close_valve',
            'leak',
            'Critical leak reported for this check. Close the water valve.',
            safe=True,
        ))

    pump = actuators[Actuator.Kind.IRRIGATION_PUMP]
    if rain:
        reason = 'Rain is expected. Suspend non-essential irrigation.'
        if stressed:
            reason += f' Crop stress is {stress:.0f}, and irrigation stays off while rain is expected.'
        plans.append(_plan(pump, 'off', 'suspend_irrigation', 'rain', reason, safe=True))
    elif not grid:
        reason = 'The grid is unavailable. Suspend irrigation so critical loads come first.'
        if stressed:
            reason += f' Crop stress is {stress:.0f}, and irrigation stays off during the outage.'
        plans.append(_plan(pump, 'off', 'suspend_irrigation', 'outage_pump', reason, safe=True))
    elif stressed and water_ready:
        plans.append(_plan(
            pump,
            'on',
            'start_irrigation',
            'crop_stress',
            (
                f'Crop stress is {stress:.0f} and the tank is at {tank:.0f}%. '
                'Start irrigation.'
            ),
            safe=False,
        ))
    elif stressed:
        plans.append(_plan(
            pump,
            None,
            'alert',
            'crop_stress',
            (
                f'Crop stress is {stress:.0f}, and the tank is at {tank:.0f}%. '
                'Irrigation was not started because the available water is below 25%.'
            ),
            safe=False,
        ))

    loads = actuators[Actuator.Kind.NON_CRITICAL_LOADS]
    battery = actuators[Actuator.Kind.BATTERY]
    solar_actuator = actuators[Actuator.Kind.SOLAR_ALLOCATION]
    if not grid:
        plans.append(_plan(
            loads,
            'shed',
            'shed_non_critical_loads',
            'outage_loads',
            'The grid is unavailable. Shed non-critical loads and keep critical loads first.',
            safe=True,
        ))
        if battery_percent >= BATTERY_RESERVE:
            plans.append(_plan(
                battery,
                'discharging',
                'discharge_battery',
                'power_outage',
                (
                    f'The grid is unavailable and the battery is at {battery_percent:.0f}%. '
                    'Discharge the battery for critical loads.'
                ),
                safe=False,
            ))
        else:
            plans.append(_plan(
                battery,
                None,
                'alert',
                'power_outage',
                (
                    f'The grid is unavailable and the battery is at {battery_percent:.0f}%. '
                    'It stays as it is because the reserve is below 15%.'
                ),
                safe=False,
            ))
        plans.append(_plan(
            solar_actuator,
            'essential',
            'set_solar_allocation',
            'power_outage',
            'The grid is unavailable. Point solar production at essential loads.',
            safe=False,
        ))
    elif solar >= essential + SURPLUS_MARGIN:
        if tank < TANK_STORED:
            plans.append(_plan(
                solar_actuator,
                'pumping',
                'set_solar_allocation',
                'solar_surplus',
                (
                    f'Solar production is {solar:.0f} W and essential loads are {essential:.0f} W. '
                    f'The tank is at {tank:.0f}%, so the surplus goes to pumping and storage before the battery.'
                ),
                safe=False,
            ))
            plans.append(_plan(
                battery,
                'idle',
                'set_battery',
                'solar_surplus',
                'Solar surplus is going to storage first. The battery stays idle.',
                safe=False,
            ))
        else:
            plans.append(_plan(
                solar_actuator,
                'battery',
                'set_solar_allocation',
                'solar_surplus',
                (
                    f'Solar production is {solar:.0f} W and essential loads are {essential:.0f} W. '
                    f'The tank is at {tank:.0f}%, so the surplus goes to the battery.'
                ),
                safe=False,
            ))
            plans.append(_plan(
                battery,
                'charging',
                'charge_battery',
                'solar_surplus',
                'Storage has room to spare. Charge the battery with the solar surplus.',
                safe=False,
            ))
    return plans


def _plan(actuator, desired, action, rule, reason, safe):
    return {
        'actuator': actuator,
        'desired': desired,
        'action': action,
        'rule': rule,
        'reason': reason,
        'safe': safe,
    }


def _apply(plan, mode):
    actuator = Actuator.objects.select_for_update().get(pk=plan['actuator'].pk)
    previous = actuator.state
    desired = plan['desired']
    reason = plan['reason']
    action = plan['action']
    if desired is None or mode == 'assist' or (mode == 'smart' and not plan['safe']) or not actuator.authorized:
        new_state = previous
        action = 'alert'
        if desired is None:
            pass
        elif mode == 'assist':
            reason += ' Assist mode only alerts. The actuator was not changed.'
        elif mode == 'smart' and not plan['safe']:
            reason += ' Smart mode does not perform this action. The actuator was not changed.'
        else:
            reason += ' This actuator is not authorized. It was not changed.'
    else:
        new_state = desired
        if actuator.state != desired:
            actuator.state = desired
            actuator.save(update_fields=['state'])
            _sync(actuator)
    return ActuatorAction.objects.create(
        actuator=actuator,
        home=actuator.home,
        farm=actuator.farm,
        action=action,
        reason=reason,
        previous_state=previous,
        new_state=new_state,
        mode=mode,
        rule=plan['rule'],
    )


def _sync(actuator):
    if actuator.kind == Actuator.Kind.WATER_VALVE and actuator.home_id:
        actuator.home.water_valve_open = actuator.state == 'open'
        actuator.home.save(update_fields=['water_valve_open'])
    if actuator.kind == Actuator.Kind.IRRIGATION_PUMP and actuator.farm_id:
        actuator.farm.irrigation_systems.update(is_active=actuator.state == 'on')
    if actuator.kind == Actuator.Kind.NON_CRITICAL_LOADS and actuator.home_id:
        Appliance.objects.filter(home_id=actuator.home_id, kind__in=NON_CRITICAL).update(
            is_active=actuator.state == 'on',
        )
