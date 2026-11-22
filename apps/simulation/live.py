"""Figures derived from one read of the shared clock.

Nothing here advances the clock. The series is stored hours. The reading is
the same payload scored, flowed, and described by the existing engines.
"""

from apps.brain.services import build_brain
from apps.dashboard.briefing import _farm, _home
from apps.marketplace.network import hour_flows
from apps.resources.passport import hour_scores
from apps.simulation.models import SimulationStep

SERIES_LIMIT = 36


def recent_series(limit=SERIES_LIMIT):
    steps = list(SimulationStep.objects.order_by('-hour')[:limit])
    rows = []
    for step in reversed(steps):
        payload = step.payload or {}
        tanks = payload.get('tanks') or {}
        batteries = payload.get('batteries') or {}
        solar = payload.get('solar') or {}
        rows.append({
            'hour': payload.get('hour', step.hour),
            'home_tank': tanks.get('home_percent'),
            'farm_tank': tanks.get('farm_percent'),
            'home_battery': batteries.get('home_percent'),
            'farm_battery': batteries.get('farm_percent'),
            'home_solar': solar.get('home_watts'),
            'farm_solar': solar.get('farm_watts'),
        })
    return rows


def reading_for(user, state):
    flows, _status, _totals = hour_flows(state, _previous(state['hour']))
    flows = sorted(flows, key=lambda item: item['quantity'], reverse=True)[:5]
    scores = hour_scores(state)
    home = farm = None
    if getattr(user, 'is_authenticated', False):
        home = _home(user)
        farm = _farm(user)
    brain = build_brain(home, farm)
    grid_on = state['sensors']['grid']['grid_availability']['value'] > 0
    return {
        'resilience': round(scores['home'], 1),
        'grid': 'Up' if grid_on else 'Down',
        'status': brain['status']['text'],
        'status_detail': brain['status']['detail'],
        'brain_detail': brain['status']['detail'],
        'lines': [
            {'label': line['label'], 'value': line['value']}
            for line in brain['current'][:4]
        ],
        'flows': [
            {
                'source_label': item['source_label'],
                'destination_label': item['destination_label'],
                'quantity': item['quantity'],
                'unit': item['unit'],
            }
            for item in flows
        ],
    }


def _previous(hour):
    if hour <= 0:
        return None
    step = SimulationStep.objects.filter(hour=hour - 1).first()
    return step.payload if step else None
