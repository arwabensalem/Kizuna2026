from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.permissions import user_is_admin
from apps.farms.models import Farm
from apps.homes.models import Home
from apps.weather.models import CollectionSystem, WeatherTimeline
from apps.weather.scenarios import SCENARIOS
from apps.weather.services import (
    advance_timeline,
    describe,
    ensure_collection,
    recovered_label,
    scenario_choices,
    start_timeline,
)


@login_required
def board(request):
    homes, farms = _sites(request.user)
    home, farm = _selection(request, homes, farms)
    return render(request, 'weather/board.html', _context(request, homes, farms, home, farm))


@require_POST
@login_required
def save_collection(request):
    home, farm = _posted_sites(request)
    if home is None and farm is None:
        messages.error(request, 'Choose a home or a farm before saving the collection system.')
        return redirect('weather:board')
    collection = ensure_collection(home, farm)
    cleaned, errors = _collection_form(request.POST)
    if errors:
        homes, farms = _sites(request.user)
        context = _context(request, homes, farms, home, farm)
        context['errors'] = errors
        context['posted'] = request.POST
        return render(request, 'weather/board.html', context)
    for field, value in cleaned.items():
        setattr(collection, field, value)
    if collection.tank_liters > collection.tank_capacity_liters:
        messages.error(request, 'The tank level cannot be higher than its capacity. Nothing was saved.')
        return redirect(_board_url(home, farm))
    collection.save()
    messages.success(
        request,
        f'Collection settings saved. The tank is at {collection.tank_liters:.1f} L. No weather was applied.',
    )
    return redirect(_board_url(home, farm))


@require_POST
@login_required
def authorize(request):
    home, farm = _posted_sites(request)
    collection = _owned_collection(request, request.POST.get('collection'))
    collection.authorized = request.POST.get('authorized') == 'on'
    if not collection.authorized:
        collection.prepared = False
    collection.save(update_fields=['authorized', 'prepared'])
    if collection.authorized:
        messages.success(request, 'Collection system is authorized. The tank was not changed.')
    else:
        messages.success(
            request,
            'Collection system is not authorized. It will not take in rain. The tank was not changed.',
        )
    return redirect(_board_url(home, farm))


@require_POST
@login_required
def start(request):
    home, farm = _posted_sites(request)
    if home is None and farm is None:
        messages.error(request, 'Choose a home or a farm before starting a scenario.')
        return redirect('weather:board')
    scenario = request.POST.get('scenario', '')
    if scenario not in SCENARIOS:
        messages.error(request, 'Choose one of the simulated scenarios.')
        return redirect(_board_url(home, farm))
    _timeline, actions, recovery = start_timeline(home, farm, scenario)
    _remember(request, actions, recovery)
    messages.success(request, f'{SCENARIOS[scenario]["label"]} is running. These figures are simulated.')
    return redirect(_board_url(home, farm))


@require_POST
@login_required
def advance(request):
    home, farm = _posted_sites(request)
    timeline = _owned_timeline(request, request.POST.get('timeline'))
    before = timeline.hour
    timeline, actions, recovery = advance_timeline(timeline)
    if timeline.hour == before:
        messages.success(request, 'The simulated timeline is at its last hour. The tank was not changed.')
    elif not actions:
        messages.success(
            request,
            f'Hour {timeline.hour} of the simulated timeline. No rain this hour. The tank was not changed.',
        )
    _remember(request, actions, recovery)
    return redirect(_board_url(home, farm))


def _context(request, homes, farms, home, farm):
    collection = ensure_collection(home, farm) if home or farm else None
    timeline = _latest(home, farm)
    hours = list(timeline.hours.all()) if timeline else []
    actions = list(timeline.actions.all()) if timeline else []
    last_ids = request.session.get('weather_last_action_ids', [])
    last_actions = [action for action in actions if action.pk in last_ids]
    this_hour = None
    run_total = Decimal('0.0')
    if timeline is not None:
        this_hour = timeline.recoveries.filter(hour=timeline.hour).order_by('-created_at').first()
        run_total = timeline.recoveries.aggregate(total=Sum('recovered_liters'))['total'] or Decimal('0.0')
    recovered = this_hour.recovered_liters if this_hour else Decimal('0.0')
    return {
        'homes': homes,
        'farms': farms,
        'home': home,
        'farm': farm,
        'collection': collection,
        'timeline': timeline,
        'hours': hours,
        'actions': actions,
        'preparation': [action for action in actions if action.action != 'collect_rainwater'],
        'last_actions': last_actions,
        'status': describe(timeline) if timeline else 'Choose a simulated scenario to build a timeline.',
        'recovered_text': recovered_label(recovered),
        'run_total': f'{run_total:.1f}',
        'scenarios': SCENARIOS,
        'scenario_choices': scenario_choices(),
        'errors': [],
        'posted': {},
        'system_state': _system_state(collection),
        'can_advance': bool(hours) and timeline.hour < hours[-1].hour,
    }


def _remember(request, actions, recovery):
    request.session['weather_last_action_ids'] = [action.pk for action in actions]
    if recovery is not None:
        messages.success(request, recovered_label(recovery.recovered_liters))
    for action in actions:
        messages.success(
            request,
            f'{action.mode} · {action.action} · {action.actuator} · {action.previous_state} → {action.new_state}. {action.reason}',
        )


def _system_state(collection):
    if collection is None:
        return 'idle'
    if not collection.authorized:
        return 'not authorized'
    if collection.prepared:
        return 'prepared'
    if collection.ready:
        return 'ready'
    return 'authorized'


def _latest(home, farm):
    if home is None and farm is None:
        return None
    timelines = WeatherTimeline.objects.all()
    if home is not None:
        timelines = timelines.filter(home=home)
    else:
        timelines = timelines.filter(home__isnull=True)
    if farm is not None:
        timelines = timelines.filter(farm=farm)
    else:
        timelines = timelines.filter(farm__isnull=True)
    return timelines.first()


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


def _posted_sites(request):
    homes, farms = _sites(request.user)
    return _pick(homes, request.POST.get('home')), _pick(farms, request.POST.get('farm'))


def _pick(queryset, raw):
    if not raw:
        return None
    return get_object_or_404(queryset, pk=raw)


def _owned_collection(request, raw):
    homes, farms = _sites(request.user)
    collection = get_object_or_404(CollectionSystem, pk=raw)
    if collection.home_id and homes.filter(pk=collection.home_id).exists():
        return collection
    if collection.farm_id and farms.filter(pk=collection.farm_id).exists():
        return collection
    raise Http404


def _owned_timeline(request, raw):
    homes, farms = _sites(request.user)
    timeline = get_object_or_404(WeatherTimeline, pk=raw)
    if timeline.home_id and homes.filter(pk=timeline.home_id).exists():
        return timeline
    if timeline.farm_id and farms.filter(pk=timeline.farm_id).exists():
        return timeline
    raise Http404


def _board_url(home, farm):
    query = []
    if home is not None:
        query.append(f'home={home.pk}')
    if farm is not None:
        query.append(f'farm={farm.pk}')
    url = reverse('weather:board')
    if query:
        return url + '?' + '&'.join(query)
    return url


def _collection_form(post):
    errors = []

    def decimal(name, low, high):
        try:
            value = Decimal(post.get(name, ''))
        except (InvalidOperation, TypeError):
            errors.append(f'{name} must be a number.')
            return Decimal('0')
        if value < low or value > high:
            errors.append(f'{name} must be between {low} and {high}.')
            return Decimal('0')
        return value

    try:
        capacity = int(post.get('tank_capacity_liters', ''))
    except (TypeError, ValueError):
        errors.append('tank_capacity_liters must be a whole number.')
        capacity = 0
    else:
        if capacity < 100 or capacity > 100000:
            errors.append('tank_capacity_liters must be between 100 and 100000.')
    cleaned = {
        'roof_area_m2': decimal('roof_area_m2', Decimal('1'), Decimal('500')).quantize(Decimal('0.1')),
        'capture_share': decimal('capture_share', Decimal('0'), Decimal('1')).quantize(Decimal('0.01')),
        'tank_capacity_liters': capacity,
        'tank_liters': decimal('tank_liters', Decimal('0'), Decimal('100000')).quantize(Decimal('0.1')),
    }
    return cleaned, errors
