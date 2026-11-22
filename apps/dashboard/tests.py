from django.contrib.auth import get_user_model
from django.test import TestCase


class PhaseOneTests(TestCase):
    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'KIZUNA')
        self.assertContains(response, 'Créer mon compte')

    def test_dashboard_requires_login(self):
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/accounts/login/?next=/dashboard/')

    def test_dashboard_shows_the_jury_board(self):
        user = get_user_model().objects.create_user(
            username='board', password='Kizuna-board-2026',
        )
        self.client.force_login(user)
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        for heading in (
            'État général', 'Eau', 'Énergie', 'Alerte en cours',
            'Production solaire', 'Eau récupérée', 'Score de résilience',
            'Jumeau numérique', 'Échanges de ressources', 'Conseils de KIZUNA',
        ):
            self.assertContains(response, heading)
        self.assertContains(response, 'Lancer la journée de crise')
        self.assertContains(response, '/crisis/day/')
        for label in (
            'Ma maison', 'Maison 3D', 'Météo', 'Pilote automatique',
            'Passeport ressources', 'Réglages',
        ):
            self.assertContains(response, label)
        for hidden in (
            'Ma ferme', 'Mon entreprise', 'Et si… ?', 'Labo de crise',
            'Réseau de ressources', 'Ligue de résilience', 'Vendre et échanger',
        ):
            self.assertNotContains(response, hidden)

    def test_admin_keeps_the_shared_platform(self):
        user = get_user_model().objects.create_user(
            username='board-admin', password='Kizuna-board-2026', role='admin',
        )
        self.client.force_login(user)
        response = self.client.get('/dashboard/')
        for label in (
            'Ma maison', 'Ma ferme', 'Et si… ?', 'Labo de crise',
            'Réseau de ressources', 'Ligue de résilience', 'Tunisie', 'Vendre et échanger',
        ):
            self.assertContains(response, label)
        self.assertNotContains(response, 'Mon entreprise')

    def test_health(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'project': 'KIZUNA'})

    def test_admin_login_page(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nom d’utilisateur')
