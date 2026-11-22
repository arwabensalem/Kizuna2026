from django.test import TestCase

from apps.accounts.models import User
from apps.actuators.models import Actuator
from apps.digital_twin.state import build_twin_state
from apps.homes.models import Appliance, Home, Room
from apps.weather.models import CollectionSystem, WeatherHour, WeatherTimeline


def citizen(username):
    return User.objects.create_user(username=username, password='Kizuna-twin-2026', role=User.Role.CITIZEN)


def make_home(owner, valve_open=True):
    return Home.objects.create(
        owner=owner,
        name='Twin house',
        residents=2,
        area_m2=80,
        bedrooms=1,
        bathrooms=1,
        has_living_room=True,
        water_valve_open=valve_open,
    )


def flow(state, key):
    return next(item for item in state['flows'] if item['id'] == key)


class TwinStateTests(TestCase):
    def test_anonymous_requests_are_blocked(self):
        owner = citizen('twin.owner')
        house = make_home(owner)
        response = self.client.get(f'/api/twin/homes/{house.pk}/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['detail'], 'Authentication required.')

    def test_another_citizen_cannot_read_the_home(self):
        owner = citizen('twin.one')
        other = citizen('twin.two')
        house = make_home(owner)
        self.client.force_login(other)
        response = self.client.get(f'/api/twin/homes/{house.pk}/')
        self.assertEqual(response.status_code, 404)

    def test_lights_valve_and_pump_follow_the_home(self):
        owner = citizen('twin.lights')
        house = make_home(owner, valve_open=True)
        room = Room.objects.create(home=house, name='Bath', kind=Room.Kind.BATHROOM)
        living = Room.objects.create(home=house, name='Lounge', kind=Room.Kind.LIVING_ROOM)
        lights = Appliance.objects.create(
            home=house,
            room=living,
            kind=Appliance.Kind.LIGHTS,
            power_watts=60,
            is_active=False,
        )
        Appliance.objects.create(
            home=house,
            room=room,
            kind=Appliance.Kind.WATER_HEATER,
            power_watts=1500,
            water_liters_per_hour=8,
            is_active=True,
        )
        Actuator.objects.create(
            home=house,
            kind=Actuator.Kind.IRRIGATION_PUMP,
            state='on',
            authorized=True,
        )
        state = build_twin_state(house)
        lounge = next(item for item in state['rooms'] if item['name'] == 'Lounge')
        self.assertFalse(lounge['lights_on'])
        self.assertTrue(state['valve']['open'])
        self.assertTrue(state['pump']['running'])
        self.assertTrue(flow(state, 'water_bathroom')['active'])
        self.assertEqual(flow(state, 'water_bathroom')['amount'], 8)
        self.assertTrue(flow(state, 'water_garden')['active'])
        self.assertTrue(flow(state, 'battery_pump')['active'])
        self.assertEqual(flow(state, 'battery_pump')['from'], 'battery')
        self.assertEqual(flow(state, 'battery_pump')['to'], 'pump')

        lights.is_active = True
        lights.save(update_fields=['is_active'])
        lit = build_twin_state(house)
        lounge = next(item for item in lit['rooms'] if item['name'] == 'Lounge')
        self.assertTrue(lounge['lights_on'])

        house.water_valve_open = False
        house.save(update_fields=['water_valve_open'])
        closed = build_twin_state(house)
        self.assertFalse(closed['valve']['open'])
        self.assertFalse(flow(closed, 'water_bathroom')['active'])
        self.assertFalse(flow(closed, 'water_garden')['active'])
        self.assertTrue(flow(closed, 'battery_pump')['active'])

    def test_rain_fills_the_stored_tank_and_the_roof_flow(self):
        owner = citizen('twin.rain')
        house = make_home(owner)
        CollectionSystem.objects.create(
            home=house,
            roof_area_m2=80,
            capture_share='0.80',
            tank_capacity_liters=2000,
            tank_liters='500.0',
            prepared=True,
            authorized=True,
        )
        timeline = WeatherTimeline.objects.create(
            home=house,
            scenario='rain_now',
            hour=0,
            mode=WeatherTimeline.Mode.COLLECTING,
            source='simulation',
        )
        WeatherHour.objects.create(
            timeline=timeline,
            hour=0,
            temperature_c='20.0',
            humidity_percent=86,
            rainfall_probability=95,
            rainfall_mm='4.0',
            solar_radiation_wm2=120,
            wind_kmh=18,
        )
        state = build_twin_state(house)
        self.assertTrue(state['simulated'])
        self.assertEqual(state['tank']['source'], 'collection')
        self.assertEqual(state['tank']['percent'], 25.0)
        self.assertEqual(state['tank']['liters'], 500.0)
        self.assertTrue(state['weather']['raining'])
        self.assertTrue(state['weather']['collecting'])
        self.assertTrue(flow(state, 'rain_roof')['active'])
        self.assertTrue(flow(state, 'roof_tank')['active'])
        self.assertEqual(flow(state, 'rain_roof')['from'], 'rain')
        self.assertEqual(flow(state, 'roof_tank')['to'], 'tank')
        self.assertEqual(state['solar']['watts'], 137)

    def test_unprepared_rain_does_not_enter_the_tank(self):
        owner = citizen('twin.drytank')
        house = make_home(owner)
        CollectionSystem.objects.create(
            home=house,
            roof_area_m2=80,
            capture_share='0.80',
            tank_capacity_liters=2000,
            tank_liters='500.0',
            prepared=False,
        )
        timeline = WeatherTimeline.objects.create(home=house, scenario='rain_now', hour=0, source='simulation')
        WeatherHour.objects.create(
            timeline=timeline,
            hour=0,
            temperature_c='20.0',
            humidity_percent=86,
            rainfall_probability=95,
            rainfall_mm='4.0',
            solar_radiation_wm2=700,
            wind_kmh=12,
        )
        state = build_twin_state(house)
        self.assertTrue(flow(state, 'rain_roof')['active'])
        self.assertFalse(flow(state, 'roof_tank')['active'])

    def test_the_page_points_at_the_module_and_the_api(self):
        owner = citizen('twin.page')
        house = make_home(owner)
        self.client.force_login(owner)
        response = self.client.get('/twin/')
        self.assertContains(response, 'Maison 3D vivante')
        self.assertContains(response, 'data-twin-root')
        self.assertContains(response, f'/api/twin/homes/{house.pk}/')
        self.assertContains(response, 'js/twin.js')
        self.assertContains(response, 'ni un modèle figé')
        self.assertContains(response, 'Maison 3D')
        self.assertContains(response, 'chambre, salle de bain, cuisine')
        api = self.client.get(f'/api/twin/homes/{house.pk}/')
        self.assertEqual(api.status_code, 200)
        body = api.json()
        self.assertIn('bathroom', [room['kind'] for room in body['rooms']])
        self.assertTrue(any(item['id'] == 'solar_home' for item in body['flows']))
        self.assertTrue(any(item['id'] == 'water_bathroom' for item in body['flows']))
