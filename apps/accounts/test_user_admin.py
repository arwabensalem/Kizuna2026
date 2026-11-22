from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='chef', password='Kizuna-admin-2026', role=User.Role.ADMIN)
        self.farmer = User.objects.create_user(username='hedi', password='Kizuna-market-2026', role=User.Role.FARMER, phone='+21698123456')

    def test_only_admin_can_open_user_management(self):
        self.client.force_login(self.farmer)
        self.assertEqual(self.client.get(reverse('accounts:users')).status_code, 403)
        self.assertEqual(self.client.post(reverse('accounts:user_toggle', args=[self.admin.pk])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('accounts:users')).status_code, 302)

    def test_admin_sees_users_and_menu_link(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse('accounts:users'), {'role': 'farmer'})
        self.assertContains(page, '@hedi')
        self.assertNotContains(page, '@chef')
        self.assertContains(page, reverse('accounts:users'))

    def test_admin_creates_farmer_and_buyer_with_temporary_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('accounts:user_create'), {
            'username': 'oasis', 'first_name': 'Salem', 'last_name': 'Ben Ali', 'role': 'farmer',
            'email': '', 'phone': '97 111 222', 'is_active': 'on',
        }, follow=True)
        farmer = User.objects.get(username='oasis')
        self.assertEqual(farmer.phone, '+21697111222')
        self.assertTrue(farmer.email_verified)
        message = [str(m) for m in response.context['messages']][0]
        password = message.split('Mot de passe provisoire : ')[1].split(' ')[0]
        self.assertTrue(farmer.check_password(password))

        bad = self.client.post(reverse('accounts:user_create'), {
            'username': 'tokyo', 'role': 'business', 'email': '', 'phone': '', 'is_active': 'on',
        })
        self.assertContains(bad, "adresse e-mail de l&#x27;acheteur")
        self.client.post(reverse('accounts:user_create'), {
            'username': 'tokyo', 'role': 'business', 'email': 'buyer@example.jp', 'phone': '+81 3 1234 5678', 'is_active': 'on',
        })
        self.assertEqual(User.objects.get(username='tokyo').role, User.Role.BUSINESS)

    def test_duplicate_phone_is_refused(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('accounts:user_create'), {
            'username': 'copie', 'role': 'farmer', 'phone': '98123456', 'is_active': 'on',
        })
        self.assertContains(response, 'déjà ce numéro')

    def test_suspend_reactivate_and_self_protection(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('accounts:user_toggle', args=[self.farmer.pk]))
        self.farmer.refresh_from_db()
        self.assertFalse(self.farmer.is_active)
        self.client.post(reverse('accounts:user_toggle', args=[self.farmer.pk]))
        self.farmer.refresh_from_db()
        self.assertTrue(self.farmer.is_active)
        self.client.post(reverse('accounts:user_toggle', args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        response = self.client.post(reverse('accounts:user_edit', args=[self.admin.pk]), {
            'username': 'chef', 'role': 'citizen', 'email': '', 'phone': '', 'is_active': 'on',
        })
        self.assertContains(response, 'propre rôle administrateur')

    def test_admin_changes_role_and_resets_password(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('accounts:user_edit', args=[self.farmer.pk]), {
            'username': 'hedi', 'role': 'business', 'email': 'hedi@example.tn', 'phone': '', 'is_active': 'on',
        })
        self.farmer.refresh_from_db()
        self.assertEqual(self.farmer.role, User.Role.BUSINESS)
        old = self.farmer.password
        self.client.post(reverse('accounts:user_reset_password', args=[self.farmer.pk]))
        self.farmer.refresh_from_db()
        self.assertNotEqual(self.farmer.password, old)
