from django.test import TestCase

from apps.accounts.models import User
from apps.ai_engine.detection import evaluate_home
from apps.ai_engine.models import AnomalyEvent, AutomaticAction, ConsumptionSample
from apps.homes.models import Appliance, Home


def citizen(username):
    return User.objects.create_user(username=username, password='Kizuna-anomaly-2026', role=User.Role.CITIZEN)


def home_for(owner, **kwargs):
    values = {
        'name': 'House',
        'residents': 1,
        'bathrooms': 1,
        'area_m2': 60,
    }
    values.update(kwargs)
    return Home.objects.create(owner=owner, **values)


def reading(**kwargs):
    values = {
        'water_liters_per_hour': 1,
        'energy_watts': 80,
        'temperature_c': 24,
        'hour': 14,
        'tank_percent': 60,
        'tank_previous_percent': 60,
    }
    values.update(kwargs)
    return values


class HouseholdAnomalyTests(TestCase):
    def test_the_same_flow_is_judged_against_each_home(self):
        owner = citizen('anomaly.owner')
        small = home_for(owner, name='Small', residents=1, bathrooms=1, area_m2=60)
        large = home_for(
            owner,
            name='Large',
            residents=6,
            bathrooms=2,
            area_m2=180,
            has_kitchen=True,
            has_garden=True,
            has_pool=True,
        )
        Appliance.objects.create(
            home=large,
            kind=Appliance.Kind.WASHING_MACHINE,
            power_watts=500,
            water_liters_per_hour=15,
            is_active=True,
        )
        shared = reading(water_liters_per_hour=20, energy_watts=100, hour=20, temperature_c=33)
        small_result = evaluate_home(small, shared)
        large_result = evaluate_home(large, shared)
        self.assertGreater(large_result['water']['baseline'], small_result['water']['baseline'])
        self.assertEqual(small_result['water']['type'], AnomalyEvent.Type.CRITICAL)
        self.assertIn(large_result['water']['type'], (
            AnomalyEvent.Type.NORMAL,
            AnomalyEvent.Type.HIGH_LEGITIMATE,
        ))
        self.assertTrue(small.water_valve_open)
        self.assertEqual(small.automatic_actions.get().action, AutomaticAction.Action.ALERT)

    def test_appliances_heat_and_a_rising_tank_are_not_leaks(self):
        owner = citizen('anomaly.uses')
        busy = home_for(owner, name='Busy', residents=3, bathrooms=2, has_kitchen=True, area_m2=110)
        Appliance.objects.create(
            home=busy,
            kind=Appliance.Kind.WASHING_MACHINE,
            power_watts=500,
            water_liters_per_hour=20,
            is_active=True,
        )
        legitimate = evaluate_home(busy, reading(
            water_liters_per_hour=45,
            energy_watts=700,
            hour=20,
            temperature_c=32,
        ))
        self.assertEqual(legitimate['water']['type'], AnomalyEvent.Type.HIGH_LEGITIMATE)
        self.assertFalse(legitimate['actions'][0].new_state == 'closed' and legitimate['actions'][0].previous_state == 'open')
        self.assertTrue(busy.water_valve_open)

        filling = home_for(owner, name='Tank', residents=2, bathrooms=1, area_m2=80)
        Appliance.objects.create(
            home=filling,
            kind=Appliance.Kind.PUMP,
            power_watts=700,
            water_liters_per_hour=12,
            is_active=True,
        )
        filled = evaluate_home(filling, reading(
            water_liters_per_hour=18,
            tank_previous_percent=40,
            tank_percent=55,
        ))
        self.assertEqual(filled['water']['type'], AnomalyEvent.Type.TANK_FILLING)
        self.assertTrue(filling.water_valve_open)
        self.assertEqual(filled['actions'][0].action, AutomaticAction.Action.ALERT)

    def test_possible_leak_alerts_without_moving_the_valve(self):
        owner = citizen('anomaly.leak')
        house = home_for(owner, name='Quiet')
        result = evaluate_home(house, reading(water_liters_per_hour=4, energy_watts=90))
        self.assertEqual(result['water']['type'], AnomalyEvent.Type.POSSIBLE_LEAK)
        self.assertEqual(result['water']['severity'], AnomalyEvent.Severity.WARNING)
        action = result['actions'][0]
        self.assertEqual(action.action, AutomaticAction.Action.ALERT)
        self.assertEqual(action.previous_state, 'open')
        self.assertEqual(action.new_state, 'open')
        house.refresh_from_db()
        self.assertTrue(house.water_valve_open)

    def test_critical_leak_alerts_until_autopilot_is_on(self):
        owner = citizen('anomaly.critical')
        house = home_for(owner, name='Leak')
        quiet = evaluate_home(house, reading(water_liters_per_hour=12, energy_watts=90))
        self.assertEqual(quiet['water']['type'], AnomalyEvent.Type.CRITICAL)
        self.assertEqual(quiet['actions'][0].source, AutomaticAction.Source.ALERT)
        house.refresh_from_db()
        self.assertTrue(house.water_valve_open)

        house.autopilot_enabled = True
        house.save(update_fields=['autopilot_enabled'])
        closed = evaluate_home(house, reading(water_liters_per_hour=12, energy_watts=90))
        self.assertEqual(closed['actions'][0].action, AutomaticAction.Action.CLOSE_VALVE)
        self.assertEqual(closed['actions'][0].source, AutomaticAction.Source.AUTOPILOT)
        self.assertEqual(closed['actions'][0].previous_state, 'open')
        self.assertEqual(closed['actions'][0].new_state, 'closed')
        house.refresh_from_db()
        self.assertFalse(house.water_valve_open)
        self.assertEqual(AutomaticAction.objects.filter(home=house).count(), 2)

    def test_critical_energy_does_not_close_the_valve(self):
        owner = citizen('anomaly.energy')
        house = home_for(owner, name='Power', autopilot_enabled=True)
        result = evaluate_home(house, reading(water_liters_per_hour=1, energy_watts=8000))
        self.assertEqual(result['water']['type'], AnomalyEvent.Type.NORMAL)
        self.assertEqual(result['energy']['type'], AnomalyEvent.Type.CRITICAL)
        self.assertEqual(result['actions'][0].action, AutomaticAction.Action.ALERT)
        house.refresh_from_db()
        self.assertTrue(house.water_valve_open)

    def test_saved_history_moves_this_homes_baseline(self):
        owner = citizen('anomaly.history')
        house = home_for(owner, name='History')
        for _ in range(8):
            ConsumptionSample.objects.create(
                home=house,
                hour=14,
                temperature_c=24,
                water_liters_per_hour=10,
                energy_watts=100,
                tank_percent=60,
            )
        with_history = evaluate_home(house, reading(water_liters_per_hour=10, energy_watts=100))
        bare = home_for(owner, name='Bare')
        without = evaluate_home(bare, reading(water_liters_per_hour=10, energy_watts=100))
        self.assertGreater(with_history['water']['baseline'], without['water']['baseline'])
        self.assertNotEqual(with_history['water']['type'], AnomalyEvent.Type.CRITICAL)
        self.assertEqual(without['water']['type'], AnomalyEvent.Type.CRITICAL)

    def test_isolation_forest_does_not_relabel_normal_water(self):
        owner = citizen('anomaly.forest')
        house = home_for(owner, name='Series', residents=2, bathrooms=1, area_m2=80)
        for hour in range(24):
            ConsumptionSample.objects.create(
                home=house,
                hour=hour,
                temperature_c=25,
                water_liters_per_hour=3,
                energy_watts=120,
                tank_percent=60,
            )
        result = evaluate_home(house, reading(
            water_liters_per_hour=2,
            energy_watts=9000,
            hour=14,
            temperature_c=25,
        ))
        self.assertTrue(result['forest_used'])
        self.assertEqual(result['water']['type'], AnomalyEvent.Type.NORMAL)
        self.assertEqual(result['water']['source'], AnomalyEvent.Source.RULES)
        self.assertEqual(AnomalyEvent.objects.filter(home=house, resource=AnomalyEvent.Resource.WATER).count(), 0)

    def test_the_page_logs_the_alert_and_the_autopilot_close(self):
        owner = citizen('anomaly.page')
        house = home_for(owner, name='Page')
        self.client.force_login(owner)
        page = self.client.get(f'/homes/{house.pk}/anomalies/')
        self.assertContains(page, 'its own baseline')
        self.assertContains(page, 'Autopilot is off')
        self.assertContains(page, 'Open')
        checked = self.client.post(f'/homes/{house.pk}/anomalies/check/', {
            'water_liters_per_hour': '12',
            'energy_watts': '90',
            'temperature_c': '24',
            'hour': '14',
            'tank_percent': '60',
            'tank_previous_percent': '60',
        })
        self.assertRedirects(checked, f'/homes/{house.pk}/anomalies/')
        house.refresh_from_db()
        self.assertTrue(house.water_valve_open)
        follow = self.client.get(f'/homes/{house.pk}/anomalies/')
        self.assertContains(follow, 'Critical abnormal consumption')
        self.assertContains(follow, 'open → open')
        self.client.post(f'/homes/{house.pk}/anomalies/autopilot/', {'enabled': 'on'})
        self.client.post(f'/homes/{house.pk}/anomalies/check/', {
            'water_liters_per_hour': '12',
            'energy_watts': '90',
            'temperature_c': '24',
            'hour': '14',
            'tank_percent': '60',
            'tank_previous_percent': '60',
        })
        house.refresh_from_db()
        self.assertFalse(house.water_valve_open)
        logged = self.client.get(f'/homes/{house.pk}/anomalies/')
        self.assertContains(logged, 'Autopilot closed the water valve')
        self.assertContains(logged, 'open → closed')

        other = citizen('anomaly.other')
        self.client.force_login(other)
        hidden = self.client.get(f'/homes/{house.pk}/anomalies/')
        self.assertEqual(hidden.status_code, 404)
