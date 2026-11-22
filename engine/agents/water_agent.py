"""Water module: demand, leaks, and availability.

Thresholds are the same lines the brain and the actuator rules already use:
15% contained, 25% available, 60% medium. A missing reading is reported as
missing. This module does not change a valve or a tank.
"""

from engine.agents.reading import flag, number, show

TANK_CONTAINED = 15
TANK_AVAILABLE = 25
TANK_MEDIUM = 60


def assess(state):
    demand = number(state, ('consumption', 'home_water_liters_per_hour'))
    home = number(state, ('tanks', 'home_percent'))
    farm = number(state, ('tanks', 'farm_percent'))
    leak = flag(state, 'critical_leak')
    findings = [
        _demand(demand),
        _leak(leak),
        _tank('Home tank', home),
        _tank('Farm tank', farm),
    ]
    actions = []
    if leak:
        actions.append({
            'id': 'close_valve',
            'action': 'Close the water valve',
            'reason': 'A critical leak flag is in this state. Close the valve. The actuator rule uses the same flag.',
            'blocks': ['start_irrigation'],
        })
    if home is not None and home < TANK_AVAILABLE:
        actions.append({
            'id': 'hold_water',
            'action': 'Hold non-essential water use',
            'reason': (
                f'Home tank is {show(home, "%")}, below the {TANK_AVAILABLE}% available line. '
                'Do not start irrigation from this tank.'
            ),
            'blocks': ['start_irrigation'],
        })
    return {
        'agent': 'water',
        'status': _status(leak, home),
        'findings': findings,
        'actions': actions,
    }


def _demand(liters):
    if liters is None:
        detail = 'Home water demand is not in this state.'
    else:
        detail = f'Home water demand is {show(liters, " L/h")} on this state.'
    return {'topic': 'water demand', 'value': show(liters, ' L/h'), 'detail': detail}


def _leak(leak):
    if leak is None:
        return {
            'topic': 'leaks',
            'value': 'not in this state',
            'detail': 'No leak flag was provided. This is not a claim that the pipes are sound.',
        }
    if leak:
        return {
            'topic': 'leaks',
            'value': 'critical leak',
            'detail': 'The state marks a critical leak.',
        }
    return {
        'topic': 'leaks',
        'value': 'no leak flag',
        'detail': 'The leak flag in this state is off.',
    }


def _tank(name, percent):
    if percent is None:
        return {
            'topic': 'water availability',
            'value': f'{name} not in this state',
            'detail': f'{name} percent is not in this state.',
        }
    if percent < TANK_CONTAINED:
        line = f'below the {TANK_CONTAINED}% contained line'
    elif percent < TANK_AVAILABLE:
        line = f'below the {TANK_AVAILABLE}% available line'
    elif percent < TANK_MEDIUM:
        line = f'between the {TANK_AVAILABLE}% available line and the {TANK_MEDIUM}% medium line'
    else:
        line = f'at or above the {TANK_MEDIUM}% medium line'
    return {
        'topic': 'water availability',
        'value': f'{name} {show(percent, "%")}',
        'detail': f'{name} is {show(percent, "%")}, {line}.',
    }


def _status(leak, home):
    if leak:
        return 'alert'
    if home is None:
        return 'unknown'
    if home < TANK_CONTAINED:
        return 'alert'
    if home < TANK_AVAILABLE:
        return 'watch'
    return 'normal'
