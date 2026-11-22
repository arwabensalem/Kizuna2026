from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.access import OwnedDeleteView, OwnedUpdateView
from apps.accounts.models import User
from apps.accounts.permissions import role_required, user_is_admin
from apps.farms.forms import (
    CropForm,
    FarmCropFormSet,
    FarmForm,
    FarmSensorForm,
    FarmSolarForm,
    FarmTankForm,
    IrrigationSystemForm,
    main_crop,
)
from apps.farms.models import Crop, Farm, FarmSensor, FarmSolar, FarmTank, IrrigationSystem
from apps.farms.advisor import advise
from apps.farms.geo import farm_point, places_json
from apps.farms.simulation import simulate_farm


def farms_for(user):
    farms = Farm.objects.select_related('owner')
    if user_is_admin(user):
        return farms
    return farms.filter(owner=user)


def owned_farm(request, pk):
    return get_object_or_404(farms_for(request.user), pk=pk)


def _cancel(request, fallback):
    farm_id = request.GET.get('farm') or request.POST.get('farm')
    if farm_id and farms_for(request.user).filter(pk=farm_id).exists():
        return reverse('farms:detail', args=[farm_id])
    return fallback


class FarmChildUpdateView(OwnedUpdateView):
    owner_lookup = 'farm__owner'
    allowed_roles = (User.Role.FARMER,)
    template_name = 'farms/record_form.html'

    def get_success_url(self):
        return reverse('farms:detail', args=[self.object.farm_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_success_url()
        return context


class FarmChildDeleteView(OwnedDeleteView):
    owner_lookup = 'farm__owner'
    allowed_roles = (User.Role.FARMER,)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('farms:detail', args=[self.object.farm_id])


@role_required(User.Role.FARMER)
def farm_list(request):
    return render(request, 'farms/farm_list.html', {
        'farms': farms_for(request.user).prefetch_related('crops'),
    })


def _farm_form(request, farm=None):
    """Création et modification d'une ferme avec toutes ses cultures."""
    creating = farm is None
    instance = farm or Farm(owner=request.user)
    form = FarmForm(request.POST or None, instance=instance)
    # Anciennes intégrations qui n'envoient pas la liste des cultures : la ferme seule.
    with_crops = request.method != 'POST' or 'crops-TOTAL_FORMS' in request.POST
    formset = FarmCropFormSet(
        request.POST if request.method == 'POST' and with_crops else None,
        instance=instance,
        prefix='crops',
    ) if with_crops else None
    if formset is not None and request.method != 'POST' and not (instance.pk and instance.crops.exists()):
        # Première culture préremplie : la culture principale sur toute la ferme.
        formset.extra = 1
        if instance.pk:
            formset.initial_extra = [{'kind': instance.crop_type, 'area_m2': instance.area_m2}]
    if request.method == 'POST':
        form_ok = form.is_valid()
        if formset is not None:
            formset.farm_area = form.cleaned_data.get('area_m2') if form_ok else None
        crops_ok = formset is None or formset.is_valid()
        if form_ok and crops_ok:
            with transaction.atomic():
                saved = form.save(commit=False)
                if creating:
                    saved.owner = request.user
                saved.save()
                if formset is not None:
                    formset.instance = saved
                    formset.save()
                    kind = main_crop(saved.crops.all())
                    if kind and kind != saved.crop_type:
                        saved.crop_type = kind
                        saved.save(update_fields=['crop_type'])
            messages.success(request, 'Votre ferme est enregistrée.' if creating else 'Ferme mise à jour.')
            return redirect('farms:detail', pk=saved.pk)
    return render(request, 'farms/farm_form.html', {
        'form': form,
        'formset': formset,
        'farm': farm,
        'title': 'Ajouter une ferme' if creating else f'Modifier « {farm.name} »',
        'places': places_json(),
    })


@role_required(User.Role.FARMER)
def farm_create(request):
    return _farm_form(request)


@role_required(User.Role.FARMER)
def farm_edit(request, pk):
    return _farm_form(request, owned_farm(request, pk))


@role_required(User.Role.FARMER)
def farm_detail(request, pk):
    farm = owned_farm(request, pk)
    crops = list(farm.crops.all())
    farm_area = float(farm.area_m2 or 0)
    planted = sum(float(crop.area_m2) for crop in crops)
    for crop in crops:
        crop.share = round(100 * float(crop.area_m2) / farm_area, 1) if farm_area else 0
    point = farm_point(farm)
    return render(request, 'farms/farm_detail.html', {
        'farm': farm,
        'crops': crops,
        'planted_m2': round(planted),
        'planted_share': round(100 * planted / farm_area) if farm_area else 0,
        'free_m2': max(round(farm_area - planted), 0),
        'free_share': max(round(100 - 100 * planted / farm_area, 1), 0) if farm_area else 0,
        'point': point,
        'sensors': farm.farm_sensors.all(),
        'systems': farm.irrigation_systems.all(),
        'tanks': farm.tanks.all(),
        'solar_units': farm.solar_units.all(),
        'snapshot': simulate_farm(farm),
    })


class FarmDeleteView(OwnedDeleteView):
    model = Farm
    allowed_roles = (User.Role.FARMER,)
    success_url = reverse_lazy('farms:list')


def _record_list(request, queryset, template_rows, title, add_url, empty_note, headings):
    if not user_is_admin(request.user):
        queryset = queryset.filter(farm__owner=request.user)
    return render(request, 'farms/record_list.html', {
        'title': title,
        'add_url': add_url,
        'empty_note': empty_note,
        'headings': headings,
        'rows': [template_rows(item) for item in queryset],
    })


def _record_create(request, form_class, title, fallback):
    form = form_class(request.POST or None, user=request.user, initial={
        'farm': request.GET.get('farm'),
    })
    if request.method == 'POST' and form.is_valid():
        record = form.save()
        messages.success(request, 'C’est enregistré.')
        return redirect('farms:detail', pk=record.farm_id)
    return render(request, 'farms/record_form.html', {
        'form': form,
        'title': title,
        'cancel_url': _cancel(request, fallback),
    })


@role_required(User.Role.FARMER)
def crop_list(request):
    crops = Crop.objects.select_related('farm', 'farm__owner')
    return _record_list(
        request,
        crops,
        lambda crop: {
            'cells': [crop.farm.name, crop.name, crop.get_stage_display(), f'{crop.area_m2} m²'],
            'edit_url': reverse('farms:crop_edit', args=[crop.pk]),
            'delete_url': reverse('farms:crop_delete', args=[crop.pk]),
        },
        'Cultures',
        reverse('farms:crop_create'),
        'Aucune culture pour le moment.',
        ['Ferme', 'Culture', 'Stade', 'Surface'],
    )


@role_required(User.Role.FARMER)
def crop_create(request):
    return _record_create(request, CropForm, 'Ajouter une culture', reverse('farms:crops'))


class CropUpdateView(FarmChildUpdateView):
    model = Crop
    form_class = CropForm
    title = 'Modifier la culture'


class CropDeleteView(FarmChildDeleteView):
    model = Crop


@role_required(User.Role.FARMER)
def sensor_list(request):
    sensors = FarmSensor.objects.select_related('farm', 'farm__owner')
    return _record_list(
        request,
        sensors,
        lambda sensor: {
            'cells': [
                sensor.farm.name,
                sensor.display_name,
                sensor.unit,
                'Actif' if sensor.is_active else 'Inactif',
            ],
            'edit_url': reverse('farms:sensor_edit', args=[sensor.pk]),
            'delete_url': reverse('farms:sensor_delete', args=[sensor.pk]),
        },
        'Capteurs de la ferme',
        reverse('farms:sensor_create'),
        'Aucun capteur pour le moment.',
        ['Ferme', 'Capteur', 'Unité', 'État'],
    )


@role_required(User.Role.FARMER)
def sensor_create(request):
    return _record_create(request, FarmSensorForm, 'Ajouter un capteur', reverse('farms:sensors'))


class FarmSensorUpdateView(FarmChildUpdateView):
    model = FarmSensor
    form_class = FarmSensorForm
    title = 'Modifier le capteur'


class FarmSensorDeleteView(FarmChildDeleteView):
    model = FarmSensor


@role_required(User.Role.FARMER)
def irrigation_list(request):
    systems = IrrigationSystem.objects.select_related('farm', 'farm__owner')
    return _record_list(
        request,
        systems,
        lambda system: {
            'cells': [
                system.farm.name,
                system.name,
                system.get_method_display(),
                f'{system.flow_liters_per_hour} L/h',
                'En marche' if system.is_active else 'À l’arrêt',
            ],
            'edit_url': reverse('farms:irrigation_edit', args=[system.pk]),
            'delete_url': reverse('farms:irrigation_delete', args=[system.pk]),
        },
        'Irrigation',
        reverse('farms:irrigation_create'),
        'Aucun système d’irrigation pour le moment.',
        ['Ferme', 'Nom', 'Méthode', 'Débit', 'État'],
    )


@role_required(User.Role.FARMER)
def irrigation_create(request):
    return _record_create(
        request,
        IrrigationSystemForm,
        'Ajouter un système d’irrigation',
        reverse('farms:irrigation'),
    )


class IrrigationSystemUpdateView(FarmChildUpdateView):
    model = IrrigationSystem
    form_class = IrrigationSystemForm
    title = 'Modifier l’irrigation'


class IrrigationSystemDeleteView(FarmChildDeleteView):
    model = IrrigationSystem


@require_POST
@role_required(User.Role.FARMER)
def irrigation_toggle(request, pk):
    systems = IrrigationSystem.objects.select_related('farm')
    if not user_is_admin(request.user):
        systems = systems.filter(farm__owner=request.user)
    system = get_object_or_404(systems, pk=pk)
    system.is_active = not system.is_active
    system.save(update_fields=['is_active'])
    state = 'en marche' if system.is_active else 'à l’arrêt'
    messages.success(request, f'{system.name} est {state}.')
    return redirect(request.POST.get('next') or reverse('farms:detail', args=[system.farm_id]))


@role_required(User.Role.FARMER)
def tank_list(request):
    tanks = FarmTank.objects.select_related('farm', 'farm__owner')
    return _record_list(
        request,
        tanks,
        lambda tank: {
            'cells': [tank.farm.name, tank.name, f'{tank.capacity_liters} L'],
            'edit_url': reverse('farms:tank_edit', args=[tank.pk]),
            'delete_url': reverse('farms:tank_delete', args=[tank.pk]),
        },
        'Réservoirs',
        reverse('farms:tank_create'),
        'Aucun réservoir pour le moment.',
        ['Ferme', 'Nom', 'Capacité'],
    )


@role_required(User.Role.FARMER)
def tank_create(request):
    return _record_create(request, FarmTankForm, 'Ajouter un réservoir', reverse('farms:tanks'))


class FarmTankUpdateView(FarmChildUpdateView):
    model = FarmTank
    form_class = FarmTankForm
    title = 'Modifier le réservoir'


class FarmTankDeleteView(FarmChildDeleteView):
    model = FarmTank


@role_required(User.Role.FARMER)
def solar_list(request):
    units = FarmSolar.objects.select_related('farm', 'farm__owner')
    return _record_list(
        request,
        units,
        lambda unit: {
            'cells': [unit.farm.name, unit.name, f'{unit.capacity_watts} W'],
            'edit_url': reverse('farms:solar_edit', args=[unit.pk]),
            'delete_url': reverse('farms:solar_delete', args=[unit.pk]),
        },
        'Panneaux solaires',
        reverse('farms:solar_create'),
        'Aucun panneau solaire pour le moment.',
        ['Ferme', 'Nom', 'Capacité'],
    )


@role_required(User.Role.FARMER)
def solar_create(request):
    return _record_create(request, FarmSolarForm, 'Ajouter des panneaux solaires', reverse('farms:solar'))


class FarmSolarUpdateView(FarmChildUpdateView):
    model = FarmSolar
    form_class = FarmSolarForm
    title = 'Modifier les panneaux solaires'


class FarmSolarDeleteView(FarmChildDeleteView):
    model = FarmSolar


def _rain_forecast(farm):
    """Pluie prévue (mm) sur les prochaines heures du dernier scénario météo de la ferme."""
    timeline = farm.weather_timelines.order_by('-created_at').first()
    if not timeline:
        return 0.0
    hours = timeline.hours.filter(hour__gte=timeline.hour)
    return round(float(sum(item.rainfall_mm for item in hours)), 1)


def _number(raw, default, low=0, high=100):
    try:
        value = float(str(raw).replace(',', '.'))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


@role_required(User.Role.FARMER)
def farm_advice(request, pk):
    farm = owned_farm(request, pk)
    snapshot = simulate_farm(farm)
    default_shallow = float(snapshot['soil_moisture'])
    default_deep = min(default_shallow + 5, 100)
    default_rain = _rain_forecast(farm)
    shallow = _number(request.GET.get('sol20'), default_shallow)
    deep = _number(request.GET.get('sol40'), default_deep)
    rain = _number(request.GET.get('pluie'), default_rain, high=300)
    advice = advise(farm, shallow, deep, rain, now_hour=timezone.localtime().hour)
    return render(request, 'farms/advice.html', {
        'farm': farm,
        'advice': advice,
        'readings': {'sol20': shallow, 'sol40': deep, 'pluie': rain},
        'from_sensors': not request.GET,
    })


@role_required(User.Role.FARMER)
def advice_shortcut(request):
    """Menu « Quand arroser ? » : ouvre les conseils de la première ferme."""
    farm = farms_for(request.user).order_by('pk').first()
    if farm is None:
        messages.info(request, 'Décrivez d’abord votre ferme pour recevoir vos conseils d’arrosage.')
        return redirect('farms:create')
    return redirect('farms:advice', pk=farm.pk)
