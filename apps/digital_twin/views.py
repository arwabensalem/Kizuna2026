from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.digital_twin.state import build_twin_state
from apps.homes.views import homes_for


@login_required
def board(request):
    homes = homes_for(request.user).order_by('name')
    home = _selected(homes, request.GET.get('home'))
    return render(request, 'twin/board.html', {
        'homes': homes,
        'home': home,
    })


@require_GET
def twin_state(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=403)
    home = get_object_or_404(homes_for(request.user), pk=pk)
    return JsonResponse(build_twin_state(home))


def _selected(homes, raw):
    if raw:
        return get_object_or_404(homes, pk=raw)
    return homes.first()
