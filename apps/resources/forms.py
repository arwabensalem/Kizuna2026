from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.forms import BootstrapModelForm
from apps.accounts.permissions import user_is_admin
from apps.homes.models import Home
from apps.resources.models import ResourcePassport


class ResourcePassportForm(BootstrapModelForm):
    needs_user = True

    class Meta:
        model = ResourcePassport
        fields = ('home', 'period_label', 'water_used_m3', 'energy_used_kwh')

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
