from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.crisis.lab import crop_stress
from apps.homes.models import Home
from apps.resources.passport import build_passports
from apps.simulation.models import SimulationStep
from apps.simulation.services import advance_simulation, reset_simulation


def card(board, card_id):
    return next(item for item in board['passports'] if item['id'] == card_id)


def metric(board, card_id, key):
    found = card(board, card_id)
    return next(item for item in found['metrics'] if item['key'] == key)


class PassportTests(TestCase):
    def setUp(self):
        reset_simulation(scenario='NORMAL')
        advance_simulation(steps=12)
        self.user = User.objects.create_user(username='holder', password='Kizuna-passport-2026')
        self.other = User.objects.create_user(username='other-holder', password='Kizuna-passport-2026')
        Home.objects.create(owner=self.user, name='House 1')
        Home.objects.create(owner=self.other, name='Arwa')

    def test_scores_come_from_the_stored_hours(self):
        board = build_passports(self.user)
        steps = list(SimulationStep.objects.order_by('hour'))
        solar = sum(step.payload['solar']['home_watts'] for step in steps)
        load = sum(step.payload['consumption']['home_electricity_watts'] for step in steps)
        expected = round(min(100.0, 100 * solar / load), 1)
        self.assertEqual(metric(board, 'clock-home', 'renewable_production')['score'], expected)
        stresses = [
            crop_stress(
                step.payload['soil_moisture'],
                step.payload['sensors']['farm']['temperature']['value'],
                step.payload['sensors']['farm']['humidity']['value'],
                step.payload['sensors']['farm']['rainfall']['value'],
            )
            for step in steps
        ]
        crop = round(min(100.0, max(0.0, 100 - sum(stresses) / len(stresses))), 1)
        self.assertEqual(metric(board, 'clock-farm', 'crop_resilience')['score'], crop)

    def test_the_same_hours_give_the_same_cards(self):
        first = build_passports(self.user)
        second = build_passports(self.user)
        self.assertEqual(first['passports'], second['passports'])

    def test_blank_scores_stay_blank(self):
        board = build_passports(self.user)
        self.assertIsNone(metric(board, 'clock-business', 'water_efficiency')['score'])
        self.assertIsNone(metric(board, 'clock-business', 'recovery')['score'])
        house = next(item for item in board['passports'] if item['name'] == 'House 1')
        self.assertIsNone(next(row for row in house['metrics'] if row['key'] == 'water_efficiency')['score'])
        self.assertIsNone(next(row for row in house['metrics'] if row['key'] == 'energy_efficiency')['score'])

    def test_rain_raises_water_recovery(self):
        dry = metric(build_passports(self.user), 'clock-home', 'water_recovery')['score'] or 0
        reset_simulation(scenario='HEAVY_RAIN')
        advance_simulation(steps=6)
        wet = metric(build_passports(self.user), 'clock-home', 'water_recovery')['score']
        self.assertIsNotNone(wet)
        self.assertGreater(wet, dry)

    def test_another_users_home_is_hidden(self):
        names = {item['name'] for item in build_passports(self.user)['passports']}
        self.assertIn('House 1', names)
        self.assertNotIn('Arwa', names)
        self.assertIn('Home A', names)
        self.assertIn('Farm B', names)
        self.assertIn('Workshop C', names)

    def test_every_numbered_score_is_in_range(self):
        for item in build_passports(self.user)['passports']:
            for row in item['metrics']:
                if row['score'] is None:
                    continue
                self.assertGreaterEqual(row['score'], 0)
                self.assertLessEqual(row['score'], 100)


class PassportPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='card', password='Kizuna-passport-2026')

    def test_page_requires_login(self):
        self.assertEqual(self.client.get(reverse('passport:board')).status_code, 302)

    def test_page_shows_the_three_clock_cards(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('passport:board'))
        self.assertContains(response, 'Resource passport')
        self.assertContains(response, 'Home A')
        self.assertContains(response, 'Farm B')
        self.assertContains(response, 'Workshop C')
        self.assertContains(response, 'Water efficiency')
        self.assertContains(response, 'Water productivity')
        self.assertContains(response, 'Renewable contribution')
        self.assertContains(response, 'Nothing on this page is random')
