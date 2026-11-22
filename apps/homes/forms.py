from django import forms

from apps.accounts.forms import BootstrapModelForm
from apps.accounts.permissions import user_is_admin
from apps.homes.models import Appliance, Home, Room


def _french_choices(field):
    """Affiche les types (pièces, appareils) en français ; la valeur enregistrée ne change pas."""
    from apps.dashboard.templatetags.kizuna_fr import KINDS
    field.choices = [(value, KINDS.get(value, label)) for value, label in field.choices]


class HomeForm(BootstrapModelForm):
    class Meta:
        model = Home
        fields = (
            'home_type',
            'name',
            'address',
            'area_m2',
            'residents',
            'bedrooms',
            'bathrooms',
            'has_kitchen',
            'has_living_room',
            'has_garden',
            'has_pool',
            'has_garage',
            'has_solar_panels',
            'has_water_tank',
            'latitude',
            'longitude',
        )
        widgets = {'home_type': forms.RadioSelect}
        labels = {
            'home_type': 'Modèle de maison',
            'name': 'Nom de la maison',
            'address': 'Adresse',
            'area_m2': 'Surface (m²)',
            'residents': "Nombre d'habitants",
            'bedrooms': 'Nombre de chambres',
            'bathrooms': 'Nombre de salles de bain',
            'has_kitchen': 'Cuisine',
            'has_living_room': 'Salon',
            'has_garden': 'Jardin',
            'has_pool': 'Piscine',
            'has_garage': 'Garage',
            'has_solar_panels': 'Panneaux solaires sur le toit',
            'has_water_tank': "Réservoir d'eau (citerne, majel)",
            'latitude': 'Latitude (facultatif)',
            'longitude': 'Longitude (facultatif)',
        }
        help_texts = {
            'name': 'Par exemple : Maison de Sfax.',
            'latitude': 'Laissez vide si vous ne savez pas.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['home_type'].required = False

    def clean_home_type(self):
        return self.cleaned_data.get('home_type') or Home.HomeType.APARTMENT


class RoomForm(BootstrapModelForm):
    class Meta:
        model = Room
        fields = ('name', 'kind')
        labels = {'name': 'Nom de la pièce', 'kind': 'Type de pièce'}
        help_texts = {'name': 'Par exemple : Chambre des enfants.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _french_choices(self.fields['kind'])


class RoomSelect(forms.Select):
    def __init__(self, rooms=None, *args, **kwargs):
        self.rooms_by_id = {room.pk: room for room in (rooms or [])}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs,
        )
        try:
            room_id = int(str(value))
        except (TypeError, ValueError):
            return option
        room = self.rooms_by_id.get(room_id)
        if room:
            option['attrs']['data-home'] = str(room.home_id)
        return option


class ApplianceForm(BootstrapModelForm):
    needs_user = True

    class Meta:
        model = Appliance
        fields = (
            'home',
            'room',
            'kind',
            'label',
            'power_watts',
            'water_liters_per_hour',
            'temperature_setpoint',
            'is_active',
        )
        labels = {
            'home': 'Maison',
            'room': 'Pièce (facultatif)',
            'kind': "Type d'appareil",
            'label': 'Nom (facultatif)',
            'power_watts': 'Puissance électrique (W)',
            'water_liters_per_hour': "Consommation d'eau (L/h)",
            'temperature_setpoint': 'Température réglée, pour une clim (°C, facultatif)',
            'is_active': 'Allumé en ce moment',
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        homes = Home.objects.all() if user_is_admin(user) else Home.objects.filter(owner=user)
        rooms = Room.objects.select_related('home')
        if not user_is_admin(user):
            rooms = rooms.filter(home__owner=user)
        rooms = list(rooms)
        self.fields['home'].queryset = homes
        self.fields['room'].queryset = Room.objects.filter(pk__in=[room.pk for room in rooms])
        self.fields['room'].widget = RoomSelect(rooms=rooms, attrs={'class': 'form-select'})
        self.fields['room'].widget.choices = self.fields['room'].choices
        self.fields['room'].required = False
        self.fields['label'].required = False
        _french_choices(self.fields['kind'])

    def clean(self):
        cleaned = super().clean()
        home = cleaned.get('home')
        room = cleaned.get('room')
        if home and not user_is_admin(self.user) and home.owner_id != self.user.id:
            self.add_error('home', 'Choisissez une de vos maisons.')
        if home and room and room.home_id != home.id:
            self.add_error('room', 'Choisissez une pièce de cette maison.')
        if cleaned.get('kind') not in Appliance.WATER_KINDS:
            cleaned['water_liters_per_hour'] = 0
        return cleaned
