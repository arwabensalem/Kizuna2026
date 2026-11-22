from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import User
from apps.farms.advisor import advise
from apps.farms.models import Crop, Farm, IrrigationSystem

PASSWORD = 'Kizuna-farm-2026'


class FarmAdvisorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            'hedi', 'hedi@example.com', PASSWORD, role=User.Role.FARMER,
        )
        self.farm = Farm.objects.create(
            owner=self.user, name='Oliveraie de Sfax', area_m2=10000,
            soil_type='loam', irrigation_type='drip', crop_type='olive',
        )
        Crop.objects.create(farm=self.farm, name='Parcelle nord', area_m2=4000, stage='fruiting')
        Crop.objects.create(farm=self.farm, name='Parcelle sud', area_m2=2000, stage='flowering')
        IrrigationSystem.objects.create(farm=self.farm, name='Goutte-à-goutte', method='drip', flow_liters_per_hour=4000)

    def test_dry_soil_gives_volume_and_pumping_time_per_parcel(self):
        result = advise(self.farm, shallow=20, deep=24, rain_mm_48h=0, today=date(2026, 7, 10), now_hour=7)
        self.assertEqual(result['decision']['status'], 'now')
        self.assertEqual(len(result['parcels']), 2)
        north = result['parcels'][0]
        self.assertGreater(north['volume_m3'], 0)
        self.assertGreater(north['minutes'], 0)
        self.assertEqual(result['pump_m3_per_hour'], 4.0)
        self.assertAlmostEqual(north['volume_m3'], 4000 * (40 - 21.6) / 100 * 0.4 / 0.9, delta=0.2)

    def test_rain_coming_means_no_irrigation(self):
        result = advise(self.farm, shallow=30, deep=32, rain_mm_48h=12, today=date(2026, 3, 1))
        self.assertEqual(result['decision']['status'], 'rain')
        self.assertIn('la pluie arrive', result['decision']['title'])
        self.assertEqual(result['total_m3'], 0)

    def test_wet_soil_needs_nothing(self):
        result = advise(self.farm, shallow=45, deep=44, rain_mm_48h=0)
        self.assertEqual(result['decision']['status'], 'ok')

    def test_olive_harvest_falls_in_season_with_price(self):
        result = advise(self.farm, shallow=30, deep=30, rain_mm_48h=0, today=date(2026, 7, 10))
        harvest = result['harvests'][0]
        self.assertIn(harvest['date'].month, (11, 12, 1))
        self.assertGreater(harvest['yield_kg'], 0)
        self.assertGreater(harvest['revenue'], 0)

    def test_advice_page_for_owner_only(self):
        self.client.login(username='hedi', password=PASSWORD)
        response = self.client.get(f'/farms/{self.farm.pk}/conseils/?sol20=18&sol40=22&pluie=0')
        self.assertContains(response, 'Quand arroser ?')
        self.assertContains(response, 'Parcelle nord')
        self.assertContains(response, 'm³')
        other = get_user_model().objects.create_user('autre', 'a@example.com', PASSWORD, role=User.Role.FARMER)
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/farms/{self.farm.pk}/conseils/').status_code, 404)
