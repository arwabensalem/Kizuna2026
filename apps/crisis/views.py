import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.crisis.day import build_crisis_day
from apps.crisis.demo_mode import build_demo
from apps.crisis.lab import LIMITS, SCENARIOS, LabError, clean_inputs, run_lab


@login_required
@ensure_csrf_cookie
def lab(request):
    return render(request, 'crisis/lab.html', {
        'scenarios': SCENARIOS,
        'limits': LIMITS,
        'start': SCENARIOS['HEATWAVE'],
    })


def hackathon_demo(request):
    return render(request, 'crisis/demo.html', {'demo': build_demo()})


@login_required
def crisis_day(request):
    return render(request, 'crisis/day.html', {'day': build_crisis_day()})


@require_GET
def crisis_day_state(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=403)
    return JsonResponse(build_crisis_day())


@require_POST
def simulate(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=403)
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Send JSON.'}, status=400)
    try:
        inputs = clean_inputs(payload)
    except LabError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    return JsonResponse(run_lab(inputs))
