from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.marketplace import trade
from apps.marketplace.models import BuyerRequest, OfferMessage, Product


class TradeMathTests(SimpleTestCase):
    def test_currency_round_trip(self):
        self.assertEqual(trade.convert(Decimal('10'), 'JPY'), Decimal('480'))
        self.assertEqual(trade.to_tnd(Decimal('480'), 'JPY'), Decimal('10.00'))
        self.assertEqual(trade.money(Decimal('10'), 'JPY'), '480 ¥')
        self.assertEqual(trade.money(Decimal('10'), 'EUR'), '2,90 €')
        self.assertEqual(trade.clean_currency('xyz'), 'TND')

    def test_traditional_chain_ends_near_ten_times_and_shares_sum_to_100(self):
        steps = trade.traditional_chain(Decimal('10'), 'oil')
        self.assertEqual(steps[0]['key'], 'farmer')
        self.assertEqual(steps[-1]['price'], Decimal('100.00'))
        self.assertEqual(steps[0]['share'], 10)
        self.assertAlmostEqual(sum(s['share'] for s in steps), 100, delta=2)

    def test_direct_deal_gives_the_farmer_most_of_the_price(self):
        deal = trade.direct_deal(Decimal('16'), 'oil', 'jp_sea')
        self.assertGreater(deal['farmer_share'], 60)
        self.assertLess(deal['landed'], deal['shelf_price'])
        self.assertEqual(deal['traditional_share'], 10)

    def test_every_language_has_every_key(self):
        keys = set(trade.STRINGS['fr'])
        for lang in ('en', 'ja'):
            self.assertEqual(set(trade.STRINGS[lang]), keys, lang)

    def test_origin_coordinates_from_region_name(self):
        self.assertEqual(trade.origin_coords('Tozeur (Djérid)'), (33.92, 8.13))
        self.assertIsNone(trade.origin_coords('Nowhere'))


class DirectTradeTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(username='hedi', password='Kizuna-market-2026', role=User.Role.FARMER)
        self.buyer = User.objects.create_user(username='yuki', password='Kizuna-market-2026', role=User.Role.BUSINESS)
        self.stranger = User.objects.create_user(username='nosy', password='Kizuna-market-2026', role=User.Role.BUSINESS)
        self.product = Product.objects.create(
            farmer=self.farmer, name='Extra virgin olive oil', category='oil', quantity=Decimal('500'),
            unit='litre', origin='Sfax', harvest_date=date(2026, 11, 8), price_tnd=Decimal('16.00'),
            certifications='organic,aop', export_ready=True,
        )

    def test_japanese_buyer_view_shows_yen_and_japanese_labels(self):
        self.client.force_login(self.buyer)
        board = self.client.get(reverse('market:board'), {'lang': 'ja', 'cur': 'JPY'})
        self.assertContains(board, 'チュニジアの農家から直接購入')
        self.assertContains(board, '768 ¥')
        self.assertContains(board, '有機')
        detail = self.client.get(reverse('market:detail', args=[self.product.pk]))
        self.assertContains(detail, '産地パスポート')
        self.assertContains(detail, self.product.lot_code)
        self.assertContains(detail, '厚生労働省')

    def test_detail_shows_the_price_chain_in_french_by_default(self):
        self.client.force_login(self.buyer)
        page = self.client.get(reverse('market:detail', args=[self.product.pk]))
        self.assertContains(page, 'Où va votre argent ?')
        self.assertContains(page, 'Passeport d&#x27;origine')
        self.assertContains(page, 'bourse-map')

    def test_offer_in_yen_is_stored_in_dinars_and_starts_a_thread(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('market:detail', args=[self.product.pk]), {
            'quantity': '200', 'offer_price': '720', 'currency': 'JPY',
            'destination': 'jp_sea', 'incoterm': 'FOB', 'message': 'こんにちは',
        })
        offer = BuyerRequest.objects.get()
        self.assertEqual(offer.offer_price_tnd, Decimal('15.00'))
        self.assertEqual(offer.currency, 'JPY')
        self.assertEqual(offer.destination, 'jp_sea')
        self.assertEqual(offer.status, BuyerRequest.Status.PENDING)
        self.assertEqual(offer.thread.get().event, 'offer')

    def test_offer_without_price_uses_the_listed_price(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('market:detail', args=[self.product.pk]), {'quantity': '10'})
        self.assertEqual(BuyerRequest.objects.get().offer_price_tnd, Decimal('16.00'))

    def _offer(self):
        offer = BuyerRequest.objects.create(
            buyer=self.buyer, farmer=self.farmer, product=self.product, quantity=Decimal('100'),
            offer_price_tnd=Decimal('15.00'), destination='jp_sea',
        )
        OfferMessage.objects.create(offer=offer, author=self.buyer, price_tnd=offer.offer_price_tnd, event='offer')
        return offer

    def test_counter_offer_then_accept(self):
        offer = self._offer()
        url = reverse('market:offer', args=[offer.pk])
        self.client.force_login(self.buyer)
        self.client.post(url, {'action': 'accept'})
        offer.refresh_from_db()
        self.assertEqual(offer.status, BuyerRequest.Status.PENDING, 'a buyer cannot accept their own price')
        self.client.force_login(self.farmer)
        self.client.post(url, {'action': 'counter', 'price': '16', 'currency': 'TND', 'body': 'Organic certified'})
        offer.refresh_from_db()
        self.assertEqual(offer.status, BuyerRequest.Status.COUNTERED)
        self.assertEqual(offer.offer_price_tnd, Decimal('16.00'))
        self.client.force_login(self.buyer)
        self.client.post(url, {'action': 'accept'})
        offer.refresh_from_db()
        self.assertEqual(offer.status, BuyerRequest.Status.ACCEPTED)
        self.assertEqual(offer.total_tnd, Decimal('1600.0000'))
        self.client.post(url, {'action': 'decline'})
        offer.refresh_from_db()
        self.assertEqual(offer.status, BuyerRequest.Status.ACCEPTED)

    def test_only_the_two_parties_can_open_an_offer(self):
        offer = self._offer()
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(reverse('market:offer', args=[offer.pk])).status_code, 404)
        self.client.force_login(self.farmer)
        self.assertContains(self.client.get(reverse('market:offers')), 'Extra virgin olive oil')

    def test_fair_price_calculator(self):
        self.client.force_login(self.buyer)
        page = self.client.get(reverse('market:fair_price'), {'price': '10', 'category': 'oil', 'dest': 'fr'})
        self.assertContains(page, 'Calculateur de prix juste')
        self.assertContains(page, '10 000,00 TND')
        bad = self.client.get(reverse('market:fair_price'), {'price': 'abc'})
        self.assertEqual(bad.status_code, 200)

    def test_farmer_lists_with_price_farm_and_certifications(self):
        self.client.force_login(self.farmer)
        self.client.post(reverse('market:create'), {
            'name': 'Deglet Nour', 'category': 'fruit', 'quantity': '100', 'unit': 'kg',
            'price_tnd': '9', 'origin': 'Tozeur', 'harvest_date': '2026-10-28',
            'availability': 'available', 'export_ready': 'on', 'cert_organic': 'on', 'cert_halal': 'on',
        })
        product = Product.objects.get(name='Deglet Nour')
        self.assertEqual(product.certification_codes, ['organic', 'halal'])
        self.assertTrue(product.export_ready)

    def test_business_accounts_see_the_market_in_the_menu(self):
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(reverse('market:board')), 'Acheter en direct')


class SeedTests(TestCase):
    def test_seed_is_idempotent(self):
        call_command('seed_bourse', verbosity=0)
        count = Product.objects.count()
        call_command('seed_bourse', verbosity=0)
        self.assertEqual(Product.objects.count(), count)
        self.assertTrue(User.objects.filter(username='tokyo.buyer').exists())
        self.assertEqual(BuyerRequest.objects.filter(status=BuyerRequest.Status.ACCEPTED).count(), 1)


class FarmProofTests(TestCase):
    def test_seeded_olive_lot_shows_irrigation_and_sensors_as_proof(self):
        call_command('seed_bourse', verbosity=0)
        call_command('seed_bourse', verbosity=0)
        from apps.farms.models import FarmSensor
        oil = Product.objects.get(name='Huile d’olive extra vierge Chemlali')
        self.assertEqual(FarmSensor.objects.filter(farm=oil.farm).count(), 5)
        self.client.force_login(User.objects.get(username='tokyo.buyer'))
        page = self.client.get(reverse('market:detail', args=[oil.pk]), {'lang': 'en'})
        self.assertContains(page, 'Farm evidence (sensor data)')
        self.assertContains(page, 'Drip (water-saving)')
        self.assertContains(page, '1 450 m³')
        self.assertContains(page, '6.0 kW')

    def test_lot_without_farm_says_no_data(self):
        farmer = User.objects.create_user(username='sami', password='Kizuna-market-2026', role=User.Role.FARMER)
        product = Product.objects.create(
            farmer=farmer, name='Figues', category='fruit', quantity=Decimal('50'),
            unit='kg', origin='Djerba', harvest_date=date(2026, 9, 1), price_tnd=Decimal('5.00'),
        )
        self.client.force_login(farmer)
        page = self.client.get(reverse('market:detail', args=[product.pk]), {'lang': 'fr'})
        self.assertContains(page, 'pas encore partagé de données')

    def test_poland_and_canada_routes(self):
        pl = trade.route('pl', 'en')
        ca = trade.route('ca', 'fr')
        self.assertIn('Gdańsk', pl['port'])
        self.assertIn('EUR.1 (EU–Tunisia agreement, reduced duties)', pl['docs'])
        self.assertTrue(any('ACIA' in d for d in ca['docs']))
        self.assertTrue(any('bilingue' in d for d in ca['docs']))
