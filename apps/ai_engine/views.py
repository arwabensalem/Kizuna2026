import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.ai_engine import services
from apps.ai_engine.datasets import CROP_TYPES, SOIL_TYPES
from apps.ai_engine.training import LABEL

TASK_ORDER = ('water', 'energy', 'farm_water', 'crop_stress', 'anomaly')


@login_required
@ensure_csrf_cookie
def board(request):
    report = services.load_report()
    tasks = []
    if report:
        stored = report.get('tasks') or {}
        for name in TASK_ORDER:
            if name in stored:
                tasks.append({'slug': name, **stored[name]})
    return render(request, 'ai/board.html', {
        'label': LABEL,
        'report': report,
        'tasks': tasks,
        'crops': CROP_TYPES,
        'soils': SOIL_TYPES,
    })


@require_POST
def water(request):
    return _predict(request, services.predict_water)


@require_POST
def energy(request):
    return _predict(request, services.predict_energy)


@require_POST
def farm_water(request):
    return _predict(request, services.predict_farm_water)


@require_POST
def crop_stress(request):
    return _predict(request, services.predict_crop_stress)


@require_POST
def anomaly(request):
    return _predict(request, services.detect_anomaly)


def _predict(request, handler):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=403)
    payload, error = _payload(request)
    if error:
        return error
    try:
        result = handler(payload)
    except services.PredictionError as exc:
        status = 503 if exc.missing else 400
        return JsonResponse({'detail': str(exc)}, status=status)
    return JsonResponse(result)


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
