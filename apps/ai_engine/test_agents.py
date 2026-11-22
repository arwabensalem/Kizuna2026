from django.test import SimpleTestCase

from engine.agents import coordinate
from engine.agents.orchestrator import KizunaOrchestrator
from engine.orchestrator import Orchestrator


def clock(**overrides):
    state = {
        'hour': 14,
        'scenario': 'NORMAL',
        'critical_leak': False,
        'sensors': {
            'home': {'temperature': {'value': 28, 'unit': 'C'}},
            'farm': {
                'temperature': {'value': 29, 'unit': 'C'},
                'humidity': {'value': 55, 'unit': '%'},
                'rainfall': {'value': 0, 'unit': 'mm'},
            },
            'grid': {'grid_availability': {'value': 1}},
        },
        'tanks': {'home_percent': 70, 'farm_percent': 68},
        'batteries': {'home_percent': 80, 'farm_percent': 75},
        'solar': {'home_watts': 2200, 'farm_watts': 3000},
        'consumption': {
            'home_water_liters_per_hour': 12,
            'home_electricity_watts': 500,
        },
        'soil_moisture': 46,
        'pump': {'farm': 'off'},
    }
    state.update(overrides)
    return state


def action_ids(result):
    return [item['id'] for item in result['actions']]


class AgentArchitectureTests(SimpleTestCase):
    def test_the_phase_stub_is_unchanged(self):
        with self.assertRaises(NotImplementedError):
            Orchestrator().decide({})

    def test_empty_state_chooses_nothing(self):
        result = coordinate({})
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['actions'], [])
        self.assertIn('no action was chosen', result['trace'][-1])
        self.assertIn('No language model', result['label'])

    def test_same_state_returns_the_same_decision(self):
        state = clock()
        self.assertEqual(coordinate(state), coordinate(state))
        self.assertEqual(
            KizunaOrchestrator().coordinate(state)['actions'],
            coordinate(state)['actions'],
        )

    def test_a_settled_hour_does_not_irrigate(self):
        result = coordinate(clock())
        self.assertNotIn('start_irrigation', action_ids(result))
        self.assertNotIn('close_valve', action_ids(result))
        self.assertEqual(result['status'], 'normal')

    def test_a_leak_blocks_irrigation(self):
        result = coordinate(clock(
            critical_leak=True,
            soil_moisture=10,
            sensors={
                'home': {'temperature': {'value': 40}},
                'farm': {
                    'temperature': {'value': 42},
                    'humidity': {'value': 25},
                    'rainfall': {'value': 0},
                },
                'grid': {'grid_availability': {'value': 1}},
            },
        ))
        self.assertIn('close_valve', action_ids(result))
        self.assertNotIn('start_irrigation', action_ids(result))
        self.assertTrue(any(line.startswith('Not taken:') for line in result['trace']))

    def test_heat_and_dry_soil_starts_irrigation_when_water_and_power_allow_it(self):
        result = coordinate(clock(
            scenario='HEATWAVE',
            soil_moisture=22,
            sensors={
                'home': {'temperature': {'value': 45}},
                'farm': {
                    'temperature': {'value': 45},
                    'humidity': {'value': 30},
                    'rainfall': {'value': 0},
                },
                'grid': {'grid_availability': {'value': 1}},
            },
        ))
        self.assertIn('start_irrigation', action_ids(result))
        climate = next(item for item in result['modules'] if item['agent'] == 'climate')
        self.assertEqual(climate['findings'][0]['value'], 'heatwave scenario')

    def test_rain_suspends_irrigation_even_when_crops_are_stressed(self):
        result = coordinate(clock(
            scenario='HEAVY_RAIN',
            soil_moisture=10,
            sensors={
                'home': {'temperature': {'value': 24}},
                'farm': {
                    'temperature': {'value': 45},
                    'humidity': {'value': 20},
                    'rainfall': {'value': 2},
                },
                'grid': {'grid_availability': {'value': 1}},
            },
        ))
        ids = action_ids(result)
        self.assertIn('suspend_irrigation', ids)
        self.assertIn('collect_rain', ids)
        self.assertNotIn('start_irrigation', ids)

    def test_an_outage_with_little_solar_does_not_start_the_pump(self):
        result = coordinate(clock(
            batteries={'home_percent': 10, 'farm_percent': 10},
            solar={'home_watts': 50, 'farm_watts': 100},
            soil_moisture=10,
            sensors={
                'home': {'temperature': {'value': 40}},
                'farm': {
                    'temperature': {'value': 42},
                    'humidity': {'value': 25},
                    'rainfall': {'value': 0},
                },
                'grid': {'grid_availability': {'value': 0}},
            },
        ))
        ids = action_ids(result)
        self.assertIn('shed_non_critical_loads', ids)
        self.assertIn('hold_battery', ids)
        self.assertNotIn('discharge_battery', ids)
        self.assertNotIn('start_irrigation', ids)

    def test_solar_can_cover_the_pump_during_an_outage(self):
        result = coordinate(clock(
            batteries={'home_percent': 40, 'farm_percent': 50},
            solar={'home_watts': 200, 'farm_watts': 1200},
            soil_moisture=10,
            sensors={
                'home': {'temperature': {'value': 40}},
                'farm': {
                    'temperature': {'value': 42},
                    'humidity': {'value': 25},
                    'rainfall': {'value': 0},
                },
                'grid': {'grid_availability': {'value': 0}},
            },
        ))
        ids = action_ids(result)
        self.assertIn('discharge_battery', ids)
        self.assertIn('start_irrigation', ids)
        self.assertNotIn('hold_pump_power', ids)
