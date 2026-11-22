from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.farms.models import Crop, Farm
from apps.homes.models import Appliance, Home
from apps.marketplace.models import BuyerRequest, Product

PASSWORD = 'Kizuna-demo-2026'


class SeedDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)

    def test_everything_needed_for_the_jury_exists(self):
        self.assertTrue(User.objects.get(username='kizuna.admin').is_superuser)
        self.assertEqual(Home.objects.count(), 3)
        self.assertGreaterEqual(Appliance.objects.count(), 20)
        self.assertEqual(Farm.objects.count(), 5)
        self.assertGreaterEqual(Crop.objects.count(), 13)
        self.assertGreaterEqual(Product.objects.count(), 7)
        self.assertGreaterEqual(BuyerRequest.objects.count(), 7)

    def test_running_twice_creates_nothing_new(self):
        before = (Home.objects.count(), Farm.objects.count(), Product.objects.count(), BuyerRequest.objects.count())
        call_command('seed_demo', verbosity=0)
        after = (Home.objects.count(), Farm.objects.count(), Product.objects.count(), BuyerRequest.objects.count())
        self.assertEqual(before, after)

    def test_demo_accounts_log_in_and_pages_open(self):
        logins = {
            'amira': ['/dashboard/', '/homes/', '/twin/'],
            '+216 98 100 205': ['/farms/', '/farms/crops/', '/market/'],
            'tokyo.buyer': ['/market/', '/market/offers/'],
        }
        for username, pages in logins.items():
            self.client.logout()
            response = self.client.post('/accounts/login/', {'username': username, 'password': PASSWORD})
            self.assertEqual(response.status_code, 302, username)
            for url in pages:
                self.assertEqual(self.client.get(url).status_code, 200, f'{username} {url}')
        self.client.logout()
        self.assertEqual(
            self.client.post('/accounts/login/', {'username': 'kizuna.admin', 'password': 'Kizuna-admin-2026'}).status_code, 302,
        )
        self.assertEqual(self.client.get('/accounts/users/').status_code, 200)

    def test_amira_sees_ac_and_fridge_alerts(self):
        self.client.login(username='amira', password=PASSWORD)
        home = Home.objects.get(owner__username='amira')
        page = self.client.get(f'/homes/{home.pk}/')
        self.assertContains(page, 'trop bas')
        self.assertContains(page, 'anormalement')
