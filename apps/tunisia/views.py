from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from apps.tunisia.index import LABEL, build_tunisia


@login_required
@ensure_csrf_cookie
def board(request):
    return render(request, 'tunisia/map.html', {
        'label': LABEL,
        'boundaries': static('data/tunisia-governorates.geojson'),
    })


@require_GET
def state(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=403)
    return JsonResponse(build_tunisia(request.user))
