"""Climate module: heatwave, drought, rainfall, and the named scenario.

A heatwave is the HEATWAVE or COMBINED_CRISIS scenario, or a home temperature
at or above 35°C, which is the crisis-lab heat line. Drought is only the
DROUGHT or COMBINED_CRISIS scenario, not a guess from one dry hour.
Rainfall is the stored millimetres. This module does not call a weather service.
"""

from engine.agents.reading import number, show, text

HOT = 35
HEAT_SCENARIOS = {'HEATWAVE', 'COMBINED_CRISIS'}
DRY_SCENARIOS = {'DROUGHT', 'COMBINED_CRISIS'}
RAIN_SCENARIOS = {'HEAVY_RAIN'}


def assess(state):
    scenario = text(state, ('scenario',))
    temperature = number(state, ('sensors', 'home', 'temperature'))
    rain = number(state, ('sensors', 'farm', 'rainfall'))
    heat = _heat(scenario, temperature)
    dry = _drought(scenario)
    findings = [
        heat,
        dry,
        _rain(rain, scenario),
        _scenario(scenario),
    ]
    actions = []
    if (rain is not None and rain > 0) or scenario in RAIN_SCENARIOS:
        amount = show(rain, ' mm') if rain is not None else 'not in this state'
        actions.append({
            'id': 'suspend_irrigation',
            'action': 'Suspend irrigation',
            'reason': (
                f'Rainfall is {amount}'
                + (f' and the scenario is {scenario}.' if scenario in RAIN_SCENARIOS else '.')
                + ' Irrigation waits, and rain can be collected.'
            ),
            'blocks': ['start_irrigation'],
        })
        actions.append({
            'id': 'collect_rain',
            'action': 'Collect rainwater',
            'reason': 'Rain is on this state. Roof capture is the recovery path already used by the crisis day.',
            'blocks': [],
        })
    if dry['value'] == 'drought scenario':
        actions.append({
            'id': 'hold_water',
            'action': 'Hold non-essential water use',
            'reason': f'The scenario is {scenario}. The simulation series withholds rainfall in that scenario.',
            'blocks': [],
        })
    status = 'unknown'
    if scenario is not None or temperature is not None or rain is not None:
        status = 'normal'
    if heat['value'] in {'heatwave scenario', 'hot'} or dry['value'] == 'drought scenario':
        status = 'watch'
    if scenario == 'COMBINED_CRISIS':
        status = 'alert'
    return {
        'agent': 'climate',
        'status': status,
        'findings': findings,
        'actions': actions,
    }


def _heat(scenario, temperature):
    if scenario in HEAT_SCENARIOS:
        value = 'heatwave scenario'
        detail = f'The scenario is {scenario}. Home temperature is {show(temperature, "°C")}.'
    elif temperature is not None and temperature >= HOT:
        value = 'hot'
        named = scenario or 'not in this state'
        detail = (
            f'Home temperature is {show(temperature, "°C")}, at or above the {HOT}°C heat line. '
            f'The scenario is {named}.'
        )
    elif temperature is None and scenario is None:
        value = 'not in this state'
        detail = 'Scenario and home temperature are not in this state, so heat is not judged.'
    else:
        value = 'no heatwave'
        detail = (
            f'Home temperature is {show(temperature, "°C")}. '
            f'The {HOT}°C heat line is not crossed, and the scenario is {scenario or "not in this state"}.'
        )
    return {'topic': 'heatwave', 'value': value, 'detail': detail}


def _drought(scenario):
    if scenario is None:
        return {
            'topic': 'drought',
            'value': 'not in this state',
            'detail': 'No scenario was provided, so drought is not inferred from one hour.',
        }
    if scenario in DRY_SCENARIOS:
        return {
            'topic': 'drought',
            'value': 'drought scenario',
            'detail': f'The scenario is {scenario}.',
        }
    return {
        'topic': 'drought',
        'value': 'not a drought scenario',
        'detail': f'The scenario is {scenario}, which is not DROUGHT or COMBINED_CRISIS.',
    }


def _rain(rain, scenario):
    if rain is None and scenario not in RAIN_SCENARIOS:
        value = 'not in this state'
        detail = 'Rainfall is not in this state.'
    elif rain is None:
        value = scenario
        detail = f'The scenario is {scenario} and the rainfall amount is not in this state.'
    elif rain > 0:
        value = show(rain, ' mm')
        detail = f'Rainfall is {value}.'
    else:
        value = '0 mm'
        detail = 'Rainfall is 0 mm on this state. That alone is not a drought.'
    return {'topic': 'rainfall', 'value': value, 'detail': detail}


def _scenario(scenario):
    if scenario is None:
        return {
            'topic': 'weather scenarios',
            'value': 'not in this state',
            'detail': 'No scenario name was provided.',
        }
    return {
        'topic': 'weather scenarios',
        'value': scenario,
        'detail': f'The named scenario is {scenario}.',
    }
