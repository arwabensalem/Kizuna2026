from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.actuators.engine import ensure_actuators
from apps.actuators.models import Actuator
from apps.farms.models import Farm, IrrigationSystem
from apps.homes.models import Home
from apps.weather.models import CollectionSystem, WeatherTimeline
from apps.weather.scenarios import SCENARIOS
from apps.weather.services import advance_timeline, ensure_collection, start_timeline


def citizen(username):
    return User.objects.create_user(username=username, password='Kizuna-weather-2026', role=User.Role.CITIZEN)


def make_home(owner, mode='assist'):
    return Home.objects.create(
        owner=owner,
        name='Weather house',
        residents=2,
        area_m2=90,
        autonomy_mode=mode,
        autopilot_enabled=mode != 'assist',
    )


class WeatherEngineTests(TestCase):
    def test_scenarios_carry_the_six_simulated_variables(self):
        for name, spec in SCENARIOS.items():
            self.assertEqual(len(spec['hours']), 12, name)
            for row in spec['hours']:
                self.assertEqual(len(row), 6, name)

    def test_rain_in_four_hours_prepares_and_then_fills_the_tank(self):
        owner = citizen('weather.rain')
        house = make_home(owner, mode='smart')
        pump = ensure_actuators(house, None)[Actuator.Kind.IRRIGATION_PUMP]
        pump.state = 'on'
        pump.authorized = True
        pump.save(update_fields=['state', 'authorized'])
        system = ensure_collection(house, None)
        system.roof_area_m2 = Decimal('100.0')
        system.capture_share = Decimal('0.80')
        system.tank_capacity_liters = 2000
        system.tank_liters = Decimal('800.0')
        system.authorized = True
        system.save()

        timeline, actions, recovery = start_timeline(house, None, 'rain_in_4_hours')
        self.assertEqual(timeline.mode, WeatherTimeline.Mode.RAIN_PREPARATION)
        self.assertEqual(timeline.source, 'simulation')
        self.assertIsNone(recovery)
        self.assertEqual(
            [action.action for action in actions],
            ['suspend_irrigation', 'prepare_collection', 'check_tank', 'prepare_collection_system'],
        )
        for action in actions:
            self.assertEqual(action.mode, 'rain_preparation')
            self.assertIn('Rain expected in 4 hours', action.reason)
            self.assertTrue(action.actuator)
            self.assertTrue(action.previous_state)
            self.assertTrue(action.new_state)
            self.assertIsNotNone(action.created_at)
        self.assertEqual(actions[0].previous_state, 'on')
        self.assertEqual(actions[0].new_state, 'off')
        self.assertEqual(actions[3].new_state, 'prepared')
        pump.refresh_from_db()
        self.assertEqual(pump.state, 'off')
        system.refresh_from_db()
        self.assertEqual(system.tank_liters, Decimal('800.0'))
        self.assertEqual(timeline.hours.get(hour=4).rainfall_mm, Decimal('4.0'))
        self.assertEqual(timeline.hours.get(hour=3).rainfall_mm, Decimal('0.0'))

        for _hour in range(3):
            timeline, dry_actions, dry_recovery = advance_timeline(timeline)
            self.assertEqual(dry_actions, [])
            self.assertIsNone(dry_recovery)
        timeline, wet_actions, wet = advance_timeline(timeline)
        self.assertEqual(timeline.hour, 4)
        self.assertEqual(timeline.mode, WeatherTimeline.Mode.COLLECTING)
        self.assertEqual(wet.recovered_liters, Decimal('320.0'))
        self.assertEqual(wet.tank_before, Decimal('800.0'))
        self.assertEqual(wet.tank_after, Decimal('1120.0'))
        self.assertEqual(wet_actions[-1].action, 'collect_rainwater')
        self.assertEqual(wet_actions[-1].previous_state, '800.0 L')
        self.assertEqual(wet_actions[-1].new_state, '1120.0 L')
        self.assertIn('rainwater system', wet_actions[-1].reason)
        system.refresh_from_db()
        self.assertEqual(system.tank_liters, Decimal('1120.0'))

    def test_unauthorized_collection_does_not_change_the_tank(self):
        owner = citizen('weather.lock')
        house = make_home(owner, mode='autopilot')
        system = ensure_collection(house, None)
        system.tank_liters = Decimal('800.0')
        system.save(update_fields=['tank_liters'])
        timeline, actions, _recovery = start_timeline(house, None, 'rain_now')
        self.assertEqual(actions[3].action, 'prepare_collection_system')
        self.assertEqual(actions[3].previous_state, 'not prepared')
        self.assertEqual(actions[3].new_state, 'not prepared')
        self.assertIn('not authorized', actions[3].reason)
        self.assertEqual(actions[-1].previous_state, actions[-1].new_state)
        system.refresh_from_db()
        self.assertEqual(system.tank_liters, Decimal('800.0'))
        self.assertFalse(system.prepared)
        self.assertEqual(timeline.recoveries.count(), 0)

    def test_assist_does_not_switch_the_pump_off(self):
        owner = citizen('weather.assist')
        house = make_home(owner, mode='assist')
        pump = ensure_actuators(house, None)[Actuator.Kind.IRRIGATION_PUMP]
        pump.state = 'on'
        pump.authorized = True
        pump.save(update_fields=['state', 'authorized'])
        _timeline, actions, _recovery = start_timeline(house, None, 'rain_in_4_hours')
        self.assertEqual(actions[0].previous_state, 'on')
        self.assertEqual(actions[0].new_state, 'on')
        self.assertIn('Assist mode only alerts', actions[0].reason)
        pump.refresh_from_db()
        self.assertEqual(pump.state, 'on')

    def test_a_full_tank_keeps_only_what_fits(self):
        owner = citizen('weather.full')
        house = make_home(owner)
        system = ensure_collection(house, None)
        system.roof_area_m2 = Decimal('100.0')
        system.capture_share = Decimal('0.80')
        system.tank_capacity_liters = 1000
        system.tank_liters = Decimal('900.0')
        system.authorized = True
        system.save()
        _timeline, _actions, recovery = start_timeline(house, None, 'rain_now')
        self.assertEqual(recovery.offered_liters, Decimal('400.0'))
        self.assertEqual(recovery.recovered_liters, Decimal('100.0'))
        self.assertEqual(recovery.tank_after, Decimal('1000.0'))
        system.refresh_from_db()
        self.assertEqual(system.tank_liters, Decimal('1000.0'))

    def test_a_clear_day_does_not_prepare_or_collect(self):
        owner = citizen('weather.clear')
        house = make_home(owner)
        system = ensure_collection(house, None)
        before = system.tank_liters
        timeline, actions, recovery = start_timeline(house, None, 'clear_day')
        self.assertEqual(actions, [])
        self.assertIsNone(recovery)
        self.assertEqual(timeline.mode, WeatherTimeline.Mode.STANDBY)
        timeline, later, later_recovery = advance_timeline(timeline)
        self.assertEqual(later, [])
        self.assertIsNone(later_recovery)
        system.refresh_from_db()
        self.assertEqual(system.tank_liters, before)

    def test_a_farm_pump_stops_and_the_collection_uses_the_farm_tank(self):
        owner = citizen('weather.farm')
        farm = Farm.objects.create(
            owner=owner,
            name='Weather grove',
            area_m2=1200,
            tank_capacity_liters=8000,
            autonomy_mode='autopilot',
        )
        irrigation = IrrigationSystem.objects.create(
            farm=farm,
            name='Drip line',
            method=Farm.IrrigationType.DRIP,
            is_active=True,
        )
        pump = ensure_actuators(None, farm)[Actuator.Kind.IRRIGATION_PUMP]
        pump.state = 'on'
        pump.authorized = True
        pump.save(update_fields=['state', 'authorized'])
        system = ensure_collection(None, farm)
        self.assertEqual(system.roof_area_m2, Decimal('80.0'))
        self.assertEqual(system.tank_capacity_liters, 8000)
        system.authorized = True
        system.save(update_fields=['authorized'])
        start_timeline(None, farm, 'rain_in_4_hours')
        pump.refresh_from_db()
        irrigation.refresh_from_db()
        self.assertEqual(pump.state, 'off')
        self.assertFalse(irrigation.is_active)

    def test_the_page_shows_preparation_then_recovered_water(self):
        owner = citizen('weather.page')
        house = make_home(owner, mode='smart')
        self.client.force_login(owner)
        self.client.post('/weather/collection/', {
            'home': house.pk,
            'roof_area_m2': '100',
            'capture_share': '0.80',
            'tank_capacity_liters': '2000',
            'tank_liters': '800',
        })
        system = CollectionSystem.objects.get(home=house)
        started = self.client.post('/weather/start/', {
            'home': house.pk,
            'scenario': 'rain_in_4_hours',
        }, follow=True)
        self.assertContains(started, 'RAIN PREPARATION MODE')
        self.assertContains(started, 'Rain expected in 4 hours')
        self.assertContains(started, 'est une simulation')
        self.assertContains(started, 'suspend_irrigation')
        self.assertContains(started, 'prepare_collection')
        self.assertContains(started, 'check_tank')
        self.assertContains(started, 'prepare_collection_system')
        self.assertContains(started, '+ 0.0 L recovered')
        self.assertContains(started, 'Jumeau numérique')
        self.assertContains(started, 'Toit')
        self.assertContains(started, 'Risque de pluie')
        self.assertContains(started, 'Ensoleillement')
        self.client.post('/weather/authorize/', {
            'home': house.pk,
            'collection': system.pk,
            'authorized': 'on',
        })
        response = None
        timeline = WeatherTimeline.objects.get(home=house)
        for _hour in range(4):
            response = self.client.post('/weather/advance/', {
                'home': house.pk,
                'timeline': timeline.pk,
            }, follow=True)
        self.assertContains(response, '+ 320.0 L recovered')
        self.assertContains(response, '1120.0 / 2000 L')
        self.assertContains(response, 'collect_rainwater')
        self.assertContains(response, '800.0 L → 1120.0 L')

    def test_another_citizen_cannot_start_this_home(self):
        owner = citizen('weather.owner')
        other = citizen('weather.other')
        house = make_home(owner)
        self.client.force_login(other)
        response = self.client.post('/weather/start/', {
            'home': house.pk,
            'scenario': 'clear_day',
        })
        self.assertEqual(response.status_code, 404)
        self.assertEqual(WeatherTimeline.objects.count(), 0)
