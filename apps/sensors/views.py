from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy

from apps.accounts.models import User
from apps.accounts.permissions import role_required, user_is_admin
from apps.accounts.access import OwnedDeleteView, OwnedUpdateView
from apps.sensors.forms import FarmSensorForm, HomeSensorForm
from apps.sensors.models import Sensor


def _rows(objects, edit_name, delete_name):
    return [
        {
            'cells': [sensor.place_name, sensor.name, sensor.get_kind_display(), sensor.unit],
            'edit_url': reverse(edit_name, args=[sensor.pk]),
            'delete_url': reverse(delete_name, args=[sensor.pk]),
        }
        for sensor in objects
    ]


def _visible_sensors(user, placement):
    sensors = Sensor.objects.select_related('home', 'farm', 'home__owner', 'farm__owner')
    if user_is_admin(user):
        if placement == 'home':
            return sensors.filter(home__isnull=False)
        return sensors.filter(farm__isnull=False)
    if placement == 'home':
        return sensors.filter(home__owner=user)
    return sensors.filter(farm__owner=user)


@role_required(User.Role.CITIZEN)
def home_sensor_list(request):
    form = HomeSensorForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Sensor saved.')
        return redirect('sensors:home')
    return render(request, 'manage/collection.html', {
        'title': 'Home sensors',
        'kicker': 'Citizen',
        'form': form,
        'form_title': 'Add a sensor',
        'empty_note': 'Add a home before you add a sensor.',
        'headings': ['Home', 'Name', 'Kind', 'Unit'],
        'rows': _rows(_visible_sensors(request.user, 'home'), 'sensors:edit', 'sensors:delete'),
    })


@role_required(User.Role.FARMER)
def farm_sensor_list(request):
    form = FarmSensorForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Sensor saved.')
        return redirect('sensors:farm')
    return render(request, 'manage/collection.html', {
        'title': 'Farm sensors',
        'kicker': 'Farmer',
        'form': form,
        'form_title': 'Add a sensor',
        'empty_note': 'Add a farm before you add a sensor.',
        'headings': ['Farm', 'Name', 'Kind', 'Unit'],
        'rows': _rows(_visible_sensors(request.user, 'farm'), 'sensors:edit', 'sensors:delete'),
    })


class SensorQueryMixin:
    def get_queryset(self):
        user = self.request.user
        sensors = Sensor.objects.select_related('home', 'farm')
        if user_is_admin(user):
            return sensors
        if user.role == User.Role.CITIZEN:
            return sensors.filter(home__owner=user)
        if user.role == User.Role.FARMER:
            return sensors.filter(farm__owner=user)
        return sensors.none()


class SensorUpdateView(SensorQueryMixin, OwnedUpdateView):
    model = Sensor
    allowed_roles = (User.Role.CITIZEN, User.Role.FARMER)
    title = 'Edit sensor'

    def get_form_class(self):
        sensor = self.get_object()
        return HomeSensorForm if sensor.home_id else FarmSensorForm

    def get_success_url(self):
        sensor = self.object
        if sensor.farm_id and not sensor.home_id:
            return reverse_lazy('sensors:farm')
        return reverse_lazy('sensors:home')


class SensorDeleteView(SensorQueryMixin, OwnedDeleteView):
    model = Sensor
    allowed_roles = (User.Role.CITIZEN, User.Role.FARMER)

    def get_success_url(self):
        if self.object.farm_id and not self.object.home_id:
            return reverse('sensors:farm')
        return reverse('sensors:home')
