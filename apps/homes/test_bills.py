from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.homes.advice import home_advice
from apps.homes.bills import predict_bills, sonede_cost, steg_cost
from apps.homes.models import Appliance, Home

PASSWORD = 'Kizuna-home-2026'


class BillTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            'amira', 'amira@example.com', PASSWORD, role=User.Role.CITIZEN,
        )
        self.home = Home.objects.create(owner=self.user, name='Appartement', residents=3, area_m2=90)

    def add(self, kind, watts=0, water=0, active=True, setpoint=None):
        return Appliance.objects.create(
            home=self.home, kind=kind, power_watts=watts,
            water_liters_per_hour=water, is_active=active, temperature_setpoint=setpoint,
        )

    def test_steg_is_progressive_then_flat_above_200(self):
        self.assertAlmostEqual(steg_cost(50), (50 * 0.062 + 0.7) * 1.13, places=3)
        self.assertAlmostEqual(steg_cost(250), (250 * 0.218 + 0.7) * 1.13, places=3)
        self.assertGreater(steg_cost(201), steg_cost(200) * 1.2)

    def test_sonede_grows_with_volume(self):
        self.assertLess(sonede_cost(15), sonede_cost(45))

    def test_small_home_stays_in_low_tier(self):
        self.add('lights', watts=60)
        bills = predict_bills(self.home, today=date(2026, 11, 10))
        self.assertEqual(bills['electricity']['alert']['status'], 'ok')
        self.assertEqual(bills['electricity']['alert']['tier'], 1)
        self.assertGreater(bills['water']['amount'], 0)

    def test_alert_before_expensive_tier(self):
        self.add('ac', watts=1800)
        bills = predict_bills(self.home, today=date(2026, 11, 3))
        alert = bills['electricity']['alert']
        self.assertEqual(alert['status'], 'danger')
        self.assertIn('tranche', alert['message'])

    def test_home_page_shows_bills_and_advice(self):
        self.add('refrigerator', watts=320)
        self.add('ac', watts=1500, setpoint=18)
        self.client.login(username='amira', password=PASSWORD)
        response = self.client.get(f'/homes/{self.home.pk}/')
        self.assertContains(response, 'Mes prochaines factures')
        self.assertContains(response, 'STEG')
        self.assertContains(response, 'SONEDE')
        self.assertContains(response, 'consomme anormalement')
        self.assertContains(response, 'réglée trop bas')


class AdviceTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('sami', 's@example.com', PASSWORD)
        self.home = Home.objects.create(owner=user, name='Villa', residents=4, area_m2=150, has_solar_panels=True)

    def at(self, hour):
        return timezone.make_aware(datetime(2026, 7, 1, hour, 0))

    def test_solar_says_start_washing_machine_at_noon(self):
        Appliance.objects.create(home=self.home, kind='washing_machine', power_watts=2000, is_active=False)
        tips = home_advice(self.home, now=self.at(13))['tips']
        self.assertTrue(any('Lancez la machine à laver maintenant' in tip['text'] for tip in tips))

    def test_no_solar_tip_at_night(self):
        Appliance.objects.create(home=self.home, kind='washing_machine', power_watts=2000, is_active=False)
        tips = home_advice(self.home, now=self.at(23))['tips']
        self.assertFalse(any('panneaux' in tip['title'] for tip in tips))

    def test_normal_fridge_and_eco_ac_give_no_alert(self):
        Appliance.objects.create(home=self.home, kind='refrigerator', power_watts=140)
        Appliance.objects.create(home=self.home, kind='ac', power_watts=1200, temperature_setpoint=26)
        tips = home_advice(self.home, now=self.at(23))['tips']
        self.assertEqual(tips, [])
