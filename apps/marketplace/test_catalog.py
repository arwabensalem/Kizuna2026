from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.marketplace.models import BuyerRequest, Product


class MarketplaceTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(
            username='olivier', password='Kizuna-market-2026', role=User.Role.FARMER,
        )
        self.buyer = User.objects.create_user(
            username='buyer', password='Kizuna-market-2026', role=User.Role.CITIZEN,
        )
        self.other = User.objects.create_user(
            username='other-farmer', password='Kizuna-market-2026', role=User.Role.FARMER,
        )
        self.stranger = User.objects.create_user(
            username='stranger', password='Kizuna-market-2026', role=User.Role.CITIZEN,
        )

    def listing(self, **extra):
        data = {
            'name': 'Chemlali olives',
            'category': Product.Category.OLIVE,
            'quantity': '40.00',
            'unit': Product.Unit.KG,
            'origin': 'Lafayette',
            'harvest_date': '2026-11-01',
            'availability': Product.Availability.AVAILABLE,
            'description': 'Early harvest from the home grove',
        }
        data.update(extra)
        return data

    def test_a_farmer_can_list_a_harvest(self):
        self.client.force_login(self.farmer)
        response = self.client.post(reverse('market:create'), self.listing())
        product = Product.objects.get()
        self.assertEqual(product.farmer, self.farmer)
        self.assertEqual(product.name, 'Chemlali olives')
        self.assertEqual(product.origin, 'Lafayette')
        self.assertRedirects(response, reverse('market:detail', args=[product.pk]))

    def test_a_buyer_cannot_create_a_listing(self):
        self.client.force_login(self.buyer)
        response = self.client.post(reverse('market:create'), self.listing())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Product.objects.count(), 0)

    def test_search_and_category_filter(self):
        self.client.force_login(self.farmer)
        self.client.post(reverse('market:create'), self.listing())
        self.client.post(reverse('market:create'), self.listing(
            name='Durum wheat',
            category=Product.Category.GRAIN,
            origin='Sfax',
        ))
        self.client.get(reverse('market:board'))
        self.client.force_login(self.buyer)
        found = self.client.get(reverse('market:board'), {'q': 'Lafayette'})
        self.assertContains(found, 'Chemlali olives')
        self.assertNotContains(found, 'Durum wheat')
        grain = self.client.get(reverse('market:board'), {'category': Product.Category.GRAIN})
        self.assertContains(grain, 'Durum wheat')
        self.assertNotContains(grain, 'Chemlali olives')

    def test_detail_links_the_farmer_and_stores_a_quantity_request(self):
        self.client.force_login(self.farmer)
        self.client.post(reverse('market:create'), self.listing())
        product = Product.objects.get()
        self.client.force_login(self.buyer)
        page = self.client.get(reverse('market:detail', args=[product.pk]))
        self.assertContains(page, reverse('market:farmer', args=[self.farmer.pk]))
        self.assertContains(page, 'Demander une quantité')
        sent = self.client.post(reverse('market:detail', args=[product.pk]), {
            'quantity': '12.50',
            'message': 'I can collect on Friday.',
        })
        self.assertRedirects(sent, reverse('market:detail', args=[product.pk]))
        stored = BuyerRequest.objects.get()
        self.assertEqual(stored.buyer, self.buyer)
        self.assertEqual(stored.farmer, self.farmer)
        self.assertEqual(stored.product, product)
        self.assertEqual(str(stored.quantity), '12.50')
        product.refresh_from_db()
        self.assertEqual(str(product.quantity), '40.00')

    def test_a_farmer_cannot_request_their_own_listing(self):
        self.client.force_login(self.farmer)
        self.client.post(reverse('market:create'), self.listing())
        product = Product.objects.get()
        self.client.post(reverse('market:detail', args=[product.pk]), {'quantity': '1'})
        self.assertEqual(BuyerRequest.objects.count(), 0)

    def test_another_farmer_cannot_edit_the_listing(self):
        self.client.force_login(self.farmer)
        self.client.post(reverse('market:create'), self.listing())
        product = Product.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('market:edit', args=[product.pk])).status_code, 404)

    def test_contact_from_the_profile_is_visible_only_to_the_farmer(self):
        self.client.force_login(self.buyer)
        response = self.client.post(reverse('market:farmer', args=[self.farmer.pk]), {
            'message': 'Do you still have oil next week?',
        })
        self.assertRedirects(response, reverse('market:farmer', args=[self.farmer.pk]))
        stored = BuyerRequest.objects.get()
        self.assertIsNone(stored.product)
        self.assertEqual(stored.message, 'Do you still have oil next week?')
        self.client.force_login(self.stranger)
        hidden = self.client.get(reverse('market:farmer', args=[self.farmer.pk]))
        self.assertNotContains(hidden, 'Do you still have oil next week?')
        self.client.force_login(self.farmer)
        visible = self.client.get(reverse('market:farmer', args=[self.farmer.pk]))
        self.assertContains(visible, 'Do you still have oil next week?')
        self.assertContains(visible, 'buyer')

    def test_pages_require_login(self):
        self.assertEqual(self.client.get(reverse('market:board')).status_code, 302)
