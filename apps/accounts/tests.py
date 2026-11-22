from django.contrib.auth import get_user_model

from django.core import mail
from django.test import TestCase

from apps.accounts.models import User
from apps.farms.models import Farm
from apps.homes.models import Home

PASSWORD = 'Kizuna-home-2026'


def make_user(username, role):
    return get_user_model().objects.create_user(
        username=username,
        password=PASSWORD,
        email=f'{username}@example.com',
        role=role,
    )


class UserRoleTests(TestCase):
    def test_default_role_is_citizen(self):
        user = get_user_model().objects.create_user(
            username='citizen-default',
            password=PASSWORD,
        )
        self.assertEqual(user.role, User.Role.CITIZEN)

    def test_superuser_is_admin_and_password_is_hashed(self):
        user = get_user_model().objects.create_superuser(
            'operator',
            'operator@example.com',
            PASSWORD,
        )
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith('pbkdf2_'))


class AuthenticationTests(TestCase):
    def test_register_logs_in_at_once_and_hashes_password(self):
        response = self.client.post('/accounts/register/', {
            'username': 'citizen1',
            'first_name': 'Citizen',
            'last_name': 'One',
            'email': 'citizen1@example.com',
            'role': User.Role.CITIZEN,
            'password1': PASSWORD,
            'password2': PASSWORD,
        })
        self.assertRedirects(response, '/homes/new/')
        user = get_user_model().objects.get(username='citizen1')
        self.assertEqual(user.role, User.Role.CITIZEN)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertNotIn(PASSWORD, user.password)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(len(mail.outbox), 0)

    def test_public_registration_rejects_admin_role(self):
        response = self.client.post('/accounts/register/', {
            'username': 'not-admin',
            'email': 'not-admin@example.com',
            'role': User.Role.ADMIN,
            'password1': PASSWORD,
            'password2': PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='not-admin').exists())

    def test_login_logout_and_profile(self):
        make_user('citizen1', User.Role.CITIZEN)
        login_response = self.client.post('/accounts/login/', {
            'username': 'citizen1',
            'password': PASSWORD,
        })
        self.assertRedirects(login_response, '/dashboard/')

        profile = self.client.post('/accounts/profile/', {
            'action': 'profile',
            'first_name': 'Sam',
            'last_name': 'User',
            'email': 'sam.user@example.com',
        })
        self.assertRedirects(profile, '/accounts/profile/')
        user = get_user_model().objects.get(username='citizen1')
        self.assertEqual(user.first_name, 'Sam')
        self.assertEqual(user.email, 'sam.user@example.com')

        changed = self.client.post('/accounts/profile/', {
            'action': 'password',
            'old_password': PASSWORD,
            'new_password1': 'Kizuna-new-2026',
            'new_password2': 'Kizuna-new-2026',
        })
        self.assertRedirects(changed, '/accounts/profile/')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Kizuna-new-2026'))
        self.assertEqual(self.client.get('/accounts/profile/').status_code, 200)

        logged_out = self.client.post('/accounts/logout/')
        self.assertRedirects(logged_out, '/')
        self.assertRedirects(self.client.get('/dashboard/'), '/accounts/login/?next=/dashboard/')


class RoleAccessTests(TestCase):
    def test_citizen_manages_a_home_and_cannot_open_a_farm(self):
        citizen = make_user('citizen1', User.Role.CITIZEN)
        self.client.force_login(citizen)
        created = self.client.post('/homes/new/', {
            'name': 'House 1',
            'address': 'Tunis',
            'area_m2': '90',
            'residents': 4,
            'bedrooms': 2,
            'bathrooms': 1,
        })
        home = Home.objects.get()
        self.assertRedirects(created, f'/homes/{home.pk}/')
        self.assertEqual(home.owner, citizen)
        self.assertEqual(home.residents, 4)
        self.assertEqual(self.client.get('/farms/').status_code, 403)
        dashboard = self.client.get('/dashboard/')
        self.assertContains(dashboard, 'Simulation')
        self.assertContains(dashboard, 'Passeport ressources')
        self.assertNotContains(dashboard, 'Irrigation')

    def test_citizen_cannot_edit_another_home(self):
        owner = make_user('citizen1', User.Role.CITIZEN)
        other = make_user('citizen2', User.Role.CITIZEN)
        home = Home.objects.create(owner=owner, name='Private house', residents=2)
        self.client.force_login(other)
        self.assertNotContains(self.client.get('/homes/'), 'Private house')
        self.assertEqual(self.client.get(f'/homes/{home.pk}/edit/').status_code, 404)

    def test_farmer_manages_a_farm_and_cannot_open_homes(self):
        farmer = make_user('farmer1', User.Role.FARMER)
        self.client.force_login(farmer)
        created = self.client.post('/farms/new/', {
            'name': 'North field',
            'location': 'Tunis',
            'area_m2': '2000',
            'soil_type': 'loam',
            'irrigation_type': 'drip',
            'crop_type': 'olive',
            'tank_capacity_liters': '5000',
            'solar_capacity_watts': '3000',
            'latitude': '36.806500',
            'longitude': '10.181500',
        })
        farm = Farm.objects.get()
        self.assertRedirects(created, f'/farms/{farm.pk}/')
        self.assertEqual(farm.owner, farmer)
        dashboard = self.client.get('/dashboard/')
        self.assertContains(dashboard, 'Simulation')
        self.assertContains(dashboard, 'umidité du sol')
        self.assertNotContains(dashboard, 'Passeport')
        blocked = self.client.get('/homes/')
        self.assertContains(blocked, 'pas pour votre compte', status_code=403)

    def test_buyer_opens_the_market_and_cannot_open_homes(self):
        buyer = make_user('buyer1', User.Role.BUSINESS)
        self.client.force_login(buyer)
        self.assertEqual(self.client.get('/market/').status_code, 200)
        self.assertEqual(self.client.get('/homes/').status_code, 403)
        self.assertNotContains(self.client.get('/dashboard/'), 'Mon entreprise')

    def test_admin_can_open_every_section(self):
        admin = make_user('admin1', User.Role.ADMIN)
        self.client.force_login(admin)
        for path in (
            '/homes/',
            '/homes/appliances/',
            '/sensors/home/',
            '/resources/passports/',
            '/farms/',
            '/farms/crops/',
            '/farms/irrigation/',
            '/sensors/farm/',
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)


class RegistrationTests(TestCase):
    """Plus de confirmation par e-mail ni par SMS : le compte est actif tout de suite."""

    def _register(self, role=User.Role.CITIZEN, username='amira', email='amira@example.com'):
        return self.client.post('/accounts/register/', {
            'username': username,
            'first_name': 'Amira',
            'email': email,
            'role': role,
            'password1': PASSWORD,
            'password2': PASSWORD,
        })

    def test_new_account_can_log_in_again(self):
        self._register()
        self.client.logout()
        response = self.client.post('/accounts/login/', {'username': 'amira', 'password': PASSWORD})
        self.assertRedirects(response, '/dashboard/')

    def test_farmer_signs_up_with_phone_and_lands_on_farm_form(self):
        response = self.client.post('/accounts/register/', {
            'username': 'hedi', 'first_name': 'Hédi', 'role': User.Role.FARMER,
            'phone': '98 123 456', 'password1': PASSWORD, 'password2': PASSWORD,
        })
        self.assertRedirects(response, '/farms/new/')
        user = get_user_model().objects.get(username='hedi')
        self.assertEqual(user.phone, '+21698123456')
        self.assertEqual(user.email, '')
        self.assertEqual(len(mail.outbox), 0)
        self.client.logout()
        login = self.client.post('/accounts/login/', {'username': '+216 98 123 456', 'password': PASSWORD})
        self.assertRedirects(login, '/dashboard/')

    def test_public_registration_offers_no_business_role(self):
        response = self._register(role=User.Role.BUSINESS, username='societe', email='societe@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='societe').exists())
        self.assertNotContains(self.client.get('/accounts/register/'), 'Entreprise')

    def test_business_pages_are_gone(self):
        for url in ('/businesses/', '/businesses/equipment/', '/resources/consumption/'):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_confirmation_pages_are_gone(self):
        for url in ('/accounts/register/check-email/', '/accounts/register/verify-phone/', '/accounts/confirm/resend/'):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_farmer_needs_valid_unique_phone(self):
        bad = self.client.post('/accounts/register/', {
            'username': 'hedi', 'role': User.Role.FARMER, 'phone': '123',
            'password1': PASSWORD, 'password2': PASSWORD,
        })
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, 'Numéro invalide')
        self.client.post('/accounts/register/', {
            'username': 'hedi', 'role': User.Role.FARMER, 'phone': '98123456',
            'password1': PASSWORD, 'password2': PASSWORD,
        })
        self.client.logout()
        twice = self.client.post('/accounts/register/', {
            'username': 'hedi2', 'role': User.Role.FARMER, 'phone': '+21698123456',
            'password1': PASSWORD, 'password2': PASSWORD,
        })
        self.assertContains(twice, 'déjà ce numéro')

    def test_citizen_still_needs_email(self):
        response = self.client.post('/accounts/register/', {
            'username': 'sans', 'role': User.Role.CITIZEN,
            'password1': PASSWORD, 'password2': PASSWORD,
        })
        self.assertContains(response, 'Entrez votre adresse e-mail')

    def test_duplicate_email_is_refused(self):
        make_user('first', User.Role.CITIZEN)
        response = self._register(username='second', email='FIRST@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='second').exists())


class CsrfFailureTests(TestCase):
    def setUp(self):
        from django.test import Client
        self.client = Client(enforce_csrf_checks=True)
        make_user('amira', User.Role.CITIZEN)
        self.client.login(username='amira', password=PASSWORD)

    def test_logout_with_stale_token_still_logs_out(self):
        self.client.get('/dashboard/')
        response = self.client.post('/accounts/logout/', {'csrfmiddlewaretoken': 'x' * 64})
        self.assertRedirects(response, '/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_other_forms_show_a_clear_page(self):
        self.client.get('/accounts/profile/')
        response = self.client.post('/accounts/profile/', {'csrfmiddlewaretoken': 'x' * 64, 'action': 'profile'})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Cette page a expiré', status_code=403)
        self.assertIn('_auth_user_id', self.client.session)
