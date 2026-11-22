from django.core.exceptions import ValidationError

from apps.accounts.forms import BootstrapModelForm
from apps.accounts.permissions import user_is_admin
from apps.farms.models import Farm
from apps.homes.models import Home
from apps.sensors.models import Sensor


class HomeSensorForm(BootstrapModelForm):
    needs_user = True

    class Meta:
        model = Sensor
        fields = ('home', 'name', 'kind', 'unit')

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        homes = Home.objects.all() if user_is_admin(user) else Home.objects.filter(owner=user)
        self.fields['home'].queryset = homes

    def clean_home(self):
        home = self.cleaned_data['home']
        if not user_is_admin(self.user) and home.owner_id != self.user.id:
            raise ValidationError('Choose one of your homes.')
        return home

    def save(self, commit=True):
        sensor = super().save(commit=False)
        sensor.farm = None
        if commit:
            sensor.save()
        return sensor


class FarmSensorForm(BootstrapModelForm):
    needs_user = True

    class Meta:
        model = Sensor
        fields = ('farm', 'name', 'kind', 'unit')

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        farms = Farm.objects.all() if user_is_admin(user) else Farm.objects.filter(owner=user)
        self.fields['farm'].queryset = farms

    def clean_farm(self):
        farm = self.cleaned_data['farm']
        if not user_is_admin(self.user) and farm.owner_id != self.user.id:
            raise ValidationError('Choose one of your farms.')
        return farm

    def save(self, commit=True):
        sensor = super().save(commit=False)
        sensor.home = None
        if commit:
            sensor.save()
        return sensor
