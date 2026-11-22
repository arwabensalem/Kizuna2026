"""Figures for the final dashboard, read from the clock and the signed-in account.

Nothing here is invented. A blank means that record is not stored.
"""

from django.db.models import Sum

from apps.accounts.permissions import user_is_admin
from apps.ai_engine.models import AnomalyEvent
from apps.brain.services import build_brain
from apps.farms.models import Farm
from apps.farms.simulation import simulate_farm
from apps.homes.models import Home
from apps.homes.simulation import simulate_home
from apps.marketplace.network import hour_flows
from apps.resources.passport import hour_scores
from apps.simulation.models import SimulationStep
from apps.simulation.services import current_state
from apps.weather.models import WaterRecovery


def build_briefing(user):
    state = current_state()
    steps = list(SimulationStep.objects.order_by('-hour')[:2])
    latest = steps[0].payload if steps else state
    previous = steps[1].payload if len(steps) > 1 else None
    flows, _status, _totals = hour_flows(latest, previous)
    flows = sorted(flows, key=lambda item: item['quantity'], reverse=True)
    if not user_is_admin(user) and user.role == 'citizen':
        flows = [item for item in flows if _home_flow(item)]
    flows = flows[:5]
    scores = hour_scores(latest)
    home = _home(user)
    farm = _farm(user)
    home_snapshot = simulate_home(home) if home else None
    farm_snapshot = simulate_farm(farm) if farm else None
    brain = build_brain(home, farm)
    grid_on = latest['sensors']['grid']['grid_availability']['value'] > 0
    alerts = AnomalyEvent.objects.filter(status=AnomalyEvent.Status.OPEN)
    if not user_is_admin(user):
        alerts = alerts.filter(home__owner=user)
    recovered = WaterRecovery.objects.all()
    if not user_is_admin(user):
        recovered = recovered.filter(timeline__home__owner=user)
    recovered_l = recovered.aggregate(total=Sum('recovered_liters'))['total']
    return {
        'simulated': True,
        'hour': latest['hour'],
        'scenario': latest['scenario'],
        'when': latest.get('simulated_at', ''),
        'crisis_state': latest.get('crisis_state', 'none'),
        'grid_on': grid_on,
        'status': brain['status'],
        'water': {
            'home_percent': latest['tanks']['home_percent'],
            'farm_percent': latest['tanks']['farm_percent'],
        },
        'energy': {
            'home_battery': latest['batteries']['home_percent'],
            'farm_battery': latest['batteries']['farm_percent'],
            'grid': 'Up' if grid_on else 'Down',
        },
        'alerts': alerts.count(),
        'solar': {
            'home_w': latest['solar']['home_watts'],
            'farm_w': latest['solar']['farm_watts'],
        },
        'recovery_l': None if recovered_l is None else float(recovered_l),
        'resilience': round(scores['home'], 1),
        'pump': latest['pump']['farm'],
        'soil': latest['soil_moisture'],
        'flows': flows,
        'brain': {
            'text': brain['status']['text'],
            'detail': brain['status']['detail'],
            'lines': brain['current'][:4],
        },
        'home': None if home_snapshot is None else {
            'name': home.name,
            'energy_watts': home_snapshot['energy_watts'],
            'resilience': home_snapshot['resilience_score'],
        },
        'farm': None if farm_snapshot is None else {
            'name': farm.name,
            'soil_moisture': farm_snapshot['soil_moisture'],
            'crop_stress': farm_snapshot['crop_stress'],
        },
    }


def _home_flow(item):
    """Citizen flows stay on the home side of the shared hour."""
    ends = (item['source_label'], item['destination_label'])
    blob = ' '.join(ends)
    if 'Farm' in blob or 'Business' in blob:
        return False
    return not any(end.endswith((' B', ' C', ' D')) for end in ends)


def _home(user):
    homes = Home.objects.all() if user_is_admin(user) else Home.objects.filter(owner=user)
    return homes.prefetch_related('appliances__room', 'rooms').order_by('name').first()


def _farm(user):
    farms = Farm.objects.all() if user_is_admin(user) else Farm.objects.filter(owner=user)
    return farms.prefetch_related(
        'tanks', 'solar_units', 'irrigation_systems', 'farm_sensors', 'crops',
    ).order_by('name').first()
