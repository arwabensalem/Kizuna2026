"""KIZUNA Resilience Index for the Tunisia map.

Governorate figures are a demo profile plus the current simulation scenario.
Tunis then takes half of that profile and half of the shared simulation clock.
Nothing here is a census, a survey, or a weather service.
"""

from apps.accounts.permissions import user_is_admin
from apps.farms.models import Farm
from apps.homes.models import Home
from apps.simulation import engine
from apps.simulation.services import current_state
from apps.tunisia.places import (
    COUNTRY,
    FEATURED,
    FEATURED_NEIGHBOURHOOD,
    GOVERNORATES,
    PILLARS,
    PROFILES,
    ZOOMS,
)

LABEL = (
    'Simulated demo. Governorate scores are a fixed profile for the current scenario, '
    'not a national dataset and not a measurement. Tunis also uses the shared simulation clock. '
    'This is not a resilience ranking of real places.'
)
BOUNDARY_NOTE = (
    'Governorate boundaries: geoBoundaries 2017, derived from OpenStreetMap (ODbL). '
    'The boundaries are geographic. The colours are the simulated index.'
)

# Added to the demo profile. South and the interior feel a dry scenario more.
SCENARIO_SHIFT = {
    'NORMAL': {},
    'HEATWAVE': {'water': -8, 'energy': -4, 'agriculture': -10, 'climate': -16},
    'DROUGHT': {'water': -20, 'energy': 0, 'agriculture': -14, 'climate': -6},
    'POWER_OUTAGE': {'water': 0, 'energy': -26, 'agriculture': 0, 'climate': 0},
    'HEAVY_RAIN': {'water': 10, 'energy': -8, 'agriculture': 4, 'climate': -4},
    'COMBINED_CRISIS': {'water': -18, 'energy': -22, 'agriculture': -16, 'climate': -14},
}
BAND_EXTRA = {
    'HEATWAVE': {'south': {'climate': -8, 'water': -6}, 'interior': {'agriculture': -4}},
    'DROUGHT': {'south': {'water': -8}, 'interior': {'water': -4, 'agriculture': -6}},
    'HEAVY_RAIN': {'coast_north': {'water': 6}, 'coast_central': {'water': 4}, 'south': {'water': -6}},
    'POWER_OUTAGE': {'coast_north': {'energy': -4}},
    'COMBINED_CRISIS': {'south': {'water': -6, 'climate': -4}},
}

WORKSHOP_SOLAR_W = 5000
WORKSHOP_DAY_W = 1500
WORKSHOP_NIGHT_W = 150


def build_tunisia(user):
    state = current_state()
    scenario = state['scenario']
    clock = _clock_pillars(state)
    governorates = []
    for name, (band, city, lat, lng, neighbourhood) in GOVERNORATES.items():
        profile = _profile(name, band, scenario)
        featured = name == FEATURED
        scores = _mix(profile, clock) if featured else profile
        governorates.append(_governorate(
            name, band, city, lat, lng, neighbourhood, scores, featured, state,
        ))
    governorates.sort(key=lambda item: item['name'])
    national = _mean_scores(item['scores'] for item in governorates)
    return {
        'simulated': True,
        'label': LABEL,
        'boundary_note': BOUNDARY_NOTE,
        'scenario': scenario,
        'hour': state['hour'],
        'simulated_at': state['simulated_at'],
        'country': {
            'id': 'tunisia',
            'level': 'country',
            'name': COUNTRY['name'],
            'lat': COUNTRY['lat'],
            'lng': COUNTRY['lng'],
            'zoom': COUNTRY['zoom'],
            'scores': national,
            'index': national['overall'],
        },
        'governorates': governorates,
        'focus': _focus(),
        'registered': _registered(user),
        'rules': _rules(),
    }


def _profile(name, band, scenario):
    base = dict(PROFILES[band])
    shift = SCENARIO_SHIFT.get(scenario, {})
    extra = BAND_EXTRA.get(scenario, {}).get(band, {})
    scores = {}
    for pillar in PILLARS:
        wobble = _spread(name, pillar)
        scores[pillar] = _clamp(base[pillar] + shift.get(pillar, 0) + extra.get(pillar, 0) + wobble)
    scores['overall'] = _overall(scores)
    return scores


def _spread(name, pillar):
    """A fixed ±4 so two governorates in one band are not copies. Not local data."""
    seed = sum(ord(char) for char in f'{name}:{pillar}')
    return (seed % 9) - 4


def _clock_pillars(state):
    grid_on = state['sensors']['grid']['grid_availability']['value'] > 0
    temperature = state['sensors']['home']['temperature']['value']
    water = (state['tanks']['home_percent'] + state['tanks']['farm_percent']) / 2
    batteries = (state['batteries']['home_percent'] + state['batteries']['farm_percent']) / 2
    energy = batteries if not grid_on else batteries * 0.5 + 50
    return {
        'water': _clamp(water),
        'energy': _clamp(energy),
        'agriculture': _clamp(state['soil_moisture']),
        'climate': _clamp(100 - abs(temperature - 24) * 4),
    }


def _mix(profile, clock):
    scores = {pillar: _clamp((profile[pillar] + clock[pillar]) / 2) for pillar in PILLARS}
    scores['overall'] = _overall(scores)
    return scores


def _governorate(name, band, city, lat, lng, neighbourhood, scores, featured, state):
    key = _slug(name)
    city_id = f'city:{key}'
    neighbourhood_id = f'neighbourhood:{key}'
    nodes = _live_nodes(state) if featured else _demo_nodes(key, name, lat, lng, scores)
    return {
        'id': f'governorate:{key}',
        'level': 'governorate',
        'name': name,
        'band': band,
        'featured': featured,
        'lat': lat,
        'lng': lng,
        'zoom': ZOOMS['governorate'],
        'scores': scores,
        'note': (
            'Half the demo coastal profile, half the shared simulation clock.'
            if featured else
            'Demo profile for this scenario. Not a local measurement.'
        ),
        'city': {
            'id': city_id,
            'level': 'city',
            'name': city,
            'governorate': name,
            'lat': lat,
            'lng': lng,
            'zoom': ZOOMS['city'],
            'scores': scores,
            'note': f'Same simulated score as {name}. Cities are not scored on their own.',
            'neighbourhood': {
                'id': neighbourhood_id,
                'level': 'neighborhood',
                'name': neighbourhood,
                'city': city,
                'governorate': name,
                'lat': lat,
                'lng': lng,
                'zoom': ZOOMS['neighborhood'],
                'scores': scores,
                'live': featured,
                'note': (
                    'Demo neighbourhood that holds the shared simulation clock.'
                    if featured else
                    'Demo neighbourhood at the city centre. Not a surveyed boundary.'
                ),
                'nodes': nodes,
            },
        },
    }


def _live_nodes(state):
    lat, lng = GOVERNORATES[FEATURED][2], GOVERNORATES[FEATURED][3]
    grid_on = state['sensors']['grid']['grid_availability']['value'] > 0
    home_energy = _site_energy(state['batteries']['home_percent'], grid_on)
    farm_energy = _site_energy(state['batteries']['farm_percent'], grid_on)
    return [
        _node(
            'node:home-a', 'Home A', 'home', lat, lng, True,
            {'water': _clamp(state['tanks']['home_percent']), 'energy': home_energy},
            f"Shared clock. Water is the home tank ({state['tanks']['home_percent']}%). "
            f"Energy is the home battery"
            + (' with the grid up.' if grid_on else ' during the outage.'),
        ),
        _node(
            'node:farm-b', 'Farm B', 'farm', lat - 0.008, lng + 0.008, True,
            {
                'water': _clamp(state['tanks']['farm_percent']),
                'energy': farm_energy,
                'agriculture': _clamp(state['soil_moisture']),
            },
            f"Shared clock. Agriculture is the soil moisture ({state['soil_moisture']}%), not a yield.",
        ),
        _node(
            'node:business-c', 'Workshop C', 'business', lat + 0.006, lng - 0.007, True,
            {'energy': _workshop_energy(state, grid_on)},
            'Synthetic workshop from the resource network, under the same sun as Home A.',
        ),
    ]


def _demo_nodes(key, governorate, lat, lng, scores):
    return [
        _node(
            f'node:{key}:home', f'{governorate} home', 'home', lat + 0.006, lng + 0.004, False,
            {'water': scores['water'], 'energy': scores['energy']},
            'Demo home. Copies the governorate water and energy profile.',
        ),
        _node(
            f'node:{key}:farm', f'{governorate} farm', 'farm', lat - 0.008, lng + 0.008, False,
            {'water': scores['water'], 'agriculture': scores['agriculture']},
            'Demo farm. Copies the governorate water and agriculture profile.',
        ),
        _node(
            f'node:{key}:business', f'{governorate} workshop', 'business', lat + 0.004, lng - 0.008, False,
            {'energy': scores['energy']},
            'Demo workshop. Copies the governorate energy profile.',
        ),
    ]


def _node(node_id, name, kind, lat, lng, live, parts, note):
    scores = dict(parts)
    scores['overall'] = _overall_of(parts.values())
    return {
        'id': node_id,
        'level': 'node',
        'name': name,
        'kind': kind,
        'lat': round(lat, 4),
        'lng': round(lng, 4),
        'zoom': ZOOMS['node'],
        'live': live,
        'scores': scores,
        'note': note,
    }


def _site_energy(battery, grid_on):
    if grid_on:
        return _clamp(battery * 0.5 + 50)
    return _clamp(battery)


def _workshop_energy(state, grid_on):
    clock = state['hour'] % 24
    load = WORKSHOP_DAY_W if 8 <= clock < 18 else WORKSHOP_NIGHT_W
    solar = WORKSHOP_SOLAR_W * state['solar']['home_watts'] / engine.HOME_SOLAR_WATTS
    cover = 100 * min(1.0, solar / load)
    if grid_on:
        return _clamp(max(cover, 55))
    return _clamp(cover)


def _registered(user):
    if user_is_admin(user):
        homes = Home.objects.all()
        farms = Farm.objects.all()
    else:
        homes = Home.objects.filter(owner=user)
        farms = Farm.objects.filter(owner=user)
    placed = []
    unplaced = []
    for home in homes:
        _place(placed, unplaced, f'home-{home.pk}', home.name, 'home', home.latitude, home.longitude)
    for farm in farms:
        _place(placed, unplaced, f'farm-{farm.pk}', farm.name, 'farm', farm.latitude, farm.longitude)
    return {'placed': placed, 'unplaced': unplaced}


def _place(placed, unplaced, key, name, kind, latitude, longitude):
    row = {'id': f'registered:{key}', 'name': name, 'kind': kind}
    if latitude is None or longitude is None:
        row['note'] = 'No coordinates, so this site is not on the map.'
        unplaced.append(row)
        return
    row.update({
        'lat': float(latitude),
        'lng': float(longitude),
        'level': 'site',
        'zoom': ZOOMS['node'],
        'note': 'Registered site. The simulation clock is not a meter for this address, so it has no resilience score.',
    })
    placed.append(row)


def _focus():
    return {
        'governorate': f'governorate:{_slug(FEATURED)}',
        'city': f'city:{_slug(FEATURED)}',
        'neighbourhood': f'neighbourhood:{_slug(FEATURED)}',
        'node': 'node:home-a',
        'neighbourhood_name': FEATURED_NEIGHBOURHOOD,
    }


def _rules():
    return [
        'Overall resilience is the mean of the pillars that place has.',
        'Each national pillar is the mean of that pillar across the 24 governorates. The national index is the mean of those four pillars.',
        'A fixed ±4 spread keeps governorates in the same band from looking identical. It is not local data.',
        'Demo homes, farms, and businesses outside Lafayette copy their governorate profile.',
        'Registered sites are shown only for the signed-in account. They are not given a simulated score.',
        BOUNDARY_NOTE,
    ]


def _mean_scores(rows):
    rows = list(rows)
    scores = {pillar: _clamp(sum(row[pillar] for row in rows) / len(rows)) for pillar in PILLARS}
    scores['overall'] = _overall(scores)
    return scores


def _overall(scores):
    return _overall_of(scores[pillar] for pillar in PILLARS)


def _overall_of(values):
    values = list(values)
    return _clamp(sum(values) / len(values))


def _clamp(value):
    return round(max(0.0, min(100.0, value)), 1)


def _slug(name):
    return name.lower().replace(' ', '-')
