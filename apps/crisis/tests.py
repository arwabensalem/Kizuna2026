import json

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.crisis.lab import SCENARIOS, LabError, clean_inputs, crop_stress, run_lab


class FormulaForecaster:
    def __call__(self, rows):
        return [crop_stress(row['soil_moisture'], row['temperature'], row['humidity'], row['rainfall']) for row in rows]

    def describe(self):
        return {'used': False, 'model': None, 'note': 'Test forecaster.'}


def lab(scenario, **changes):
    return run_lab(clean_inputs({'scenario': scenario, **changes}), forecaster=FormulaForecaster())


class LabEngineTests(TestCase):
    def test_both_runs_start_from_identical_conditions(self):
        result = lab('COMBINED_CRISIS')
        self.assertEqual(result['without']['hours'][0]['hour'], result['with']['hours'][0]['hour'])
        self.assertEqual(len(result['without']['hours']), result['inputs']['duration'])
        self.assertEqual(len(result['with']['hours']), result['inputs']['duration'])
        self.assertIn('home_tank_l', result['initial'])
        self.assertTrue(result['simulated'])
        self.assertIn('Synthetic', result['label'])

    def test_results_are_deterministic(self):
        first = lab('HEATWAVE')
        second = lab('HEATWAVE')
        self.assertEqual(first['without']['metrics'], second['without']['metrics'])
        self.assertEqual(first['with']['metrics'], second['with']['metrics'])
        self.assertEqual(first['comparison'], second['comparison'])

    def test_run_without_kizuna_takes_no_actions(self):
        result = lab('COMBINED_CRISIS')
        base = result['without']
        self.assertEqual(base['events'], [])
        self.assertEqual(base['metrics']['solar_stored_wh'], 0)
        self.assertEqual(base['metrics']['rain_recovered_l'], 0)
        self.assertEqual(base['metrics']['shed_hours'], 0)

    def test_kizuna_keeps_pump_powered_during_outage(self):
        result = lab('POWER_OUTAGE')
        self.assertGreater(result['without']['metrics']['pump_outage_hours'], 0)
        self.assertEqual(result['with']['metrics']['pump_outage_hours'], 0)
        self.assertEqual(result['with']['metrics']['critical_unmet_wh'], 0)

    def test_heatwave_cascade_is_contained(self):
        result = lab('HEATWAVE')
        labels = [step['label'] for step in result['propagation']['steps']]
        self.assertEqual(labels[0], 'HEATWAVE')
        self.assertIn('Crop stress ↑', labels)
        self.assertEqual(result['response']['status'], 'CRISIS CONTAINED')
        self.assertEqual(result['response']['chains'][0][0]['label'], 'Solar')

    def test_heavy_rain_recovers_water(self):
        result = lab('HEAVY_RAIN')
        recovered = result['with']['metrics']['rain_recovered_l']
        self.assertGreater(recovered, 0)
        self.assertEqual(result['comparison']['water_saved_parts']['rain_recovered_l'], recovered)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(LabError):
            clean_inputs({'scenario': 'METEOR'})
        with self.assertRaises(LabError):
            clean_inputs({'scenario': 'NORMAL', 'temperature': 99})
        with self.assertRaises(LabError):
            clean_inputs({'scenario': 'NORMAL', 'grid': 'lots'})

    def test_missing_fields_use_the_scenario_preset(self):
        inputs = clean_inputs({'scenario': 'DROUGHT', 'temperature': 40})
        self.assertEqual(inputs['temperature'], 40)
        self.assertEqual(inputs['soil'], SCENARIOS['DROUGHT']['soil'])


class LabViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='lab', password='Kizuna-lab-2026', role=User.Role.CITIZEN)

    def test_page_requires_login(self):
        response = self.client.get(reverse('crisis:lab'))
        self.assertEqual(response.status_code, 302)

    def test_page_shows_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('crisis:lab'))
        self.assertContains(response, 'SIMULATE')
        for name in SCENARIOS:
            self.assertContains(response, f'data-scenario="{name}"')
        self.assertContains(response, 'id="lab-presets"')

    def test_api_requires_login(self):
        response = self.client.post(reverse('crisis_simulate'), '{}', content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['detail'], 'Authentication required.')

    def test_api_runs_simulation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('crisis_simulate'),
            json.dumps({'scenario': 'POWER_OUTAGE', 'duration': 24}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['inputs']['duration'], 24)
        self.assertIn('comparison', body)

    def test_api_rejects_bad_input(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('crisis_simulate'),
            json.dumps({'scenario': 'NORMAL', 'soil': 500}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.json())
