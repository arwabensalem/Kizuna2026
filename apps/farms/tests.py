from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.farms.models import Crop, Farm, FarmSensor, FarmSolar, FarmTank, IrrigationSystem
from apps.farms.simulation import simulate_farm

PASSWORD = 'Kizuna-farm-2026'


def make_farmer(username='farmer1'):
    return User.objects.create_user(
        username=username,
        password=PASSWORD,
        email=f'{username}@example.com',
        role=User.Role.FARMER,
    )


def make_farm(owner, **overrides):
    values = {
        'name': 'North field',
        'location': 'Tunis',
        'area_m2': 1000,
        'soil_type': Farm.Soil.LOAM,
        'irrigation_type': Farm.IrrigationType.DRIP,
        'crop_type': Farm.CropType.OLIVE,
        'tank_capacity_liters': 5000,
        'solar_capacity_watts': 3000,
        'latitude': Decimal('36.806500'),
        'longitude': Decimal('10.181500'),
    }
    values.update(overrides)
    return Farm.objects.create(owner=owner, **values)


class FarmConfigurationTests(TestCase):
    def test_farmer_adds_crop_sensor_irrigation_tank_and_solar(self):
        farmer = make_farmer()
        self.client.force_login(farmer)
        farm = make_farm(farmer)
        self.assertContains(self.client.get(f'/farms/{farm.pk}/'), 'farm-map')
        crop = self.client.post('/farms/crops/new/', {
            'farm': farm.pk,
            'name': 'Chemlali',
            'area_m2': '400',
            'stage': Crop.Stage.FLOWERING,
        })
        self.assertRedirects(crop, f'/farms/{farm.pk}/')
        sensor = self.client.post('/farms/sensors/new/', {
            'farm': farm.pk,
            'kind': FarmSensor.Kind.SOIL_MOISTURE,
            'label': 'Row probe',
            'is_active': 'on',
        })
        self.assertRedirects(sensor, f'/farms/{farm.pk}/')
        system = self.client.post('/farms/irrigation/new/', {
            'farm': farm.pk,
            'name': 'Drip line',
            'method': 'drip',
            'flow_liters_per_hour': '120',
        })
        self.assertRedirects(system, f'/farms/{farm.pk}/')
        self.assertFalse(IrrigationSystem.objects.get().is_active)
        tank = self.client.post('/farms/tanks/new/', {
            'farm': farm.pk,
            'name': 'Cistern',
            'capacity_liters': '8000',
        })
        self.assertRedirects(tank, f'/farms/{farm.pk}/')
        solar = self.client.post('/farms/solar/new/', {
            'farm': farm.pk,
            'name': 'Roof array',
            'capacity_watts': '4000',
        })
        self.assertRedirects(solar, f'/farms/{farm.pk}/')
        self.assertEqual(FarmTank.objects.get().capacity_liters, 8000)
        self.assertEqual(FarmSolar.objects.get().capacity_watts, 4000)

    def test_other_farmer_cannot_open_the_farm(self):
        owner = make_farmer('farmer1')
        other = make_farmer('farmer2')
        farm = make_farm(owner, name='Private field')
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/farms/{farm.pk}/').status_code, 404)
        response = self.client.post('/farms/crops/new/', {
            'farm': farm.pk,
            'name': 'Stolen',
            'area_m2': '10',
            'stage': Crop.Stage.SEEDLING,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Crop.objects.count(), 0)

    def test_citizen_cannot_open_farms(self):
        citizen = User.objects.create_user(
            username='citizen1',
            password=PASSWORD,
            email='citizen1@example.com',
            role=User.Role.CITIZEN,
        )
        self.client.force_login(citizen)
        self.assertEqual(self.client.get('/farms/').status_code, 403)

    def test_simulated_dashboard_uses_the_farm_configuration(self):
        farmer = make_farmer()
        farm = make_farm(farmer)
        snapshot = simulate_farm(farm)
        self.assertEqual(snapshot['soil_moisture'], 58)
        self.assertEqual(snapshot['crop_status'], 'Stable')
        self.assertEqual(snapshot['tank_percent'], 56)
        self.assertEqual(snapshot['solar_watts'], 2160)
        self.assertEqual(snapshot['irrigation_status'], 'Configured')
        self.assertEqual(snapshot['water_liters_per_day'], 2200)
        self.assertEqual(snapshot['crop_stress'], 20)

        IrrigationSystem.objects.create(
            farm=farm,
            name='Drip line',
            method='drip',
            flow_liters_per_hour=100,
            is_active=False,
        )
        idle = simulate_farm(farm)
        self.assertEqual(idle['irrigation_status'], 'Idle')
        self.assertEqual(idle['soil_moisture'], 38)

        self.client.force_login(farmer)
        page = self.client.get('/dashboard/')
        self.assertContains(page, 'Simulation')
        self.assertContains(page, 'umidité du sol')
        self.assertContains(page, 'stress des cultures')
