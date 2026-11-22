from django.test import TestCase

from apps.accounts.models import User
from apps.actuators.engine import run_rules
from apps.actuators.models import Actuator, ActuatorAction
from apps.brain.services import build_brain
from apps.homes.models import Home
from apps.simulation.services import advance_simulation, reset_simulation


def citizen(username):
    return User.objects.create_user(username=username, password='Kizuna-brain-2026', role=User.Role.CITIZEN)


def make_home(owner, mode='smart'):
    return Home.objects.create(
        owner=owner,
        name='Brain house',
        residents=2,
        area_m2=90,
        autonomy_mode=mode,
        autopilot_enabled=mode != 'assist',
    )


def labels(rows):
    return {row['label']: row for row in rows}


class BrainTests(TestCase):
    def test_current_values_come_from_the_simulation_clock(self):
        reset_simulation(seed=5, scenario='HEATWAVE')
        state = advance_simulation(steps=14)
        brain = build_brain()
        current = labels(brain['current'])
        self.assertEqual(brain['hour'], state['hour'])
        self.assertEqual(current['Temperature']['value'], f"{state['sensors']['home']['temperature']['value']}°C")
        self.assertIn(f"{state['tanks']['home_percent']}%", current['Water availability']['note'])
        self.assertIn(f"{state['solar']['home_watts']} W", current['Solar production']['note'])
        self.assertEqual(current['Grid']['value'], 'AVAILABLE')
        self.assertTrue(brain['simulated'])

    def test_understanding_compares_with_the_previous_stored_hour(self):
        reset_simulation(seed=5, scenario='HEATWAVE')
        first = build_brain()
        self.assertEqual({item['direction'] for item in first['understanding']}, {'baseline'})
        before = advance_simulation(steps=1)
        after = advance_simulation(steps=1)
        brain = build_brain()
        stress = labels(brain['understanding'])['Crop stress']
        self.assertLess(after['soil_moisture'], before['soil_moisture'] - 0.2)
        self.assertEqual(stress['symbol'], '↑')
        water = labels(brain['understanding'])['Water demand']
        self.assertIn(water['symbol'], {'↑', '↓', '→'})

    def test_outage_status_flows_and_resources_follow_the_engine(self):
        reset_simulation(seed=5, scenario='POWER_OUTAGE')
        state = advance_simulation(steps=12)
        brain = build_brain()
        available = labels(brain['available'])
        self.assertFalse(available['Grid']['available'])
        self.assertEqual(
            available['Battery']['available'],
            state['batteries']['home_percent'] >= 15,
        )
        self.assertEqual(brain['status']['level'], state['crisis_state'])
        self.assertTrue(
            brain['status']['text'].endswith('CONTAINED') or brain['status']['text'].endswith('ACTIVE')
        )
        flows = [flow['text'] for flow in brain['action']['flows']]
        if state['pump']['farm'] == 'on':
            self.assertTrue(any(text.endswith('Pump → Irrigation') for text in flows))
            self.assertFalse(any(text.startswith('Grid') for text in flows))
        else:
            self.assertIn('Pump off', flows)

    def test_normal_status_has_no_contained_word(self):
        reset_simulation(seed=5, scenario='NORMAL')
        brain = build_brain()
        self.assertEqual(brain['status']['text'], 'NORMAL')

    def test_recorded_actions_are_the_stored_rows_only(self):
        owner = citizen('brain.rows')
        house = make_home(owner)
        reset_simulation(seed=5, scenario='NORMAL')
        self.assertEqual(build_brain(house)['action']['recorded'], [])
        run_rules(house, None, {
            'critical_leak': True,
            'crop_stress': 20,
            'tank_percent': 70,
            'rain_expected': False,
            'solar_watts': 200,
            'essential_watts': 300,
            'battery_percent': 60,
            'grid_available': True,
        })
        stored = ActuatorAction.objects.get(home=house)
        rows = build_brain(house)['action']['recorded']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['action'], stored.action)
        self.assertEqual(rows[0]['reason'], stored.reason)
        self.assertEqual(rows[0]['previous_state'], stored.previous_state)
        self.assertEqual(rows[0]['new_state'], stored.new_state)
        self.assertEqual(rows[0]['actuator'], 'water valve')
        self.assertEqual(stored.actuator.kind, Actuator.Kind.WATER_VALVE)

    def test_pages_and_api_require_login_and_ownership(self):
        owner = citizen('brain.owner')
        other = citizen('brain.other')
        house = make_home(owner)
        self.assertEqual(self.client.get('/api/brain/').status_code, 403)
        self.assertEqual(self.client.get('/brain/').status_code, 302)
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/api/brain/?home={house.pk}').status_code, 404)
        self.client.force_login(owner)
        page = self.client.get('/brain/')
        for heading in (
            'Current situation',
            'System understanding',
            'Available resources',
            'Current action',
            'System status',
        ):
            self.assertContains(page, heading)
        self.assertContains(page, 'This is not a chat')
        panels = self.client.get(f'/brain/panels/?home={house.pk}')
        self.assertContains(panels, 'Current situation')
        self.assertNotContains(panels, '<nav')
        api = self.client.get(f'/api/brain/?home={house.pk}')
        self.assertEqual(api.status_code, 200)
        self.assertIn('status', api.json())
