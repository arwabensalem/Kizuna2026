"""Community ranking by improvement against each row's own baseline.

The order is the change from the earlier stored hours to the later ones.
A row that uses more water can still rank higher. Rows with no earlier
reading are listed and not ranked.
"""

from apps.accounts.permissions import user_is_admin
from apps.farms.models import Farm
from apps.farms.simulation import simulate_farm
from apps.homes.models import Home
from apps.homes.simulation import simulate_home
from apps.resources.passport import hour_scores
from apps.simulation.models import SimulationStep
from apps.simulation.services import current_state
from apps.tunisia.places import GOVERNORATES, PROFILES

LABEL = (
    'Ranked by improvement against each row’s own baseline, not by who uses the least. '
    'Baseline is the earlier stored hours. Current is the later stored hours. '
    'Neighbourhoods are a simulated community: each one weights the same clock with its own profile.'
)

KINDS = {
    'homes': 'home',
    'farms': 'farm',
    'businesses': 'business',
    'neighborhoods': 'neighborhood',
}


def build_league(user, kind=None):
    current_state()
    steps = list(SimulationStep.objects.order_by('hour'))
    hours = [hour_scores(step.payload) for step in steps]
    rows = [
        _series_row('clock-home', 'home', 'Home A', 'Lafayette · Tunis', 'Shared simulation clock', [item['home'] for item in hours], _use(hours)),
        _series_row('clock-farm', 'farm', 'Farm B', 'Lafayette · Tunis', 'Shared simulation clock', [item['farm'] for item in hours], None),
        _series_row('clock-business', 'business', 'Workshop C', 'Lafayette · Tunis', 'Shared simulation clock', [item['business'] for item in hours], None),
    ]
    rows.extend(_neighborhoods(hours))
    rows.extend(_saved(user))
    if kind in KINDS.values():
        rows = [row for row in rows if row['kind'] == kind]
    return {
        'simulated': True,
        'label': LABEL,
        'period': _period(steps),
        'kind': kind,
        'rows': _place(rows),
    }


def _neighborhoods(hours):
    rows = []
    for name, (band, city, _lat, _lng, neighbourhood) in GOVERNORATES.items():
        profile = _weight(name, band)
        weight = sum(profile.values())
        series = []
        for hour in hours:
            signals = hour['signals']
            series.append(sum(profile[pillar] * signals[pillar] for pillar in profile) / weight)
        rows.append(_series_row(
            f'neighbourhood-{name}',
            'neighborhood',
            neighbourhood,
            f'{city} · {name}',
            'Simulated neighbourhood. The shared clock, weighted by this place’s own profile.',
            series,
            None,
        ))
    return rows


def _weight(name, band):
    """Same fixed ±4 spread as the Tunisia index, so one band is not 6 copies."""
    weighted = {}
    for pillar, value in PROFILES[band].items():
        seed = sum(ord(char) for char in f'{name}:{pillar}')
        weighted[pillar] = value + (seed % 9) - 4
    return weighted


def _saved(user):
    homes = Home.objects.all() if user_is_admin(user) else Home.objects.filter(owner=user)
    farms = Farm.objects.all() if user_is_admin(user) else Farm.objects.filter(owner=user)
    rows = []
    for home in homes.prefetch_related('appliances'):
        snapshot = simulate_home(home)
        rows.append(_unranked(
            f'home-{home.pk}', 'home', home.name, 'Registered home',
            'No earlier reading is stored, so this home is not ranked.',
            float(snapshot['resilience_score']),
        ))
    for farm in farms.prefetch_related('tanks', 'solar_units', 'irrigation_systems', 'farm_sensors'):
        snapshot = simulate_farm(farm)
        rows.append(_unranked(
            f'farm-{farm.pk}', 'farm', farm.name, farm.location or 'Registered farm',
            'No earlier reading is stored, so this farm is not ranked.',
            round(max(0.0, min(100.0, 100 - snapshot['crop_stress'])), 1),
        ))
    return rows


def _series_row(row_id, kind, name, place, source, values, water_l):
    baseline, current, resilience, improvement = _summary(values)
    return {
        'id': row_id,
        'kind': kind,
        'name': name,
        'place': place,
        'source': source,
        'ranked': improvement is not None,
        'baseline': baseline,
        'current': current,
        'improvement': improvement,
        'resilience': resilience,
        'water_l': water_l,
    }


def _unranked(row_id, kind, name, place, source, resilience):
    return {
        'id': row_id,
        'kind': kind,
        'name': name,
        'place': place,
        'source': source,
        'ranked': False,
        'baseline': None,
        'current': None,
        'improvement': None,
        'resilience': resilience,
        'water_l': None,
    }


def _summary(values):
    if not values:
        return None, None, None, None
    resilience = _round(sum(values) / len(values))
    if len(values) == 1:
        return resilience, resilience, resilience, 0.0
    mid = len(values) // 2
    baseline = _round(sum(values[:mid]) / mid)
    current = _round(sum(values[mid:]) / (len(values) - mid))
    if baseline == 0:
        return baseline, current, resilience, None
    return baseline, current, resilience, _round((current - baseline) / baseline * 100)


def _place(rows):
    ranked = [row for row in rows if row['improvement'] is not None]
    unranked = [row for row in rows if row['improvement'] is None]
    ranked.sort(key=lambda row: (-row['improvement'], row['name']))
    unranked.sort(key=lambda row: row['name'])
    placed = []
    for index, row in enumerate(ranked, start=1):
        placed.append({**row, 'rank': index})
    for row in unranked:
        placed.append({**row, 'rank': None})
    return placed


def _use(hours):
    return round(sum(item['home_use_l'] for item in hours), 1)


def _period(steps):
    if not steps:
        return 'No stored hour'
    return f"Hours {steps[0].hour}–{steps[-1].hour} · {steps[-1].scenario}"


def _round(value):
    return round(float(value), 1)
