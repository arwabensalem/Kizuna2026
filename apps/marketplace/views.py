from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from apps.marketplace.network import LABEL, NetworkError, build_network


@login_required
@ensure_csrf_cookie
def network_board(request):
    return render(request, 'network/board.html', {'label': LABEL})


@require_GET
def network_state(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=403)
    try:
        return JsonResponse(build_network(request.GET.get('hour')))
    except NetworkError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
