from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.permissions import user_is_admin
from apps.actuators.engine import current_mode, ensure_actuators, run_rules
from apps.actuators.models import Actuator, ActuatorAction
from apps.farms.models import Farm
from apps.homes.models import Home
from apps.simulation.services import current_state


@login_required
def board(request):
    homes, farms = _sites(request.user)
    home, farm = _selection(request, homes, farms)
    actuators = list(ensure_actuators(home, farm).values()) if home or farm else []
    actuators.sort(key=lambda item: item.kind)
    last_ids = request.session.get('autopilot_last_ids', [])
    last_actions = _visible_actions(request.user).filter(pk__in=last_ids)
    return render(request, 'autopilot/board.html', {
        'homes': homes,
        'farms': farms,
        'home': home,
        'farm': farm,
        'clock': current_state(),
        'mode': current_mode(home, farm),
        'actuators': actuators,
        'last_actions': last_actions,
        'history': _history(home, farm),
        'errors': [],
        'posted': {},
    })


@require_POST
@login_required
def set_mode(request):
    home, farm = _posted_sites(request)
    mode = request.POST.get('mode', '')
    if home is None and farm is None:
        messages.error(request, 'Choose a home or a farm before setting the mode.')
        return redirect('actuators:board')
    if mode not in {'assist', 'smart', 'autopilot'}:
        messages.error(request, 'Choose Assist, Smart, or Autopilot.')
        return redirect(_board_url(home, farm))
    if home is not None:
        home.autonomy_mode = mode
        home.autopilot_enabled = mode != 'assist'
        home.save(update_fields=['autonomy_mode', 'autopilot_enabled'])
    if farm is not None:
        farm.autonomy_mode = mode
        farm.save(update_fields=['autonomy_mode'])
    messages.success(
        request,
        f'Mode is now {mode.upper()}. No actuator was changed.',
    )
    return redirect(_board_url(home, farm))


@require_POST
@login_required
def authorize(request):
    home, farm = _posted_sites(request)
    actuator = _owned_actuator(request, request.POST.get('actuator'))
    actuator.authorized = request.POST.get('authorized') == 'on'
    actuator.save(update_fields=['authorized'])
    word = 'authorized' if actuator.authorized else 'not authorized'
    messages.success(request, f'{actuator.get_kind_display()} is {word}. Its state was not changed.')
    return redirect(_board_url(home, farm))


@require_POST
@login_required
def run(request):
    home, farm = _posted_sites(request)
    if home is None and farm is None:
        messages.error(request, 'Choose a home or a farm before running the rules.')
        return redirect('actuators:board')
    situation, errors = _situation(request.POST)
    if errors:
        homes, farms = _sites(request.user)
        actuators = list(ensure_actuators(home, farm).values())
        actuators.sort(key=lambda item: item.kind)
        return render(request, 'autopilot/board.html', {
            'homes': homes,
            'farms': farms,
            'home': home,
            'farm': farm,
            'clock': current_state(),
            'mode': current_mode(home, farm),
            'actuators': actuators,
            'last_actions': [],
            'history': _history(home, farm),
            'errors': errors,
            'posted': request.POST,
        })
    actions = run_rules(home, farm, situation)
    request.session['autopilot_last_ids'] = [action.pk for action in actions]
    if actions:
        for action in actions:
            messages.success(
                request,
                f'{action.get_mode_display()} · {action.action} · {action.actuator.get_kind_display()} · {action.previous_state} → {action.new_state}. {action.reason}',
            )
    else:
        messages.success(request, 'No rule fired. No actuator was changed.')
    return redirect(_board_url(home, farm))


def _sites(user):
    homes = Home.objects.all() if user_is_admin(user) else Home.objects.filter(owner=user)
    farms = Farm.objects.all() if user_is_admin(user) else Farm.objects.filter(owner=user)
    return homes.order_by('name'), farms.order_by('name')


def _selection(request, homes, farms):
    home = _pick(homes, request.GET.get('home'))
    farm = _pick(farms, request.GET.get('farm'))
    if home is None and farm is None:
        home = homes.first()
        if home is None:
            farm = farms.first()
    return home, farm


def _posted_sites(request):
    homes, farms = _sites(request.user)
    return _pick(homes, request.POST.get('home')), _pick(farms, request.POST.get('farm'))


def _pick(queryset, raw):
    if not raw:
        return None
    return get_object_or_404(queryset, pk=raw)


def _owned_actuator(request, raw):
    homes, farms = _sites(request.user)
    actuator = get_object_or_404(Actuator, pk=raw)
    if actuator.home_id and homes.filter(pk=actuator.home_id).exists():
        return actuator
    if actuator.farm_id and farms.filter(pk=actuator.farm_id).exists():
        return actuator
    raise Http404


def _history(home, farm):
    actions = ActuatorAction.objects.select_related('actuator')
    if home is not None and farm is not None:
        return actions.filter(Q(home=home) | Q(farm=farm))[:40]
    if home is not None:
        return actions.filter(home=home)[:40]
    if farm is not None:
        return actions.filter(farm=farm)[:40]
    return actions.none()


def _visible_actions(user):
    homes, farms = _sites(user)
    return ActuatorAction.objects.select_related('actuator').filter(
        Q(home__in=homes) | Q(farm__in=farms)
    ).order_by('-created_at')


def _board_url(home, farm):
    query = []
    if home is not None:
        query.append(f'home={home.pk}')
    if farm is not None:
        query.append(f'farm={farm.pk}')
    url = reverse('actuators:board')
    if query:
        return url + '?' + '&'.join(query)
    return url


def _situation(post):
    errors = []

    def number(name, low, high):
        raw = post.get(name, '')
        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors.append(f'{name} must be a number.')
            return 0
        if value < low or value > high or value != value:
            errors.append(f'{name} must be between {low} and {high}.')
            return 0
        return value

    situation = {
        'critical_leak': post.get('critical_leak') == 'on',
        'rain_expected': post.get('rain_expected') == 'on',
        'grid_available': post.get('grid_available') == 'on',
        'crop_stress': number('crop_stress', 0, 100),
        'tank_percent': number('tank_percent', 0, 100),
        'solar_watts': number('solar_watts', 0, 50000),
        'essential_watts': number('essential_watts', 0, 50000),
        'battery_percent': number('battery_percent', 0, 100),
    }
    return situation, errors
