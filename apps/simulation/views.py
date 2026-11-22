import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.simulation import live, services
from apps.simulation.engine import SCENARIOS


@login_required
@ensure_csrf_cookie
def board(request):
    state = services.current_state()
    return render(request, 'simulation/board.html', {
        'state': state,
        'scenarios': SCENARIOS,
    })


@require_GET
def state(request):
    """One read of the shared clock, plus the readings the live pages paint.

    This does not advance the clock. Play on a page posts to the advance
    endpoint; every open page polls this one.
    """
    payload = services.current_state()
    body = dict(payload)
    body['series'] = live.recent_series()
    body['reading'] = live.reading_for(request.user, payload)
    return JsonResponse(body)


@require_POST
def advance(request):
    denied = _login(request)
    if denied:
        return denied
    payload, error = _payload(request)
    if error:
        return error
    try:
        updated = services.advance_simulation(
            steps=payload.get('steps', 1),
            scenario=payload.get('scenario') or None,
        )
    except services.SimulationError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    return JsonResponse(updated)


@require_POST
def reset(request):
    denied = _login(request)
    if denied:
        return denied
    payload, error = _payload(request)
    if error:
        return error
    try:
        updated = services.reset_simulation(
            seed=payload.get('seed', None),
            scenario=payload.get('scenario') or None,
        )
    except services.SimulationError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    return JsonResponse(updated)


def _login(request):
    if request.user.is_authenticated:
        return None
    return JsonResponse({'detail': 'Authentication required.'}, status=403)


def _payload(request):
    if request.content_type == 'application/json':
        if not request.body:
            return {}, None
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return None, JsonResponse({'detail': 'Send JSON.'}, status=400)
        if not isinstance(data, dict):
            return None, JsonResponse({'detail': 'Send a JSON object.'}, status=400)
        return data, None
    return request.POST, None
