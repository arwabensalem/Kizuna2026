from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.access import OwnedDeleteView, OwnedUpdateView
from apps.accounts.models import User
from apps.accounts.permissions import role_required, user_is_admin
from apps.ai_engine.detection import evaluate_home, record_valve_choice
from apps.ai_engine.models import AnomalyEvent
from apps.homes.forms import ApplianceForm, HomeForm, RoomForm
from apps.homes.models import Appliance, Home, Room
from apps.homes.advice import home_advice
from apps.homes.bills import predict_bills
from apps.homes.simulation import simulate_home


APPLIANCE_DEFAULTS = {
    Appliance.Kind.AC: {'power': 1500, 'water': 0},
    Appliance.Kind.TV: {'power': 100, 'water': 0},
    Appliance.Kind.REFRIGERATOR: {'power': 150, 'water': 0},
    Appliance.Kind.WASHING_MACHINE: {'power': 500, 'water': 45},
    Appliance.Kind.DISHWASHER: {'power': 1800, 'water': 12},
    Appliance.Kind.WATER_HEATER: {'power': 2000, 'water': 8},
    Appliance.Kind.LIGHTS: {'power': 60, 'water': 0},
    Appliance.Kind.PUMP: {'power': 750, 'water': 20},
}


def homes_for(user):
    homes = Home.objects.select_related('owner')
    if user_is_admin(user):
        return homes
    return homes.filter(owner=user)


def owned_home(request, pk):
    return get_object_or_404(homes_for(request.user), pk=pk)


def appliance_rules():
    return {
        'waterKinds': list(Appliance.WATER_KINDS),
        'defaults': APPLIANCE_DEFAULTS,
    }


@role_required(User.Role.CITIZEN)
def home_list(request):
    return render(request, 'homes/home_list.html', {
        'homes': homes_for(request.user),
    })


@role_required(User.Role.CITIZEN)
def home_create(request):
    form = HomeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        home = form.save(commit=False)
        home.owner = request.user
        home.save()
        messages.success(request, 'Votre maison est enregistrée.')
        return redirect('homes:detail', pk=home.pk)
    return render(request, 'homes/home_form.html', {
        'form': form,
        'title': 'Ajouter une maison',
    })


@role_required(User.Role.CITIZEN)
def home_detail(request, pk):
    home = owned_home(request, pk)
    rooms = home.rooms.all()
    appliances = home.appliances.select_related('room')
    bills = predict_bills(home)
    return render(request, 'homes/home_detail.html', {
        'home': home,
        'rooms': rooms,
        'appliances': appliances,
        'snapshot': simulate_home(home),
        'bills': bills,
        'bills_list': [bills['electricity'], bills['water']],
        'advice': home_advice(home),
    })


class HomeUpdateView(OwnedUpdateView):
    model = Home
    form_class = HomeForm
    allowed_roles = (User.Role.CITIZEN,)
    template_name = 'homes/home_form.html'
    title = 'Modifier la maison'

    def get_success_url(self):
        return reverse('homes:detail', args=[self.object.pk])


class HomeDeleteView(OwnedDeleteView):
    model = Home
    allowed_roles = (User.Role.CITIZEN,)
    success_url = reverse_lazy('homes:list')


@role_required(User.Role.CITIZEN)
def room_create(request, pk):
    home = owned_home(request, pk)
    form = RoomForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        room = form.save(commit=False)
        room.home = home
        room.save()
        messages.success(request, 'La pièce est enregistrée.')
        return redirect('homes:detail', pk=home.pk)
    return render(request, 'homes/room_form.html', {
        'form': form,
        'home': home,
        'title': 'Ajouter une pièce',
    })


class RoomUpdateView(OwnedUpdateView):
    model = Room
    form_class = RoomForm
    owner_lookup = 'home__owner'
    allowed_roles = (User.Role.CITIZEN,)
    template_name = 'homes/room_form.html'
    title = 'Modifier la pièce'

    def get_success_url(self):
        return reverse('homes:detail', args=[self.object.home_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['home'] = self.object.home
        return context


class RoomDeleteView(OwnedDeleteView):
    model = Room
    owner_lookup = 'home__owner'
    allowed_roles = (User.Role.CITIZEN,)

    def get_success_url(self):
        return reverse('homes:detail', args=[self.object.home_id])


@role_required(User.Role.CITIZEN)
def appliance_list(request):
    appliances = Appliance.objects.select_related('home', 'room', 'home__owner')
    if not user_is_admin(request.user):
        appliances = appliances.filter(home__owner=request.user)
    return render(request, 'homes/appliance_list.html', {
        'appliances': appliances,
    })


@role_required(User.Role.CITIZEN)
def appliance_create(request):
    form = ApplianceForm(request.POST or None, user=request.user, initial={
        'home': request.GET.get('home'),
    })
    if request.method == 'POST' and form.is_valid():
        appliance = form.save()
        messages.success(request, 'L’appareil est enregistré.')
        return redirect('homes:detail', pk=appliance.home_id)
    return render(request, 'homes/appliance_form.html', {
        'form': form,
        'title': 'Ajouter un appareil',
        'rules': appliance_rules(),
    })


class ApplianceUpdateView(OwnedUpdateView):
    model = Appliance
    form_class = ApplianceForm
    owner_lookup = 'home__owner'
    allowed_roles = (User.Role.CITIZEN,)
    template_name = 'homes/appliance_form.html'
    title = 'Modifier l’appareil'

    def get_success_url(self):
        return reverse('homes:detail', args=[self.object.home_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['rules'] = appliance_rules()
        return context


class ApplianceDeleteView(OwnedDeleteView):
    model = Appliance
    owner_lookup = 'home__owner'
    allowed_roles = (User.Role.CITIZEN,)

    def get_success_url(self):
        return reverse('homes:detail', args=[self.object.home_id])


@require_POST
@role_required(User.Role.CITIZEN)
def appliance_toggle(request, pk):
    appliances = Appliance.objects.select_related('home')
    if not user_is_admin(request.user):
        appliances = appliances.filter(home__owner=request.user)
    appliance = get_object_or_404(appliances, pk=pk)
    appliance.is_active = not appliance.is_active
    appliance.save(update_fields=['is_active'])
    messages.success(request, f'{appliance.display_name} est {"allumé" if appliance.is_active else "éteint"}.')
    return redirect(request.POST.get('next') or reverse('homes:detail', args=[appliance.home_id]))


@role_required(User.Role.CITIZEN)
def anomaly_board(request, pk):
    home = owned_home(request, pk)
    snapshot = simulate_home(home)
    return render(request, 'homes/anomalies.html', _anomaly_context(home, snapshot))


@require_POST
@role_required(User.Role.CITIZEN)
def anomaly_evaluate(request, pk):
    home = owned_home(request, pk)
    reading, errors = _reading_from_post(request.POST)
    if errors:
        snapshot = simulate_home(home)
        context = _anomaly_context(home, snapshot)
        context['errors'] = errors
        context['posted'] = request.POST
        return render(request, 'homes/anomalies.html', context)
    result = evaluate_home(home, reading)
    if result['actions']:
        messages.success(request, result['actions'][0].summary)
    else:
        messages.success(request, 'Normal consumption for this home. No alert, and the valve was not changed.')
    return redirect('homes:anomalies', pk=home.pk)


@require_POST
@role_required(User.Role.CITIZEN)
def anomaly_autopilot(request, pk):
    home = owned_home(request, pk)
    home.autopilot_enabled = request.POST.get('enabled') == 'on'
    home.autonomy_mode = (
        Home.Autonomy.AUTOPILOT if home.autopilot_enabled else Home.Autonomy.ASSIST
    )
    home.save(update_fields=['autopilot_enabled', 'autonomy_mode'])
    if home.autopilot_enabled:
        messages.success(request, 'Autopilot is on. A critical water leak will close the valve and log that action.')
    else:
        messages.success(request, 'Autopilot is off. A critical water leak will only alert you. The valve was not changed.')
    return redirect('homes:anomalies', pk=home.pk)


@require_POST
@role_required(User.Role.CITIZEN)
def anomaly_valve(request, pk):
    home = owned_home(request, pk)
    action = record_valve_choice(home, request.POST.get('valve') == 'open')
    messages.success(request, action.summary)
    nxt = request.POST.get('next') or ''
    if nxt.startswith('/') and not nxt.startswith('//'):
        return redirect(nxt)
    return redirect('homes:anomalies', pk=home.pk)


@require_POST
@role_required(User.Role.CITIZEN)
def anomaly_acknowledge(request, pk, event_pk):
    home = owned_home(request, pk)
    event = get_object_or_404(AnomalyEvent, pk=event_pk, home=home)
    event.status = AnomalyEvent.Status.ACKNOWLEDGED
    event.save(update_fields=['status'])
    messages.success(request, 'Alert acknowledged. The water valve was not changed.')
    return redirect('homes:anomalies', pk=home.pk)


def _anomaly_context(home, snapshot):
    return {
        'home': home,
        'snapshot': snapshot,
        'hour': timezone.localtime().hour,
        'events': home.anomaly_events.all()[:30],
        'actions': home.automatic_actions.all()[:30],
        'errors': [],
        'posted': {},
    }


def _reading_from_post(post):
    errors = []

    def number(name, low, high, whole=False):
        raw = post.get(name, '')
        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors.append(f'{name} must be a number.')
            return 0
        if value < low or value > high or value != value:
            errors.append(f'{name} must be between {low} and {high}.')
            return 0
        if whole and int(value) != value:
            errors.append(f'{name} must be a whole number.')
            return 0
        return int(value) if whole else value

    reading = {
        'water_liters_per_hour': number('water_liters_per_hour', 0, 5000),
        'energy_watts': number('energy_watts', 0, 50000),
        'temperature_c': number('temperature_c', -5, 55),
        'hour': number('hour', 0, 23, whole=True),
        'tank_percent': number('tank_percent', 0, 100),
        'tank_previous_percent': number('tank_previous_percent', 0, 100),
    }
    return reading, errors


@role_required(User.Role.CITIZEN)
def bills_shortcut(request):
    """Menu « Factures et conseils » : ouvre la première maison, ou propose d'en créer une."""
    home = homes_for(request.user).order_by('pk').first()
    if home is None:
        messages.info(request, 'Décrivez d’abord votre maison pour voir vos factures prédites.')
        return redirect('homes:create')
    return redirect(reverse('homes:detail', args=[home.pk]) + '#kz-bills-title')
