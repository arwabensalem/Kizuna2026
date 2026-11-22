from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.homes.models import Appliance, Home, Room
from apps.homes.simulation import simulate_home

PASSWORD = 'Kizuna-home-2026'


def make_citizen(username='citizen1'):
    return User.objects.create_user(
        username=username,
        password=PASSWORD,
        email=f'{username}@example.com',
        role=User.Role.CITIZEN,
    )


class HomeConfigurationTests(TestCase):
    def test_citizen_adds_a_room_and_an_appliance(self):
        citizen = make_citizen()
        self.client.force_login(citizen)
        home = Home.objects.create(owner=citizen, name='House 1', residents=3, area_m2=100)
        room_response = self.client.post(f'/homes/{home.pk}/rooms/new/', {
            'name': 'Kitchen',
            'kind': Room.Kind.KITCHEN,
        })
        self.assertRedirects(room_response, f'/homes/{home.pk}/')
        room = Room.objects.get()
        appliance_response = self.client.post('/homes/appliances/new/', {
            'home': home.pk,
            'room': room.pk,
            'kind': Appliance.Kind.TV,
            'label': 'Living TV',
            'power_watts': 120,
            'water_liters_per_hour': '15',
            'is_active': 'on',
        })
        self.assertRedirects(appliance_response, f'/homes/{home.pk}/')
        appliance = Appliance.objects.get()
        self.assertEqual(appliance.water_liters_per_hour, Decimal('0'))
        self.assertTrue(appliance.is_active)
        self.assertEqual(appliance.room, room)

    def test_other_citizen_cannot_add_a_room(self):
        owner = make_citizen('citizen1')
        other = make_citizen('citizen2')
        home = Home.objects.create(owner=owner, name='Private house', residents=2)
        self.client.force_login(other)
        response = self.client.post(f'/homes/{home.pk}/rooms/new/', {
            'name': 'Office',
            'kind': Room.Kind.OTHER,
        })
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Room.objects.count(), 0)

    def test_simulated_dashboard_uses_active_appliances(self):
        citizen = make_citizen()
        home = Home.objects.create(
            owner=citizen,
            name='House 1',
            residents=4,
            area_m2=100,
            has_garden=False,
        )
        Appliance.objects.create(
            home=home,
            kind=Appliance.Kind.AC,
            power_watts=1000,
            is_active=True,
        )
        Appliance.objects.create(
            home=home,
            kind=Appliance.Kind.PUMP,
            power_watts=100,
            water_liters_per_hour=Decimal('10'),
            is_active=True,
        )
        Appliance.objects.create(
            home=home,
            kind=Appliance.Kind.TV,
            label='Spare TV',
            power_watts=80,
            is_active=False,
        )
        snapshot = simulate_home(home)
        self.assertEqual(snapshot['energy_watts'], 1100)
        self.assertEqual(snapshot['water_liters_per_hour'], 10)
        self.assertEqual(snapshot['solar_watts'], 1000)
        self.assertEqual(snapshot['active_count'], 2)
        self.client.force_login(citizen)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Simulation')
        self.assertContains(response, '1100')
        self.assertContains(response, 'Score de résilience')
        self.assertNotContains(response, 'Spare TV')
