from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import User
from apps.farms.geo import farm_point, find_place, in_tunisia
from apps.farms.models import Farm

PASSWORD = 'Kizuna-farm-2026'


def payload(**extra):
    data = {
        'name': 'Domaine Ben Salah', 'location': 'Mateur, Bizerte', 'area_m2': '40000',
        'soil_type': 'loam', 'irrigation_type': 'drip',
        'tank_capacity_liters': '20000', 'solar_capacity_watts': '3000',
        'crops-TOTAL_FORMS': '2', 'crops-INITIAL_FORMS': '0',
        'crops-MIN_NUM_FORMS': '0', 'crops-MAX_NUM_FORMS': '1000',
        'crops-0-kind': 'olive', 'crops-0-area_m2': '30000', 'crops-0-stage': 'fruiting', 'crops-0-name': '',
        'crops-1-kind': 'tomato', 'crops-1-area_m2': '5000', 'crops-1-stage': 'flowering', 'crops-1-name': 'Serre',
    }
    data.update(extra)
    return data


class FarmFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('hedi', '', PASSWORD, role=User.Role.FARMER)
        self.client.force_login(self.user)

    def test_create_farm_with_several_crops_and_place(self):
        response = self.client.post('/farms/new/', payload())
        farm = Farm.objects.get()
        self.assertRedirects(response, f'/farms/{farm.pk}/')
        crops = {crop.kind: crop for crop in farm.crops.all()}
        self.assertEqual(float(crops['olive'].area_m2), 30000)
        self.assertEqual(crops['olive'].name, 'Olivier')
        self.assertEqual(float(crops['tomato'].area_m2), 5000)
        self.assertEqual(farm.crop_type, 'olive')
        # « Mateur, Bizerte » : coordonnées remplies à partir du lieu, en Tunisie.
        self.assertTrue(in_tunisia(farm.latitude, farm.longitude))
        self.assertAlmostEqual(float(farm.latitude), 37.04, places=1)
        page = self.client.get(f'/farms/{farm.pk}/')
        self.assertContains(page, 'Mes cultures')
        self.assertContains(page, 'farm-map')
        self.assertContains(page, '75.0 %')

    def test_crops_larger_than_farm_are_refused(self):
        response = self.client.post('/farms/new/', payload(**{'crops-0-area_m2': '39000'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'plus que la ferme')
        self.assertFalse(Farm.objects.exists())

    def test_at_least_one_crop(self):
        response = self.client.post('/farms/new/', payload(**{'crops-TOTAL_FORMS': '0'}))
        self.assertContains(response, 'au moins une culture')

    def test_point_outside_tunisia_is_refused(self):
        response = self.client.post('/farms/new/', payload(latitude='90', longitude='179.9'))
        self.assertContains(response, 'en dehors de la Tunisie')

    def test_edit_keeps_and_removes_crops(self):
        self.client.post('/farms/new/', payload())
        farm = Farm.objects.get()
        olive, tomato = farm.crops.order_by('kind')
        data = payload(**{
            'crops-INITIAL_FORMS': '2',
            'crops-0-id': str(olive.pk), 'crops-0-farm': str(farm.pk),
            'crops-1-id': str(tomato.pk), 'crops-1-farm': str(farm.pk), 'crops-1-DELETE': 'on',
            'crops-1-kind': 'tomato',
        })
        response = self.client.post(f'/farms/{farm.pk}/edit/', data)
        self.assertRedirects(response, f'/farms/{farm.pk}/')
        self.assertEqual(list(farm.crops.values_list('kind', flat=True)), ['olive'])

    def test_old_bad_coordinates_fall_back_to_city(self):
        farm = Farm.objects.create(owner=self.user, name='Vieille', location='bizerte',
                                   latitude=90, longitude=179.9, area_m2=1000)
        lat, lng, exact = farm_point(farm)
        self.assertFalse(exact)
        self.assertAlmostEqual(lat, 37.27, places=1)
        self.assertContains(self.client.get(f'/farms/{farm.pk}/'), 'centre de bizerte')

    def test_place_lookup(self):
        self.assertEqual(find_place('menzel bourguiba')[0], 'Menzel Bourguiba')
        self.assertEqual(find_place('Ferme à Gabes')[0], 'Gabès')
        self.assertIsNone(find_place('Paris'))
