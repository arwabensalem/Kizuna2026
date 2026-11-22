from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from apps.accounts.permissions import user_is_admin
from apps.brain.services import build_brain
from apps.farms.models import Farm
from apps.homes.models import Home


@login_required
@ensure_csrf_cookie
def board(request):
    homes, farms = _sites(request.user)
    home, farm = _selection(request, homes, farms)
    return render(request, 'brain/board.html', {
        'homes': homes,
        'farms': farms,
        'home': home,
        'farm': farm,
        'brain': build_brain(home, farm),
        'query': urlencode({
            'home': home.pk if home else '',
            'farm': farm.pk if farm else '',
        }),
    })


@login_required
@require_GET
def panels(request):
    homes, farms = _sites(request.user)
    home, farm = _selection(request, homes, farms)
    return render(request, 'brain/panels.html', {'brain': build_brain(home, farm)})


@require_GET
def state(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=403)
    homes, farms = _sites(request.user)
    home, farm = _selection(request, homes, farms)
    return JsonResponse(build_brain(home, farm))


def _sites(user):
    homes = Home.objects.all() if user_is_admin(user) else Home.objects.filter(owner=user)
    farms = Farm.objects.all() if user_is_admin(user) else Farm.objects.filter(owner=user)
    return homes.order_by('name'), farms.order_by('name')


def _selection(request, homes, farms):
    home = _pick(homes, request.GET.get('home'))
    farm = _pick(farms, request.GET.get('farm'))
    if home is None and farm is None and 'home' not in request.GET and 'farm' not in request.GET:
        home = homes.first()
        if home is None:
            farm = farms.first()
    return home, farm


def _pick(queryset, raw):
    if not raw:
        return None
    return get_object_or_404(queryset, pk=raw)
