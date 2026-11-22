import json

from django.test import TestCase

from apps.accounts.models import User
from apps.simulation.engine import _unit_interval
from apps.simulation.models import SimulatedSensor, SimulationStep
from apps.simulation.services import advance_simulation, reset_simulation

PASSWORD = 'Kizuna-sim-2026'


def sign_in(client):
    user = User.objects.create_user(
        username='simmer',
        password=PASSWORD,
        email='simmer@example.com',
        role=User.Role.CITIZEN,
    )
    client.force_login(user)
    return user


class SensorEngineTests(TestCase):
    def test_same_seed_repeats_the_series(self):
        reset_simulation(seed=11, scenario='NORMAL')
        first = advance_simulation(steps=3)
        reset_simulation(seed=11, scenario='NORMAL')
        second = advance_simulation(steps=3)
        self.assertEqual(first['sensors'], second['sensors'])
        self.assertEqual(first['tanks'], second['tanks'])
        self.assertEqual(first['batteries'], second['batteries'])
        self.assertEqual(first['soil_moisture'], second['soil_moisture'])
        self.assertEqual(first['pump'], second['pump'])
        self.assertEqual(first['valves'], second['valves'])
        self.assertNotEqual(_unit_interval(1, 0, 1), _unit_interval(2, 0, 1))

    def test_scenarios_move_the_series_in_the_expected_direction(self):
        def after(scenario, steps=1):
            reset_simulation(seed=9, scenario=scenario)
            return advance_simulation(steps=steps)

        self.assertGreater(
            after('HEATWAVE')['sensors']['home']['temperature']['value'],
            after('NORMAL')['sensors']['home']['temperature']['value'],
        )
        self.assertGreater(
            after('HEAVY_RAIN')['sensors']['farm']['rainfall']['value'],
            after('DROUGHT')['sensors']['farm']['rainfall']['value'],
        )
        self.assertLess(
            after('DROUGHT', steps=8)['soil_moisture'],
            after('HEAVY_RAIN', steps=8)['soil_moisture'],
        )
        outage = after('POWER_OUTAGE')
        self.assertEqual(outage['sensors']['grid']['grid_availability']['value'], 0)
        self.assertIn(outage['crisis_state'], ('alert', 'crisis'))
        crisis = after('COMBINED_CRISIS')
        self.assertEqual(crisis['crisis_state'], 'crisis')
        self.assertEqual(crisis['sensors']['grid']['grid_availability']['value'], 0)

    def test_api_advances_and_resets_the_stored_clock(self):
        sign_in(self.client)
        reset = self.client.post(
            '/api/simulation/reset/',
            data=json.dumps({'seed': 5, 'scenario': 'HEATWAVE'}),
            content_type='application/json',
        )
        self.assertEqual(reset.status_code, 200)
        body = reset.json()
        self.assertTrue(body['simulated'])
        self.assertIn('Synthetic', body['label'])
        self.assertEqual(body['hour'], 0)
        self.assertEqual(body['scenario'], 'HEATWAVE')
        self.assertEqual(SimulatedSensor.objects.filter(group='home').count(), 6)
        self.assertEqual(SimulatedSensor.objects.filter(group='farm').count(), 7)
        self.assertEqual(SimulatedSensor.objects.filter(group='grid').count(), 2)

        advanced = self.client.post(
            '/api/simulation/advance/',
            data=json.dumps({'steps': 2}),
            content_type='application/json',
        )
        self.assertEqual(advanced.status_code, 200)
        self.assertEqual(advanced.json()['hour'], 2)
        self.assertEqual(SimulationStep.objects.count(), 3)
        state = self.client.get('/api/simulation/state/')
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()['hour'], 2)
        self.assertEqual(state.json()['crisis_state'], advanced.json()['crisis_state'])
        self.assertEqual(state.json()['series'][-1]['hour'], 2)
        self.assertIn('resilience', state.json()['reading'])
        self.assertIn('flows', state.json()['reading'])
        self.assertIn('lines', state.json()['reading'])
        again = self.client.get('/api/simulation/state/')
        self.assertEqual(again.json()['hour'], 2)
        self.assertEqual(SimulationStep.objects.count(), 3)

        page = self.client.get('/simulation/')
        self.assertContains(page, 'Synthetic')
        self.assertContains(page, 'Simulated')
        self.assertContains(page, 'Hour')

    def test_anonymous_cannot_advance(self):
        response = self.client.post(
            '/api/simulation/advance/',
            data=json.dumps({'steps': 1}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_unknown_scenario_is_rejected(self):
        sign_in(self.client)
        response = self.client.post(
            '/api/simulation/advance/',
            data=json.dumps({'scenario': 'REAL_WEATHER'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
