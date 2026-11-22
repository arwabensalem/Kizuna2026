from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.marketplace.network import EDGES, NODES, NetworkError, build_network
from apps.simulation.services import advance_simulation, reset_simulation


def flows_by(result, source, destination, resource):
    return [
        flow for flow in result['flows']
        if (flow['source'], flow['destination'], flow['resource']) == (source, destination, resource)
    ]


def total(result, source, destination, resource):
    return sum(flow['quantity'] for flow in flows_by(result, source, destination, resource))


class NetworkEngineTests(TestCase):
    def test_every_flow_runs_on_a_drawn_edge(self):
        edges = {(source, destination, resource) for source, destination, resource in EDGES}
        nodes = {node['key'] for node in NODES}
        for scenario in ('NORMAL', 'HEATWAVE', 'DROUGHT', 'POWER_OUTAGE', 'HEAVY_RAIN', 'COMBINED_CRISIS'):
            reset_simulation(scenario=scenario)
            advance_simulation(steps=24)
            for hour in (6, 12, 19, 24):
                result = build_network(hour)
                self.assertEqual({node['key'] for node in result['nodes']}, nodes)
                for flow in result['flows']:
                    self.assertIn((flow['source'], flow['destination'], flow['resource']), edges, (scenario, hour))
                    self.assertGreater(flow['quantity'], 0)
                    self.assertEqual(flow['unit'], 'Wh' if flow['resource'] == 'energy' else 'L')
                    self.assertEqual(flow['timestamp'], result['timestamp'])

    def test_home_a_energy_balances_with_the_clock(self):
        reset_simulation(scenario='NORMAL')
        state = advance_simulation(steps=20)
        result = build_network()
        supplied = (
            total(result, 'solar_a', 'home_a', 'energy')
            + total(result, 'battery_a', 'home_a', 'energy')
            + total(result, 'grid', 'home_a', 'energy')
        )
        self.assertAlmostEqual(supplied, state['consumption']['home_electricity_watts'], delta=3)
        self.assertEqual(result['hour'], state['hour'])
        self.assertEqual(result['timestamp'], state['simulated_at'])

    def test_exchange_only_moves_curtailed_solar(self):
        reset_simulation(scenario='NORMAL')
        state = advance_simulation(steps=14)
        result = build_network()
        exchanged = sum(
            flow['quantity'] for flow in result['flows']
            if flow['kind'] == 'exchange' and flow['source'] == 'home_a'
        )
        self.assertEqual(state['batteries']['home_percent'], 100)
        self.assertGreater(exchanged, 0)
        edge = next(item for item in result['edges'] if (item['source'], item['destination']) == ('home_a', 'farm_b'))
        self.assertTrue(edge['exchange'])
        self.assertEqual(total(result, 'solar_a', 'battery_a', 'energy'), 0)
        solar = total(result, 'solar_a', 'home_a', 'energy')
        self.assertLessEqual(solar + exchanged, state['solar']['home_watts'] + 2)

    def test_no_exchange_while_batteries_charge(self):
        reset_simulation(scenario='NORMAL')
        result = build_network()
        self.assertFalse([flow for flow in result['flows'] if flow['kind'] == 'exchange' and flow['resource'] == 'energy'])

    def test_pump_chain_and_rain_chain(self):
        reset_simulation(scenario='HEATWAVE')
        advance_simulation(steps=12)
        pumped = [
            hour for hour in range(1, 13)
            if flows_by(build_network(hour), 'pump_b', 'farm_b', 'water')
        ]
        self.assertTrue(pumped)
        result = build_network(pumped[0])
        self.assertEqual(total(result, 'tank_b', 'pump_b', 'water'), total(result, 'pump_b', 'farm_b', 'water'))
        self.assertTrue(any(flow['destination'] == 'pump_b' and flow['resource'] == 'energy' for flow in result['flows']))

        reset_simulation(scenario='HEAVY_RAIN')
        advance_simulation(steps=3)
        result = build_network()
        self.assertTrue(flows_by(result, 'rain', 'roof_a', 'water'))
        self.assertTrue(flows_by(result, 'roof_a', 'tank_a', 'water'))

    def test_outage_has_no_grid_flows(self):
        reset_simulation(scenario='POWER_OUTAGE')
        advance_simulation(steps=22)
        result = build_network()
        self.assertFalse([flow for flow in result['flows'] if flow['source'] == 'grid'])
        grid = next(node for node in result['nodes'] if node['key'] == 'grid')
        self.assertEqual(grid['level'], 'alert')

    def test_same_hour_gives_same_flows(self):
        reset_simulation(scenario='NORMAL')
        advance_simulation(steps=15)
        self.assertEqual(build_network(12)['flows'], build_network(12)['flows'])

    def test_history_covers_recent_hours(self):
        reset_simulation(scenario='NORMAL')
        advance_simulation(steps=20)
        result = build_network()
        hours = {flow['hour'] for flow in result['history']}
        self.assertEqual(max(hours), 20)
        self.assertEqual(min(hours), 8)

    def test_bad_hour_is_rejected(self):
        reset_simulation(scenario='NORMAL')
        with self.assertRaises(NetworkError):
            build_network(5)
        with self.assertRaises(NetworkError):
            build_network('soon')

    def test_label_is_explicit_about_simulation(self):
        result = build_network()
        self.assertTrue(result['simulated'])
        self.assertIn('simulation of cooperation', result['label'])
        self.assertIn('not a real electricity', result['label'])


class NetworkViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='net', password='Kizuna-net-2026', role=User.Role.CITIZEN)

    def test_page_requires_login(self):
        self.assertEqual(self.client.get(reverse('network:board')).status_code, 302)

    def test_page_renders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('network:board'))
        self.assertContains(response, 'id="net-graph"')
        self.assertContains(response, 'not a real electricity')

    def test_api_requires_login(self):
        response = self.client.get(reverse('network_state'))
        self.assertEqual(response.status_code, 403)

    def test_api_returns_network(self):
        self.client.force_login(self.user)
        body = self.client.get(reverse('network_state')).json()
        for key in ('nodes', 'edges', 'flows', 'totals', 'history', 'timestamp'):
            self.assertIn(key, body)
        response = self.client.get(reverse('network_state'), {'hour': 'x'})
        self.assertEqual(response.status_code, 400)
