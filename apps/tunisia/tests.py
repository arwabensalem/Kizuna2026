import json

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.homes.models import Home
from apps.simulation.services import current_state, reset_simulation
from apps.tunisia.index import build_tunisia
from apps.tunisia.places import GOVERNORATES, PILLARS


def pillar(result, name, key):
    governorate = next(item for item in result['governorates'] if item['name'] == name)
    return governorate['scores'][key]


class TunisiaIndexTests(TestCase):
    def setUp(self):
        reset_simulation(scenario='NORMAL')
        self.user = User.objects.create_user(username='map', password='Kizuna-map-2026')
        self.other = User.objects.create_user(username='neighbour', password='Kizuna-map-2026')
        Home.objects.create(owner=self.user, name='House 1')
        Home.objects.create(owner=self.user, name='Seaside', latitude='36.800000', longitude='10.180000')
        Home.objects.create(owner=self.other, name='Arwa', latitude='36.806500', longitude='10.181500')

    def test_every_governorate_has_the_five_scores(self):
        result = build_tunisia(self.user)
        self.assertEqual(len(result['governorates']), 24)
        self.assertTrue(result['simulated'])
        self.assertIn('not a national dataset', result['label'])
        for governorate in result['governorates']:
            for key in (*PILLARS, 'overall'):
                self.assertGreaterEqual(governorate['scores'][key], 0)
                self.assertLessEqual(governorate['scores'][key], 100)
            mean = round(sum(governorate['scores'][key] for key in PILLARS) / 4, 1)
            self.assertEqual(governorate['scores']['overall'], mean)
        national = result['country']['scores']
        self.assertEqual(result['country']['index'], national['overall'])
        for key in PILLARS:
            mean = round(sum(item['scores'][key] for item in result['governorates']) / 24, 1)
            self.assertEqual(national[key], mean)

    def test_the_same_clock_gives_the_same_index(self):
        first = build_tunisia(self.user)
        second = build_tunisia(self.user)
        self.assertEqual(first['country'], second['country'])
        self.assertEqual(first['governorates'], second['governorates'])

    def test_an_outage_lowers_energy(self):
        normal = build_tunisia(self.user)
        reset_simulation(scenario='POWER_OUTAGE')
        outage = build_tunisia(self.user)
        self.assertLess(pillar(outage, 'Sfax', 'energy'), pillar(normal, 'Sfax', 'energy'))
        self.assertLess(outage['country']['index'], normal['country']['index'])

    def test_rain_holds_more_water_than_drought(self):
        reset_simulation(scenario='DROUGHT')
        dry = build_tunisia(self.user)
        reset_simulation(scenario='HEAVY_RAIN')
        wet = build_tunisia(self.user)
        self.assertGreater(pillar(wet, 'Gabès', 'water'), pillar(dry, 'Gabès', 'water'))

    def test_home_a_reads_the_simulation_clock(self):
        state = current_state()
        result = build_tunisia(self.user)
        tunis = next(item for item in result['governorates'] if item['name'] == 'Tunis')
        nodes = tunis['city']['neighbourhood']['nodes']
        home = next(node for node in nodes if node['id'] == 'node:home-a')
        farm = next(node for node in nodes if node['kind'] == 'farm')
        self.assertEqual(home['scores']['water'], state['tanks']['home_percent'])
        self.assertEqual(farm['scores']['agriculture'], state['soil_moisture'])
        self.assertTrue(home['live'])
        self.assertEqual(tunis['city']['neighbourhood']['name'], 'Lafayette')
        sfax = next(item for item in result['governorates'] if item['name'] == 'Sfax')
        demo = next(node for node in sfax['city']['neighbourhood']['nodes'] if node['kind'] == 'home')
        self.assertFalse(demo['live'])
        self.assertEqual(demo['scores']['water'], sfax['scores']['water'])

    def test_governorates_in_one_band_are_not_copies(self):
        result = build_tunisia(self.user)
        self.assertNotEqual(pillar(result, 'Sousse', 'water'), pillar(result, 'Sfax', 'water'))

    def test_registered_sites_stay_with_their_owner(self):
        result = build_tunisia(self.user)
        placed = {site['name'] for site in result['registered']['placed']}
        unplaced = {site['name'] for site in result['registered']['unplaced']}
        self.assertEqual(placed, {'Seaside'})
        self.assertIn('House 1', unplaced)
        self.assertNotIn('Arwa', placed | unplaced)
        seaside = result['registered']['placed'][0]
        self.assertNotIn('scores', seaside)

    def test_boundaries_name_the_same_governorates(self):
        path = settings.BASE_DIR / 'static' / 'data' / 'tunisia-governorates.geojson'
        data = json.loads(path.read_text(encoding='utf-8'))
        names = {feature['properties']['shapeName'] for feature in data['features']}
        self.assertEqual(names, set(GOVERNORATES))


class TunisiaViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='atlas', password='Kizuna-map-2026')

    def test_page_requires_login(self):
        self.assertEqual(self.client.get(reverse('tunisia:map')).status_code, 302)

    def test_page_has_the_map_and_the_index(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('tunisia:map'))
        self.assertContains(response, 'id="tn-map"')
        self.assertContains(response, 'KIZUNA Resilience Index')
        self.assertContains(response, 'Zoom to Home A')
        self.assertContains(response, 'not a national dataset')

    def test_api_requires_login(self):
        response = self.client.get(reverse('tunisia_state'))
        self.assertEqual(response.status_code, 403)

    def test_api_returns_the_national_index(self):
        self.client.force_login(self.user)
        body = self.client.get(reverse('tunisia_state')).json()
        self.assertIn('index', body['country'])
        self.assertEqual(len(body['governorates']), 24)
        self.assertEqual(body['focus']['node'], 'node:home-a')
