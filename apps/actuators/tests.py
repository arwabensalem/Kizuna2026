from django.test import TestCase

from apps.accounts.models import User
from apps.actuators.engine import run_rules
from apps.actuators.models import Actuator, ActuatorAction
from apps.homes.models import Appliance, Home


def citizen(username):
    return User.objects.create_user(username=username, password='Kizuna-pilot-2026', role=User.Role.CITIZEN)


def make_home(owner, mode='assist', valve_open=True):
    return Home.objects.create(
        owner=owner,
        name='Pilot house',
        residents=2,
        area_m2=90,
        autonomy_mode=mode,
        autopilot_enabled=mode != 'assist',
        water_valve_open=valve_open,
    )


def situation(**kwargs):
    values = {
        'critical_leak': False,
        'crop_stress': 20,
        'tank_percent': 70,
        'rain_expected': False,
        'solar_watts': 200,
        'essential_watts': 300,
        'battery_percent': 60,
        'grid_available': True,
    }
    values.update(kwargs)
    return values


def kind(home, name):
    return Actuator.objects.get(home=home, kind=name)


class AutopilotRuleTests(TestCase):
    def test_assist_alerts_and_smart_closes_an_authorized_valve(self):
        owner = citizen('pilot.assist')
        house = make_home(owner, mode='assist')
        kind_valve = Actuator.Kind.WATER_VALVE
        run_rules(house, None, situation())
        valve = kind(house, kind_valve)
        valve.authorized = True
        valve.save(update_fields=['authorized'])

        assisted = run_rules(house, None, situation(critical_leak=True))
        leak = assisted[0]
        self.assertEqual(leak.action, 'alert')
        self.assertEqual(leak.mode, ActuatorAction.Mode.ASSIST)
        self.assertEqual(leak.previous_state, 'open')
        self.assertEqual(leak.new_state, 'open')
        self.assertIsNotNone(leak.created_at)
        self.assertEqual(leak.actuator_id, valve.pk)
        house.refresh_from_db()
        self.assertTrue(house.water_valve_open)

        house.autonomy_mode = Home.Autonomy.SMART
        house.autopilot_enabled = True
        house.save(update_fields=['autonomy_mode', 'autopilot_enabled'])
        closed = run_rules(house, None, situation(critical_leak=True))
        self.assertEqual(closed[0].action, 'close_valve')
        self.assertEqual(closed[0].mode, ActuatorAction.Mode.SMART)
        self.assertEqual(closed[0].previous_state, 'open')
        self.assertEqual(closed[0].new_state, 'closed')
        self.assertIn('Critical leak', closed[0].reason)
        house.refresh_from_db()
        self.assertFalse(house.water_valve_open)

    def test_an_unauthorized_actuator_is_not_moved(self):
        owner = citizen('pilot.lock')
        house = make_home(owner, mode='smart')
        run_rules(house, None, situation())
        warned = run_rules(house, None, situation(critical_leak=True))
        self.assertEqual(warned[0].action, 'alert')
        self.assertIn('not authorized', warned[0].reason)
        self.assertEqual(warned[0].previous_state, warned[0].new_state)
        house.refresh_from_db()
        self.assertTrue(house.water_valve_open)

    def test_smart_does_not_start_irrigation_and_autopilot_does(self):
        owner = citizen('pilot.crop')
        house = make_home(owner, mode='smart')
        run_rules(house, None, situation())
        pump = kind(house, Actuator.Kind.IRRIGATION_PUMP)
        pump.authorized = True
        pump.save(update_fields=['authorized'])
        held = run_rules(house, None, situation(crop_stress=80, tank_percent=70))
        self.assertEqual(held[0].action, 'alert')
        self.assertIn('Smart mode does not perform this action', held[0].reason)
        pump.refresh_from_db()
        self.assertEqual(pump.state, 'off')

        house.autonomy_mode = Home.Autonomy.AUTOPILOT
        house.save(update_fields=['autonomy_mode'])
        started = run_rules(house, None, situation(crop_stress=80, tank_percent=70))
        self.assertEqual(started[0].action, 'start_irrigation')
        self.assertEqual(started[0].previous_state, 'off')
        self.assertEqual(started[0].new_state, 'on')
        pump.refresh_from_db()
        self.assertEqual(pump.state, 'on')

        pump.authorized = False
        pump.state = 'off'
        pump.save(update_fields=['authorized', 'state'])
        blocked = run_rules(house, None, situation(crop_stress=80, tank_percent=70))
        self.assertEqual(blocked[0].action, 'alert')
        self.assertIn('not authorized', blocked[0].reason)
        pump.refresh_from_db()
        self.assertEqual(pump.state, 'off')

    def test_rain_suspends_irrigation_ahead_of_crop_stress(self):
        owner = citizen('pilot.rain')
        house = make_home(owner, mode='smart')
        run_rules(house, None, situation())
        pump = kind(house, Actuator.Kind.IRRIGATION_PUMP)
        pump.state = 'on'
        pump.authorized = True
        pump.save(update_fields=['state', 'authorized'])
        actions = run_rules(house, None, situation(rain_expected=True, crop_stress=90, tank_percent=80))
        self.assertEqual(actions[0].action, 'suspend_irrigation')
        self.assertEqual(actions[0].rule, 'rain')
        self.assertIn('Crop stress', actions[0].reason)
        self.assertEqual(actions[0].previous_state, 'on')
        self.assertEqual(actions[0].new_state, 'off')
        pump.refresh_from_db()
        self.assertEqual(pump.state, 'off')

    def test_outage_and_solar_surplus_follow_the_mode(self):
        owner = citizen('pilot.power')
        house = make_home(owner, mode='smart')
        Appliance.objects.create(home=house, kind=Appliance.Kind.TV, power_watts=100, is_active=True)
        Appliance.objects.create(home=house, kind=Appliance.Kind.REFRIGERATOR, power_watts=150, is_active=True)
        run_rules(house, None, situation())
        for name in (
            Actuator.Kind.NON_CRITICAL_LOADS,
            Actuator.Kind.BATTERY,
            Actuator.Kind.SOLAR_ALLOCATION,
        ):
            actuator = kind(house, name)
            actuator.authorized = True
            actuator.save(update_fields=['authorized'])

        outage = run_rules(house, None, situation(grid_available=False, solar_watts=2000, battery_percent=60))
        by_kind = {item.actuator.kind: item for item in outage}
        self.assertEqual(by_kind[Actuator.Kind.NON_CRITICAL_LOADS].action, 'shed_non_critical_loads')
        self.assertEqual(by_kind[Actuator.Kind.NON_CRITICAL_LOADS].new_state, 'shed')
        self.assertEqual(by_kind[Actuator.Kind.BATTERY].action, 'alert')
        self.assertIn('Smart mode', by_kind[Actuator.Kind.BATTERY].reason)
        self.assertFalse(Appliance.objects.get(home=house, kind=Appliance.Kind.TV).is_active)
        self.assertTrue(Appliance.objects.get(home=house, kind=Appliance.Kind.REFRIGERATOR).is_active)

        house.autonomy_mode = Home.Autonomy.AUTOPILOT
        house.save(update_fields=['autonomy_mode'])
        supplied = run_rules(house, None, situation(grid_available=False, battery_percent=60, solar_watts=2000))
        supplied_kinds = {item.actuator.kind: item for item in supplied}
        self.assertEqual(supplied_kinds[Actuator.Kind.BATTERY].new_state, 'discharging')
        self.assertEqual(supplied_kinds[Actuator.Kind.SOLAR_ALLOCATION].new_state, 'essential')

        stored = run_rules(house, None, situation(
            grid_available=True,
            solar_watts=2000,
            essential_watts=300,
            tank_percent=40,
        ))
        stored_kinds = {item.actuator.kind: item for item in stored}
        self.assertEqual(stored_kinds[Actuator.Kind.SOLAR_ALLOCATION].new_state, 'pumping')
        self.assertEqual(stored_kinds[Actuator.Kind.BATTERY].new_state, 'idle')

        charged = run_rules(house, None, situation(
            grid_available=True,
            solar_watts=2000,
            essential_watts=300,
            tank_percent=90,
        ))
        charged_kinds = {item.actuator.kind: item for item in charged}
        self.assertEqual(charged_kinds[Actuator.Kind.SOLAR_ALLOCATION].new_state, 'battery')
        self.assertEqual(charged_kinds[Actuator.Kind.BATTERY].action, 'charge_battery')
        self.assertEqual(charged_kinds[Actuator.Kind.BATTERY].new_state, 'charging')

    def test_the_page_shows_the_action_immediately(self):
        owner = citizen('pilot.page')
        house = make_home(owner, mode='assist')
        other = citizen('pilot.other')
        self.client.force_login(owner)
        page = self.client.get('/autopilot/')
        self.assertContains(page, 'Assist')
        self.assertContains(page, 'Smart')
        self.assertContains(page, 'Autopilot')
        valve = kind(house, Actuator.Kind.WATER_VALVE)
        self.client.post('/autopilot/mode/', {'home': house.pk, 'mode': 'smart'})
        self.client.post('/autopilot/authorize/', {
            'home': house.pk,
            'actuator': valve.pk,
            'authorized': 'on',
        })
        shown = self.client.post('/autopilot/run/', {
            'home': house.pk,
            'critical_leak': 'on',
            'crop_stress': '10',
            'tank_percent': '70',
            'battery_percent': '60',
            'solar_watts': '200',
            'essential_watts': '300',
            'grid_available': 'on',
        }, follow=True)
        self.assertContains(shown, 'Résultat du test')
        self.assertContains(shown, 'close_valve')
        self.assertContains(shown, 'open → closed')
        self.assertContains(shown, 'Critical leak')
        house.refresh_from_db()
        self.assertFalse(house.water_valve_open)

        self.client.force_login(other)
        hidden = self.client.post('/autopilot/mode/', {'home': house.pk, 'mode': 'assist'})
        self.assertEqual(hidden.status_code, 404)
