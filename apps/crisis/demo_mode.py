"""Hackathon demo. One fixed story, the same every time.

Household chapters use the anomaly rules. Farm, weather, and crisis chapters
use the crisis-lab series. The Tunisia score uses the fixed NORMAL governorate
profile. Nothing here writes the shared clock, a home, or an actuator.
"""

from types import SimpleNamespace

from apps.actuators.engine import STRESS_HIGH
from apps.ai_engine.detection import _energy_decision, _water_decision
from apps.ai_engine.models import AnomalyEvent
from apps.crisis.day import _brain, _driver, _drivers, _flows, _tunisia, build_crisis_day
from apps.crisis.lab import HOME_SOLAR_W, _initial, _run, crop_stress
from apps.resources.passport import hour_scores
from apps.tunisia.index import _mean_scores, _profile
from apps.tunisia.places import FEATURED_NEIGHBOURHOOD, GOVERNORATES, PILLARS

LABEL = (
    'Deterministic demo. The same 24 chapters play every time. '
    'Household chapters use the anomaly rules. Crisis chapters use the crisis-lab series. '
    'The Tunisia index is the fixed NORMAL profile, not the live clock and not a measurement. '
    'Nothing on this page calls a weather service or changes the shared simulation clock.'
)

CHAPTERS = (
    'ONE HOME',
    'LIVING DIGITAL TWIN',
    'NORMAL RESOURCE CONSUMPTION',
    'ABNORMAL WATER CONSUMPTION',
    'LEAK DETECTION',
    'AUTONOMOUS VALVE CLOSURE',
    'FARM SOIL STRESS',
    'SOLAR-POWERED IRRIGATION',
    'WEATHER PREDICTION',
    'RAIN PREPARATION MODE',
    'CRISIS DAY',
    'HEATWAVE',
    'GRID INSTABILITY',
    'PUMP INTERRUPTION',
    'CRISIS PROPAGATION',
    'KIZUNA ACTIVATION',
    'SOLAR → BATTERY → PUMP',
    'CROP PROTECTION',
    'RAIN',
    'WATER RECOVERY',
    'CRISIS CONTAINED',
    'ZOOM OUT TO NEIGHBORHOOD',
    'ZOOM OUT TO TUNISIA',
    'TUNISIA RESILIENCE SCORE',
)

FINALE_QUOTE = (
    'What if we could simulate a crisis before it happens — '
    'and make Tunisia respond before the crisis becomes reality?'
)

HOME = SimpleNamespace(
    residents=4,
    bathrooms=2,
    has_kitchen=True,
    has_garden=True,
    has_pool=False,
    area_m2=140,
)
VALVE_TEXT = (
    'Autopilot closed the water valve because this home has a critical water leak. '
    'The valve was open.'
)


def build_demo():
    day = build_crisis_day()
    frames = {frame['time']: frame for frame in day['beats']}
    morning = _household()
    solar = _solar_hour()
    atlas = _atlas()
    contained = frames['20:00']
    scores = _passport(contained, _clock_driver(20))
    events = []
    steps = []

    def add(chapter, **fields):
        event = fields.pop('event', None)
        if event:
            events.append(event)
        step = _blank(chapter, list(events))
        step.update(fields)
        steps.append(step)

    add(
        'ONE HOME',
        time='09:00',
        focus='twin',
        narration=(
            f"One simulated home. {HOME.residents} residents, {HOME.bathrooms} bathrooms, "
            f"a kitchen and a garden, {HOME.area_m2:.0f} m². "
            f"The tank starts at {morning['tank']}% from the crisis-lab starting stock."
        ),
        source='Household rules at 09:00. Not the shared clock.',
        **morning['panels'],
    )
    add(
        'LIVING DIGITAL TWIN',
        time='09:00',
        focus='twin',
        narration=(
            'The twin reads this same hour: tank, battery, solar, and the open valve. '
            'It is a simplified house, not a measured building.'
        ),
        source='Same 09:00 reading as the previous chapter.',
        **morning['panels'],
    )
    add(
        'NORMAL RESOURCE CONSUMPTION',
        time='09:00',
        focus='dashboard',
        narration=f"{morning['water']['summary']} {morning['energy']['summary']}",
        source='Anomaly rules. Observed water and energy are this home’s own baseline.',
        event={'time': '09:00', 'text': morning['water']['summary']},
        **morning['panels'],
    )
    add(
        'ABNORMAL WATER CONSUMPTION',
        time='09:10',
        focus='dashboard',
        narration=morning['critical']['summary'],
        source='Same baseline. Observed water is four times that baseline, and the tank is not filling.',
        event={'time': '09:10', 'text': morning['critical']['summary']},
        **morning['critical_panels'],
    )
    add(
        'LEAK DETECTION',
        time='09:12',
        focus='brain',
        narration=(
            'The household rule classifies this reading as critical abnormal consumption. '
            'The valve is still open. No forest is used: this home has no saved history.'
        ),
        source='Anomaly rules. Critical when the ratio is at least 3.5 and the tank is not filling.',
        event={'time': '09:12', 'text': morning['critical']['summary']},
        **morning['critical_panels'],
    )
    closed = dict(morning['critical_panels'])
    closed['twin'] = dict(closed['twin'], valve='closed')
    closed['dashboard'] = dict(closed['dashboard'], crisis='Valve closed')
    closed['flows'] = _valve_flows(morning)
    closed['brain'] = [
        line for line in closed['brain'] if line['label'] != 'Valve'
    ] + [{'label': 'Valve', 'value': 'Closed', 'note': VALVE_TEXT}]
    add(
        'AUTONOMOUS VALVE CLOSURE',
        time='09:13',
        focus='timeline',
        narration=VALVE_TEXT,
        source='Autopilot rule for a critical water leak. Logged here. The home record is not changed.',
        event={'time': '09:13', 'text': VALVE_TEXT},
        **closed,
    )
    soil = _day_chapter(
        'FARM SOIL STRESS',
        frames['14:20'],
        focus='twin',
        narration=_soil_line(frames['14:20']),
        source='Crisis Day 14:20, from the crisis-lab series.',
    )
    _append_new(events, frames['14:20'])
    soil['events'] = list(events)
    steps.append(soil)
    irrigated = _day_chapter(
        'SOLAR-POWERED IRRIGATION',
        solar['frame'],
        focus='network',
        narration=solar['narration'],
        source='One crisis-lab hour at 11:00. Farm grid off, KIZUNA on. Separate from Crisis Day.',
        time='11:00',
    )
    if solar['event']:
        events.append(solar['event'])
    irrigated['events'] = list(events)
    steps.append(irrigated)
    for title, stamp, focus, narration in (
        (
            'WEATHER PREDICTION',
            '15:00',
            'brain',
            'The series predicts rain at 18:00. The rules do not see that rain before 15:00.',
        ),
        (
            'RAIN PREPARATION MODE',
            '15:01',
            'brain',
            'Rain is in the forecast. Irrigation waits. Collection starts when the rain hour arrives.',
        ),
        (
            'CRISIS DAY',
            '10:00',
            'timeline',
            'Crisis Day is the fixed 10:00 to 20:00 series. It starts at 10:00 NORMAL. Earlier chapters do not edit it.',
        ),
        (
            'HEATWAVE',
            '12:00',
            'dashboard',
            'Heatwave hour on that series. Temperature and demand come from the fixed drivers.',
        ),
        (
            'GRID INSTABILITY',
            '14:00',
            'dashboard',
            'The farm grid drops on this hour. Home grid is still on. Stress is the driver for 14:00.',
        ),
        (
            'PUMP INTERRUPTION',
            '14:15',
            'network',
            'The pump has no grid power, and KIZUNA is not controlling yet, so the pump is off.',
        ),
        (
            'CRISIS PROPAGATION',
            '14:20',
            'timeline',
            'Heat, demand, grid, pumps, and crops are the propagation chain for this hour.',
        ),
        (
            'KIZUNA ACTIVATION',
            '14:25',
            'brain',
            'KIZUNA’s rules switch on at 14:25. Actions from here are the lab rules, and each one is listed.',
        ),
        (
            'SOLAR → BATTERY → PUMP',
            '14:26',
            'network',
            'Farm solar runs the pump. Surplus solar charges the battery. Irrigation is the lab’s 300 L hour.',
        ),
        (
            'CROP PROTECTION',
            '14:26',
            'twin',
            _crop_line(frames['14:26']),
        ),
        (
            'RAIN',
            '18:00',
            'twin',
            'Rain falls on this hour of the series. The roof capture is counted on the next chapter, when collection is open.',
        ),
        (
            'WATER RECOVERY',
            '18:01',
            'network',
            'Roof area times this hour’s rain times the lab capture rate, into the tanks.',
        ),
        (
            'CRISIS CONTAINED',
            '20:00',
            'dashboard',
            'The controlled run ends under the lab water, energy, and crop-stress lines.',
        ),
    ):
        chapter = _day_chapter(title, frames[stamp], focus=focus, narration=narration, source=f'Crisis Day {stamp}.')
        _append_new(events, frames[stamp])
        chapter['events'] = list(events)
        if stamp == '20:00':
            chapter['summary'] = day['summary']
        steps.append(chapter)

    closing = _day_chapter(
        'ZOOM OUT TO NEIGHBORHOOD',
        contained,
        focus='map',
        narration=(
            f"{FEATURED_NEIGHBOURHOOD}, Tunis. Home and farm scores use the passport rules on the 20:00 hour. "
            "The neighbourhood index is the fixed NORMAL profile for Tunis."
        ),
        source='Passport rules on the contained hour, plus the fixed Tunis profile.',
        scope='neighbourhood',
    )
    closing['events'] = list(events)
    closing['sites'] = scores
    steps.append(closing)

    country = _day_chapter(
        'ZOOM OUT TO TUNISIA',
        contained,
        focus='map',
        narration='Twenty-four governorates. Colour is the fixed NORMAL profile, including the fixed spread. No map tiles and no weather service.',
        source='Fixed NORMAL governorate profile. Not the live simulation clock.',
        scope='country',
    )
    country['events'] = list(events)
    steps.append(country)

    score_step = _day_chapter(
        'TUNISIA RESILIENCE SCORE',
        contained,
        focus='map',
        narration=(
            f"National index {atlas['national']['overall']}. "
            "Each pillar is the mean of that pillar across the 24 governorates. "
            "The index is the mean of those four pillars."
        ),
        source='The same mean the Tunisia map uses for a profile, without the live clock.',
        scope='score',
    )
    score_step['events'] = list(events)
    score_step['dashboard']['resilience'] = atlas['national']['overall']
    score_step['dashboard']['resilience_note'] = (
        'Mean of the four national pillars. Fixed NORMAL profile. Not a measurement.'
    )
    steps.append(score_step)

    if [step['title'] for step in steps] != list(CHAPTERS):
        raise RuntimeError('Demo chapters do not match the script.')
    return {
        'simulated': True,
        'label': LABEL,
        'steps': steps,
        'atlas': atlas,
        'finale': {
            'quote': FINALE_QUOTE,
            'headline': day['summary']['headline'],
            'summary': day['summary'],
        },
    }


def _household():
    driver = _driver(9, 28, 0.0, True, True, 22)
    stocks = _initial({'water': 70, 'soil': 22})
    tank = round(stocks['home_tank_l'] / 1500 * 100, 1)
    battery = round(stocks['home_battery_wh'] / 8000 * 100, 1)
    soil = stocks['soil']
    stress = crop_stress(soil, driver['temperature'], driver['humidity'], driver['rain_mm'])
    blank = _reading(9, 28, 0, 0, tank, tank)
    water_base = _water_decision(HOME, [], [], blank)['baseline']
    energy_base = _energy_decision(HOME, [], [], blank)['baseline']
    water = _water_decision(HOME, [], [], _reading(9, 28, water_base, energy_base, tank, tank))
    energy = _energy_decision(HOME, [], [], _reading(9, 28, water_base, energy_base, tank, tank))
    if water['type'] != AnomalyEvent.Type.NORMAL or energy['type'] != AnomalyEvent.Type.NORMAL:
        raise RuntimeError('The demo baseline reading was not classified normal.')
    critical_water = round(water['baseline'] * 4, 2)
    critical = _water_decision(
        HOME, [], [], _reading(9, 28, critical_water, energy_base, tank, tank),
    )
    if critical['type'] != AnomalyEvent.Type.CRITICAL:
        raise RuntimeError('The demo leak reading was not classified critical.')
    passport = _passport_from_parts(driver, tank, battery, soil, water['observed'])
    panels = _home_panels(
        driver, tank, battery, soil, stress, water, energy, passport, 'open', 'None',
    )
    critical_passport = _passport_from_parts(driver, tank, battery, soil, critical['observed'])
    critical_panels = _home_panels(
        driver, tank, battery, soil, stress, critical, energy, critical_passport, 'open',
        'Critical abnormal consumption',
    )
    return {
        'tank': tank,
        'water': water,
        'energy': energy,
        'critical': critical,
        'panels': panels,
        'critical_panels': critical_panels,
        'solar': driver['home_solar'],
        'stress': stress,
    }


def _home_panels(driver, tank, battery, soil, stress, water, energy, passport, valve, crisis):
    solar = driver['home_solar']
    flows = []
    if solar > 0:
        flows.append(_flow('Solar', 'Home', solar, 'W', 'Home array this hour.'))
    if solar > energy['observed']:
        flows.append(_flow('Solar', 'Battery', solar - energy['observed'], 'W', 'Solar left after the home load.'))
    flows.append(_flow('Supply', 'Home', water['observed'], 'L/h', 'Observed water this reading.'))
    return {
        'status': 'NORMAL' if crisis == 'None' else 'ALERT',
        'dashboard': {
            'water': f"{water['observed']:.1f} L/h",
            'water_note': f"Baseline {water['baseline']:.1f} L/h. Ratio {water['ratio']}.",
            'energy': f"{energy['observed']:.0f} W",
            'energy_note': f"Baseline {energy['baseline']:.0f} W.",
            'crisis': crisis,
            'solar': f"{solar:.0f} W",
            'resilience': passport['home'],
            'resilience_note': 'Passport home rule: tank and battery on this reading.',
        },
        'twin': _twin(driver, tank, battery, soil, 'off', valve),
        'brain': [
            {'label': 'Temperature', 'value': f"{driver['temperature']}°C"},
            {'label': 'Water', 'value': water['type'], 'note': water['summary']},
            {'label': 'Energy', 'value': energy['type'], 'note': energy['summary']},
            {'label': 'Solar', 'value': f"{solar:.0f} W"},
            {'label': 'Soil', 'value': f"{soil}%", 'note': f"Crop stress {stress}/100"},
            {'label': 'Valve', 'value': 'Open' if valve == 'open' else 'Closed'},
            {'label': 'KIZUNA', 'value': 'OFF'},
        ],
        'flows': [item for item in flows if item['quantity'] > 0],
        'propagation': [
            {'label': 'Home', 'on': True, 'value': crisis if crisis != 'None' else 'Normal'},
        ],
        'chart': {'crop_stress': stress, 'resilience': passport['home']},
    }


def _valve_flows(morning):
    solar = morning['solar']
    energy = morning['energy']['observed']
    limited = round(morning['critical']['observed'] / 4, 1)
    flows = []
    if solar > 0:
        flows.append(_flow('Solar', 'Home', solar, 'W', 'Home array this hour.'))
    if solar > energy:
        flows.append(_flow('Solar', 'Battery', round(solar - energy, 1), 'W', 'Solar left after the home load.'))
    flows.append(_flow(
        'Valve', 'Home', limited, 'L/h',
        'Valve closed. The brain limits home water to a quarter of demand.',
    ))
    return flows


def _solar_hour():
    driver = _driver(11, 36, 0.0, False, True, 40)
    stocks = _initial({'water': 70, 'soil': 22})
    out = _run([driver], stocks, True, _forecast, limit=1)
    hour = out['hours'][0]
    if hour['pump'] != 'solar':
        raise RuntimeError('The demo solar hour did not run the pump on solar.')
    extra = round(driver['demand_w'] - driver['reference_w'], 1)
    frame = {
        'time': '11:00',
        'title': 'SOLAR-POWERED IRRIGATION',
        'twin': {
            'temperature': driver['temperature'],
            'home_tank_percent': hour['home_tank_percent'],
            'farm_tank_percent': hour['farm_tank_percent'],
            'home_battery_percent': hour['home_battery_percent'],
            'farm_battery_percent': hour['farm_battery_percent'],
            'solar_w': driver['home_solar'],
            'farm_solar_w': driver['farm_solar'],
            'pump': hour['pump'],
            'soil': hour['soil'],
            'rain_mm': driver['rain_mm'],
        },
        'flows': _flows(hour, driver, hour, 0),
        'propagation': [
            {'label': 'Farm grid', 'on': True, 'value': 'Off'},
            {'label': 'Pump', 'on': True, 'value': hour['pump']},
            {'label': 'Irrigation', 'on': True, 'value': '300 L'},
        ],
        'brain': _brain(hour, driver, True, extra),
        'chart': {
            'crop_stress': hour['crop_stress'],
            'water_stress': hour['water_stress'],
            'energy_stress': hour['energy_stress'],
        },
        'tunisia': _tunisia(hour, driver, driver['home_solar'] / HOME_SOLAR_W if HOME_SOLAR_W else 0),
        'actions': [
            {'time': '11:00', 'text': event['reason']}
            for event in out['events']
        ],
    }
    reason = next((event['reason'] for event in out['events'] if event['action'].startswith('pump')), '')
    return {
        'frame': frame,
        'narration': (
            f"Farm grid is off and farm solar is {driver['farm_solar']:.0f} W, "
            f"above the 800 W pump. The lab runs the pump on solar and sends 300 L to irrigation. "
            f"Crop stress after that hour is {hour['crop_stress']}/100."
        ),
        'event': {'time': '11:00', 'text': reason} if reason else None,
    }


def _day_chapter(title, frame, focus, narration, source, time=None, scope='home'):
    twin = frame['twin']
    chart = frame['chart']
    tunis = frame['tunisia']
    pump = twin['pump']
    if frame.get('note'):
        narration = f"{narration} {frame['note']}"
    return {
        'title': title,
        'time': time or frame['time'],
        'focus': focus,
        'scope': scope,
        'narration': narration,
        'source': source,
        'status': frame['title'],
        'dashboard': {
            'water': f"{twin['home_tank_percent']}%",
            'water_note': f"Farm tank {twin['farm_tank_percent']}%.",
            'energy': f"{twin['home_battery_percent']}%",
            'energy_note': f"Farm battery {twin['farm_battery_percent']}%. Pump {pump}.",
            'crisis': frame['title'],
            'solar': f"{twin['solar_w']:.0f} W",
            'resilience': tunis['overall'],
            'resilience_note': tunis['note'],
        },
        'twin': _twin(
            {'temperature': twin['temperature'], 'home_solar': twin['solar_w'], 'rain_mm': twin['rain_mm']},
            twin['home_tank_percent'],
            twin['home_battery_percent'],
            twin['soil'],
            pump,
            'open',
        ),
        'brain': frame['brain'],
        'flows': [
            _flow(item['source'], item['destination'], item['quantity'], item['unit'], item['note'])
            for item in frame['flows']
        ],
        'propagation': frame['propagation'],
        'chart': {'crop_stress': chart['crop_stress'], 'resilience': tunis['overall']},
        'events': [],
    }


def _passport(frame, driver):
    twin = frame['twin']
    scored = hour_scores(_passport_payload(
        driver, twin['home_tank_percent'], twin['home_battery_percent'], twin['soil'], 0,
    ))
    return {
        'home': round(scored['home'], 1),
        'farm': round(scored['farm'], 1),
        'workshop': round(scored['business'], 1),
        'home_note': 'Passport home rule on the 20:00 tanks and battery.',
        'farm_note': 'Passport farm rule: 100 minus the crop-stress formula for this hour.',
        'workshop_note': 'Passport workshop share for this hour. Not a registered business.',
    }


def _passport_from_parts(driver, tank, battery, soil, water_l):
    scored = hour_scores(_passport_payload(driver, tank, battery, soil, water_l))
    return {'home': round(scored['home'], 1)}


def _passport_payload(driver, tank, battery, soil, water_l):
    grid = 1 if driver['home_grid'] else 0
    return {
        'hour': driver['clock'],
        'soil_moisture': soil,
        'tanks': {'home_percent': tank},
        'batteries': {'home_percent': battery},
        'solar': {'home_watts': driver['home_solar']},
        'consumption': {'home_water_liters_per_hour': water_l},
        'sensors': {
            'grid': {'grid_availability': {'value': grid}},
            'home': {'temperature': {'value': driver['temperature']}},
            'farm': {
                'temperature': {'value': driver['temperature']},
                'humidity': {'value': driver['humidity']},
                'rainfall': {'value': driver['rain_mm']},
            },
        },
    }


def _atlas():
    rows = []
    for name, (band, _city, _lat, _lng, _neighbourhood) in GOVERNORATES.items():
        scores = _profile(name, band, 'NORMAL')
        rows.append({
            'name': name,
            'water': scores['water'],
            'energy': scores['energy'],
            'agriculture': scores['agriculture'],
            'climate': scores['climate'],
            'overall': scores['overall'],
        })
    national = _mean_scores(rows)
    tunis = next(row for row in rows if row['name'] == 'Tunis')
    return {
        'governorates': rows,
        'national': {pillar: national[pillar] for pillar in PILLARS} | {'overall': national['overall']},
        'tunis': tunis,
        'neighbourhood': FEATURED_NEIGHBOURHOOD,
        'note': (
            'Fixed NORMAL profile for every governorate, including the fixed ±4 spread. '
            'Tunis is not mixed with the live clock on this page. Not a measurement.'
        ),
    }


def _blank(title, events):
    return {
        'title': title,
        'events': events,
        'scope': 'home',
        'summary': None,
    }


def _append_new(events, frame):
    seen = {item['text'] for item in events}
    for action in frame.get('actions') or []:
        if action['text'] not in seen:
            events.append({'time': action['time'], 'text': action['text']})
            seen.add(action['text'])


def _clock_driver(clock):
    return next(item for item in _drivers() if item['clock'] == clock)


def _twin(driver, tank, battery, soil, pump, valve):
    return {
        'temperature': driver['temperature'],
        'tank': tank,
        'battery': battery,
        'solar': driver['home_solar'],
        'soil': soil,
        'rain': driver['rain_mm'],
        'pump': pump,
        'valve': valve,
    }


def _flow(source, destination, quantity, unit, note):
    return {
        'source': source,
        'destination': destination,
        'quantity': round(float(quantity), 1),
        'unit': unit,
        'note': note,
    }


def _reading(hour, temperature, water, energy, tank, previous):
    return {
        'hour': hour,
        'temperature_c': temperature,
        'water_liters_per_hour': water,
        'energy_watts': energy,
        'tank_percent': tank,
        'tank_previous_percent': previous,
        'history_count': 0,
    }


def _forecast(rows):
    return [
        crop_stress(row['soil_moisture'], row['temperature'], row['humidity'], row['rainfall'])
        for row in rows
    ]


def _soil_line(frame):
    soil = frame['twin']['soil']
    stress = frame['chart']['crop_stress']
    return (
        f"Soil is {soil}%. Crop stress is {stress}/100 from the lab formula. "
        f"The high-stress line used by the lab is {STRESS_HIGH}."
    )


def _crop_line(frame):
    stress = frame['chart']['crop_stress']
    pump = frame['twin']['pump']
    return (
        f"Pump is {pump}. Crop stress this hour is {stress}/100. "
        f"The day counts an hour as protected when stress is under {STRESS_HIGH}. "
        "That count is on the contained card."
    )
