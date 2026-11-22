"""Energy module: demand, solar, battery, and grid.

The 15% battery reserve, the 800 W pump, and the solar share lines (20% and
60% of the 3000 W home array) match the brain and the actuator rules.
This module does not charge or discharge a battery.
"""

from engine.agents.reading import number, show

BATTERY_RESERVE = 15
PUMP_WATTS = 800
HOME_SOLAR_WATTS = 3000
SOLAR_MEDIUM = 0.2
SOLAR_HIGH = 0.6


def assess(state):
    demand = number(state, ('consumption', 'home_electricity_watts'))
    home_solar = number(state, ('solar', 'home_watts'))
    farm_solar = number(state, ('solar', 'farm_watts'))
    home_battery = number(state, ('batteries', 'home_percent'))
    farm_battery = number(state, ('batteries', 'farm_percent'))
    grid = number(state, ('sensors', 'grid', 'grid_availability'))
    findings = [
        _named('energy demand', demand, 'W', 'Home electricity demand'),
        _solar(home_solar, farm_solar),
        _named('battery', home_battery, '%', 'Home battery'),
        _named('battery', farm_battery, '%', 'Farm battery'),
        _grid(grid),
    ]
    actions = _actions(demand, home_solar, farm_solar, home_battery, grid)
    return {
        'agent': 'energy',
        'status': _status(grid, home_battery),
        'findings': findings,
        'actions': actions,
    }


def _actions(demand, home_solar, farm_solar, home_battery, grid):
    if grid is None:
        return []
    actions = []
    if grid <= 0:
        actions.append({
            'id': 'shed_non_critical_loads',
            'action': 'Shed non-critical loads',
            'reason': 'Grid availability is 0. Keep critical loads first. The actuator rule does the same in an outage.',
            'blocks': [],
        })
        if home_battery is None:
            actions.append({
                'id': 'hold_battery',
                'action': 'Leave the battery where it is',
                'reason': 'The grid is down and the home battery percent is not in this state, so it is not discharged.',
                'blocks': [],
            })
        elif home_battery >= BATTERY_RESERVE:
            actions.append({
                'id': 'discharge_battery',
                'action': 'Discharge the battery for critical loads',
                'reason': (
                    f'The grid is down and the home battery is {show(home_battery, "%")}, '
                    f'at or above the {BATTERY_RESERVE}% reserve.'
                ),
                'blocks': [],
            })
        else:
            actions.append({
                'id': 'hold_battery',
                'action': 'Do not discharge below the reserve',
                'reason': (
                    f'The grid is down and the home battery is {show(home_battery, "%")}, '
                    f'below the {BATTERY_RESERVE}% reserve.'
                ),
                'blocks': [],
            })
        if farm_solar is None or farm_solar < PUMP_WATTS:
            shown = 'not in this state' if farm_solar is None else show(farm_solar, ' W')
            actions.append({
                'id': 'hold_pump_power',
                'action': 'Do not start the pump from a short supply',
                'reason': (
                    f'The grid is down and farm solar is {shown}. '
                    f'The pump is {PUMP_WATTS} W, so irrigation waits.'
                ),
                'blocks': ['start_irrigation'],
            })
    elif demand is not None and home_solar is not None and home_solar >= demand:
        actions.append({
            'id': 'charge_battery',
            'action': 'Charge the battery with the solar surplus',
            'reason': (
                f'Grid is up. Home solar is {show(home_solar, " W")} and demand is {show(demand, " W")}. '
                'The surplus can charge the battery.'
            ),
            'blocks': [],
        })
    return actions


def _status(grid, home_battery):
    if grid is None and home_battery is None:
        return 'unknown'
    if grid is not None and grid <= 0 and (home_battery is None or home_battery < BATTERY_RESERVE):
        return 'alert'
    if grid is not None and grid <= 0:
        return 'watch'
    if home_battery is not None and home_battery < BATTERY_RESERVE:
        return 'watch'
    return 'normal'


def _solar(home_solar, farm_solar):
    if home_solar is None:
        level = 'not in this state'
    else:
        share = home_solar / HOME_SOLAR_WATTS
        if share >= SOLAR_HIGH:
            level = 'high'
        elif share >= SOLAR_MEDIUM:
            level = 'medium'
        else:
            level = 'low'
        level = (
            f'{level} ({show(home_solar, " W")} of {HOME_SOLAR_WATTS} W, '
            f'lines at {int(SOLAR_MEDIUM * 100)}% and {int(SOLAR_HIGH * 100)}%)'
        )
    return {
        'topic': 'solar',
        'value': level if home_solar is not None else 'not in this state',
        'detail': f'Home solar {level}. Farm solar {show(farm_solar, " W")}.',
    }


def _grid(grid):
    if grid is None:
        value = 'not in this state'
        detail = 'Grid availability is not in this state.'
    elif grid <= 0:
        value = 'down'
        detail = 'Grid availability is 0.'
    else:
        value = 'up'
        detail = 'Grid availability is above 0.'
    return {'topic': 'grid', 'value': value, 'detail': detail}


def _named(topic, value, suffix, label):
    shown = show(value, suffix)
    if value is None:
        detail = f'{label} is not in this state.'
    else:
        detail = f'{label} is {shown}.'
    return {'topic': topic, 'value': shown, 'detail': detail}
