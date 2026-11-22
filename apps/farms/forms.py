from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.accounts.forms import BootstrapModelForm
from apps.accounts.permissions import user_is_admin
from apps.farms.geo import find_place, in_tunisia
from apps.farms.models import Crop, Farm, FarmSensor, FarmSolar, FarmTank, IrrigationSystem


def farms_for(user):
    if user_is_admin(user):
        return Farm.objects.all()
    return Farm.objects.filter(owner=user)


class OwnedFarmForm(BootstrapModelForm):
    needs_user = True

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['farm'].queryset = farms_for(user)

    def clean_farm(self):
        farm = self.cleaned_data.get('farm')
        if farm and not user_is_admin(self.user) and farm.owner_id != self.user.id:
            raise ValidationError('Choisissez une de vos fermes.')
        return farm


class FarmForm(BootstrapModelForm):
    class Meta:
        model = Farm
        fields = (
            'name',
            'location',
            'latitude',
            'longitude',
            'area_m2',
            'soil_type',
            'irrigation_type',
            'tank_capacity_liters',
            'solar_capacity_watts',
        )
        labels = {
            'area_m2': 'Area (m²)',
            'soil_type': 'Soil type',
            'irrigation_type': 'Irrigation type',
            'crop_type': 'Crop type',
            'tank_capacity_liters': 'Tank capacity (L)',
            'solar_capacity_watts': 'Solar capacity (W)',
        }
        help_texts = {
            'location': 'Tapez votre ville ou délégation (ex. : Mateur, Bizerte) : la carte se place toute seule.',
            'tank_capacity_liters': 'Volume total de vos réservoirs ou bassins.',
            'solar_capacity_watts': 'Puissance des panneaux qui alimentent la pompe (0 si aucun).',
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['latitude'].widget.attrs.update({'readonly': True, 'tabindex': '-1'})
        self.fields['longitude'].widget.attrs.update({'readonly': True, 'tabindex': '-1'})
        self.fields['location'].widget.attrs.update({'list': 'kz-places', 'autocomplete': 'off'})
        _whole(self, 'area_m2')

    def clean(self):
        cleaned = super().clean()
        lat, lng = cleaned.get('latitude'), cleaned.get('longitude')
        if lat is not None and lng is not None and not in_tunisia(lat, lng):
            raise ValidationError(
                'Ce point est en dehors de la Tunisie. Tapez votre ville ou cliquez sur la carte.'
            )
        if lat is None or lng is None:
            place = find_place(cleaned.get('location'))
            if place:
                cleaned['latitude'] = Decimal(str(place[1]))
                cleaned['longitude'] = Decimal(str(place[2]))
        return cleaned


def _whole(form, name):
    """Affiche 4000 au lieu de 4000.0 pour une surface entière."""
    value = getattr(form.instance, name, None) if form.instance.pk else None
    if value is not None and value == int(value):
        form.initial[name] = int(value)


class FarmCropForm(forms.ModelForm):
    class Meta:
        model = Crop
        fields = ('kind', 'name', 'area_m2', 'stage')
        labels = {
            'kind': 'Culture',
            'name': 'Nom de la parcelle (facultatif)',
            'area_m2': 'Surface (m²)',
            'stage': 'Stade',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.forms import style_form

        style_form(self)
        self.fields['name'].required = False
        self.fields['name'].widget.attrs['placeholder'] = 'ex. : Parcelle nord'
        self.fields['area_m2'].widget.attrs.update({'min': '1', 'step': '1', 'inputmode': 'decimal'})
        _whole(self, 'area_m2')

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('name') and cleaned.get('kind'):
            from apps.accounts.fr import CHOICES

            label = dict(Farm.CropType.choices).get(cleaned['kind'], '')
            cleaned['name'] = CHOICES.get(label, label)
            self.instance.name = cleaned['name']
        area = cleaned.get('area_m2')
        if area is not None and area <= 0:
            self.add_error('area_m2', 'La surface doit être supérieure à 0.')
        return cleaned


class BaseFarmCropFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        kept = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE')
        ]
        if not kept:
            raise ValidationError('Ajoutez au moins une culture avec sa surface.')
        total = sum(form.cleaned_data['area_m2'] for form in kept)
        farm_area = getattr(self, 'farm_area', None)
        if farm_area and total > farm_area:
            raise ValidationError(
                f'Vos cultures couvrent {total:.0f} m², plus que la ferme ({farm_area:.0f} m²). '
                'Corrigez une surface ou agrandissez la ferme.'
            )


FarmCropFormSet = inlineformset_factory(
    Farm,
    Crop,
    form=FarmCropForm,
    formset=BaseFarmCropFormSet,
    extra=0,
    can_delete=True,
)


def main_crop(crops):
    """La culture principale de la ferme est celle qui a la plus grande surface."""
    crops = [crop for crop in crops if crop.kind]
    if not crops:
        return None
    return max(crops, key=lambda crop: crop.area_m2).kind


class CropForm(OwnedFarmForm):
    class Meta:
        model = Crop
        fields = ('farm', 'kind', 'name', 'area_m2', 'stage')
        labels = {'area_m2': 'Area (m²)', 'kind': 'Culture'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kind'].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('kind') and cleaned.get('farm'):
            cleaned['kind'] = cleaned['farm'].crop_type
            self.instance.kind = cleaned['kind']
        return cleaned


class FarmSensorForm(OwnedFarmForm):
    class Meta:
        model = FarmSensor
        fields = ('farm', 'kind', 'label', 'is_active', 'shared_with_neighbors')
        labels = {
            'kind': 'Sensor',
            'label': 'Name',
            'is_active': 'Active',
            'shared_with_neighbors': 'Partagé avec mes voisins (station météo commune)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['label'].required = False


class IrrigationSystemForm(OwnedFarmForm):
    class Meta:
        model = IrrigationSystem
        fields = ('farm', 'name', 'method', 'flow_liters_per_hour', 'is_active')
        labels = {
            'flow_liters_per_hour': 'Flow (L/h)',
            'is_active': 'Running',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['method'].choices = [
            choice for choice in Farm.IrrigationType.choices if choice[0] != Farm.IrrigationType.NONE
        ]


class FarmTankForm(OwnedFarmForm):
    class Meta:
        model = FarmTank
        fields = ('farm', 'name', 'capacity_liters')
        labels = {'capacity_liters': 'Capacity (L)'}


class FarmSolarForm(OwnedFarmForm):
    class Meta:
        model = FarmSolar
        fields = ('farm', 'name', 'capacity_watts')
        labels = {'capacity_watts': 'Capacity (W)'}
