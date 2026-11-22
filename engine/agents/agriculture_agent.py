"""Agriculture module: soil, irrigation, and crop stress.

Crop stress uses the crisis-lab formula: distance from 45% moisture, heat
above 32°C, dry air below 40% humidity, and rainfall. Stress at or above 55
is the same high line the actuator rules use. A missing input leaves the
stress blank instead of filling it in. This module does not run a pump.
"""

from engine.agents.reading import number, show, text

IDEAL_MOISTURE = 45
SOIL_DRY = 40
STRESS_HIGH = 55
TANK_AVAILABLE = 25


def assess(state):
    soil = number(state, ('soil_moisture',))
    temperature = number(state, ('sensors', 'farm', 'temperature'))
    humidity = number(state, ('sensors', 'farm', 'humidity'))
    rain = number(state, ('sensors', 'farm', 'rainfall'))
    tank = number(state, ('tanks', 'farm_percent'))
    if tank is None:
        tank = number(state, ('tanks', 'home_percent'))
    pump = text(state, ('pump', 'farm'))
    stress = _stress(soil, temperature, humidity, rain)
    findings = [
        _soil(soil),
        _irrigation(pump, rain),
        _stress_finding(stress, soil, temperature, humidity, rain),
    ]
    return {
        'agent': 'agriculture',
        'status': _status(soil, stress),
        'findings': findings,
        'actions': _actions(stress, rain, tank, pump),
    }


def _stress(soil, temperature, humidity, rain):
    if None in (soil, temperature, humidity, rain):
        return None
    value = (
        abs(soil - IDEAL_MOISTURE) * 1.5
        + max(temperature - 32, 0) * 2
        + max(40 - humidity, 0) * 0.3
        - rain * 1.2
    )
    return round(min(100.0, max(0.0, value)), 1)


def _actions(stress, rain, tank, pump):
    actions = []
    raining = rain is not None and rain > 0
    if raining:
        actions.append({
            'id': 'suspend_irrigation',
            'action': 'Suspend irrigation',
            'reason': f'Rainfall is {show(rain, " mm")}. Irrigation stays off while rain is on this state.',
            'blocks': ['start_irrigation'],
        })
    if stress is None:
        return actions
    if stress < STRESS_HIGH:
        if pump == 'on':
            actions.append({
                'id': 'stop_irrigation',
                'action': 'Stop irrigation',
                'reason': (
                    f'Crop stress is {show(stress)}, below the {STRESS_HIGH} line, and the pump is on.'
                ),
                'blocks': [],
            })
        return actions
    if raining:
        actions.append({
            'id': 'note_stress_in_rain',
            'action': 'Leave irrigation off despite crop stress',
            'reason': (
                f'Crop stress is {show(stress)}, at or above {STRESS_HIGH}, and rainfall is {show(rain, " mm")}. '
                'Irrigation stays off.'
            ),
            'blocks': ['start_irrigation'],
        })
        return actions
    if tank is None:
        actions.append({
            'id': 'alert_irrigation',
            'action': 'Do not start irrigation',
            'reason': (
                f'Crop stress is {show(stress)}, at or above {STRESS_HIGH}, and no tank percent is in this state.'
            ),
            'blocks': ['start_irrigation'],
        })
        return actions
    if tank < TANK_AVAILABLE:
        actions.append({
            'id': 'alert_irrigation',
            'action': 'Do not start irrigation',
            'reason': (
                f'Crop stress is {show(stress)} and the tank is {show(tank, "%")}, '
                f'below the {TANK_AVAILABLE}% available line.'
            ),
            'blocks': ['start_irrigation'],
        })
        return actions
    actions.append({
        'id': 'start_irrigation',
        'action': 'Start irrigation',
        'reason': (
            f'Crop stress is {show(stress)}, at or above {STRESS_HIGH}, the tank is {show(tank, "%")}, '
            'and rainfall is 0.'
        ),
        'blocks': [],
    })
    return actions


def _status(soil, stress):
    if soil is None and stress is None:
        return 'unknown'
    if stress is not None and stress >= STRESS_HIGH:
        return 'alert'
    if soil is not None and soil < SOIL_DRY:
        return 'watch'
    return 'normal'


def _soil(soil):
    if soil is None:
        detail = 'Soil moisture is not in this state.'
        value = 'not in this state'
    elif soil < SOIL_DRY:
        value = show(soil, '%')
        detail = f'Soil moisture is {value}, below the {SOIL_DRY}% dry line. Ideal moisture in the formula is {IDEAL_MOISTURE}%.'
    else:
        value = show(soil, '%')
        detail = f'Soil moisture is {value}. The dry line is {SOIL_DRY}% and the formula ideal is {IDEAL_MOISTURE}%.'
    return {'topic': 'soil', 'value': value, 'detail': detail}


def _irrigation(pump, rain):
    if pump is None and rain is None:
        detail = 'Pump state and rainfall are not in this state.'
        value = 'not in this state'
    else:
        pump_text = pump if pump is not None else 'not in this state'
        value = f'pump {pump_text}'
        detail = f'Farm pump is {pump_text}. Rainfall is {show(rain, " mm")}.'
    return {'topic': 'irrigation', 'value': value, 'detail': detail}


def _stress_finding(stress, soil, temperature, humidity, rain):
    if stress is None:
        missing = [
            name for name, value in (
                ('soil', soil), ('temperature', temperature), ('humidity', humidity), ('rainfall', rain),
            ) if value is None
        ]
        detail = (
            'Crop stress was not calculated. Missing '
            + ', '.join(missing)
            + '. The formula is not run on a partial reading.'
        )
        value = 'not calculated'
    else:
        value = show(stress)
        line = 'at or above' if stress >= STRESS_HIGH else 'below'
        detail = (
            f'Crop stress is {value}, {line} the {STRESS_HIGH} line. '
            f'Formula inputs: soil {show(soil, "%")}, temperature {show(temperature, "°C")}, '
            f'humidity {show(humidity, "%")}, rainfall {show(rain, " mm")}.'
        )
    return {'topic': 'crop stress', 'value': value, 'detail': detail}
