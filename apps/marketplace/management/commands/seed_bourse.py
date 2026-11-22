"""Données de démonstration de la Bourse KIZUNA (agriculteurs tunisiens, acheteurs étrangers).

    python manage.py seed_bourse

Sans effet destructeur : crée seulement ce qui manque (comptes, fermes, annonces,
offres). Mot de passe des comptes de démo : Kizuna-demo-2026.
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.farms.models import Farm, FarmSensor, FarmSolar, Irrigation, IrrigationSystem
from apps.marketplace.models import BuyerRequest, OfferMessage, Product

PASSWORD = 'Kizuna-demo-2026'

# Données de capteurs qui servent de preuve de qualité dans le passeport du lot.
# (sol, irrigation, systèmes (nom, L/h), relevés d'eau (méthode, m³), capteurs, solaire W)
FARM_PROOF = {
    'Oliveraie Zitouna': (
        'sand', 'drip', [('Goutte-à-goutte oliviers', 2400)],
        [('Goutte-à-goutte, saison 2026', 1450)],
        ['soil_moisture', 'temperature', 'rainfall', 'tank_level', 'solar_production'], 6000,
    ),
    'Palmeraie de Tozeur': (
        'sand', 'drip', [('Goutte-à-goutte palmiers', 3200)],
        [('Goutte-à-goutte, saison 2026', 4800)],
        ['soil_moisture', 'temperature', 'humidity', 'solar_production'], 9000,
    ),
    'Jardins du Cap Bon': (
        'loam', 'drip', [('Goutte-à-goutte piments', 1500), ('Aspersion agrumes', 900)],
        [('Goutte-à-goutte, saison 2026', 1100)],
        ['soil_moisture', 'humidity', 'tank_level'], 3000,
    ),
    'Domaine Gharbi': (
        'clay', 'none', [], [],
        ['soil_moisture', 'temperature', 'rainfall'], 0,
    ),
}

FARMERS = [
    {
        'username': 'zitouna.sfax', 'first_name': 'Hédi', 'last_name': 'Ben Salah',
        'farm': ('Oliveraie Zitouna', 'Sfax, Tunisie', 34.7406, 10.7603, 120000, 'olive'),
        'products': [
            {
                'name': 'Huile d’olive extra vierge Chemlali', 'category': 'oil', 'unit': 'litre',
                'quantity': '1200', 'price_tnd': '16.50', 'min_order': '100',
                'origin': 'Sfax', 'harvest_date': date(2026, 11, 8), 'export_ready': True,
                'certifications': 'organic,aop',
                'description': (
                    'Oliviers Chemlali centenaires, cultivés en sec sans irrigation. Récolte à la main, '
                    'trituration à froid moins de 6 heures après la cueillette. Acidité 0,2 %. '
                    "Avant KIZUNA, la famille vendait l'huile en vrac à un collecteur local."
                ),
            },
            {
                'name': 'Olives de table Meski', 'category': 'olive', 'unit': 'kg',
                'quantity': '800', 'price_tnd': '7.00', 'min_order': '50',
                'origin': 'Sfax', 'harvest_date': date(2026, 10, 20), 'export_ready': True,
                'certifications': 'organic',
                'description': 'Olives vertes Meski, saumurées naturellement, sans conservateur.',
            },
        ],
    },
    {
        'username': 'oasis.tozeur', 'first_name': 'Salma', 'last_name': 'Jeridi',
        'farm': ('Palmeraie de Tozeur', 'Tozeur, Tunisie', 33.9197, 8.1335, 40000, 'other'),
        'products': [
            {
                'name': 'Dattes Deglet Nour en branchettes', 'category': 'fruit', 'unit': 'kg',
                'quantity': '2500', 'price_tnd': '9.00', 'min_order': '200',
                'origin': 'Tozeur (Djérid)', 'harvest_date': date(2026, 10, 28), 'export_ready': True,
                'certifications': 'organic,globalgap,halal',
                'description': (
                    "Les « doigts de lumière » de l'oasis du Djérid, irriguées par les sources de la palmeraie. "
                    'Cueillies à maturité, triées à la main et conservées en chambre froide.'
                ),
            },
        ],
    },
    {
        'username': 'capbon.harissa', 'first_name': 'Amel', 'last_name': 'Trabelsi',
        'farm': ('Jardins du Cap Bon', 'Nabeul, Tunisie', 36.4561, 10.7376, 25000, 'pepper'),
        'products': [
            {
                'name': 'Piment séché pour harissa (Baklouti)', 'category': 'vegetable', 'unit': 'kg',
                'quantity': '300', 'price_tnd': '22.00', 'min_order': '20',
                'origin': 'Nabeul, Cap Bon', 'harvest_date': date(2026, 9, 15), 'export_ready': True,
                'certifications': 'aop',
                'description': (
                    'Piments Baklouti séchés au soleil sur les terrasses de Nabeul, '
                    'base de la harissa traditionnelle inscrite au patrimoine immatériel de l’UNESCO.'
                ),
            },
            {
                'name': 'Oranges Maltaise', 'category': 'fruit', 'unit': 'crate',
                'quantity': '400', 'price_tnd': '28.00', 'min_order': '40',
                'origin': 'Cap Bon', 'harvest_date': date(2026, 11, 15), 'export_ready': False,
                'certifications': 'globalgap',
                'description': 'Maltaise demi-sanguine du Cap Bon, caisse de 15 kg.',
            },
        ],
    },
    {
        'username': 'kairouan.herbes', 'first_name': 'Mourad', 'last_name': 'Gharbi',
        'farm': ('Domaine Gharbi', 'Kairouan, Tunisie', 35.6781, 10.0963, 60000, 'wheat'),
        'products': [
            {
                'name': 'Romarin et thym sauvages séchés', 'category': 'herb', 'unit': 'kg',
                'quantity': '150', 'price_tnd': '18.00', 'min_order': '10',
                'origin': 'Kairouan', 'harvest_date': date(2026, 6, 10), 'export_ready': True,
                'certifications': 'organic,fairtrade',
                'description': 'Cueillette sauvage sur les collines de Kairouan par une coopérative de femmes rurales.',
            },
        ],
    },
]

BUYERS = [
    {'username': 'tokyo.buyer', 'first_name': 'Yuki', 'last_name': 'Tanaka'},
    {'username': 'marseille.epicerie', 'first_name': 'Claire', 'last_name': 'Martin'},
]


class Command(BaseCommand):
    help = 'Crée des données de démonstration pour la Bourse KIZUNA (sans rien supprimer).'

    def _user(self, data, role):
        user, created = User.objects.get_or_create(
            username=data['username'],
            defaults={'first_name': data['first_name'], 'last_name': data['last_name'], 'role': role},
        )
        if created:
            user.set_password(PASSWORD)
            user.save()
        return user, created

    def _proof(self, farm):
        spec = FARM_PROOF.get(farm.name)
        if not spec or farm.irrigation_systems.exists() or farm.farm_sensors.exists():
            return
        soil, method, systems, waterings, sensors, solar = spec
        farm.soil_type, farm.irrigation_type = soil, method
        farm.save(update_fields=['soil_type', 'irrigation_type'])
        for name, flow in systems:
            IrrigationSystem.objects.create(
                farm=farm, name=name, flow_liters_per_hour=Decimal(flow), is_active=True,
                method='sprinkler' if 'Aspersion' in name else 'drip',
            )
        for label, water in waterings:
            Irrigation.objects.create(farm=farm, method=label, water_m3=Decimal(water))
        for kind in sensors:
            FarmSensor.objects.create(farm=farm, kind=kind)
        if solar:
            FarmSolar.objects.create(farm=farm, name='Pompage solaire', capacity_watts=solar)

    def handle(self, *args, **options):
        made = 0
        products = {}
        for spec in FARMERS:
            farmer, created = self._user(spec, User.Role.FARMER)
            made += created
            name, location, lat, lng, area, crop = spec['farm']
            farm, _ = Farm.objects.get_or_create(
                owner=farmer, name=name,
                defaults={
                    'location': location, 'latitude': Decimal(str(lat)), 'longitude': Decimal(str(lng)),
                    'area_m2': Decimal(area), 'crop_type': crop,
                },
            )
            self._proof(farm)
            for item in spec['products']:
                fields = dict(item)
                fields['quantity'] = Decimal(fields['quantity'])
                fields['price_tnd'] = Decimal(fields['price_tnd'])
                fields['min_order'] = Decimal(fields['min_order'])
                product, p_created = Product.objects.get_or_create(
                    farmer=farmer, name=fields.pop('name'), defaults={**fields, 'farm': farm},
                )
                made += p_created
                products[product.name] = product

        buyers = {}
        for spec in BUYERS:
            buyer, created = self._user(spec, User.Role.BUSINESS)
            made += created
            buyers[buyer.username] = buyer

        oil = products.get('Huile d’olive extra vierge Chemlali')
        dates = products.get('Dattes Deglet Nour en branchettes')
        tokyo = buyers['tokyo.buyer']
        if oil and not BuyerRequest.objects.filter(buyer=tokyo, product=oil).exists():
            offer = BuyerRequest.objects.create(
                buyer=tokyo, farmer=oil.farmer, product=oil, quantity=Decimal('500'),
                offer_price_tnd=Decimal('15.00'), currency='JPY', destination='jp_sea', incoterm='FOB',
                status=BuyerRequest.Status.COUNTERED,
                message=(
                    'はじめまして。東京の自然食品店です。有機エクストラバージンオリーブオイルを探しています。\n'
                    'Hello, we run an organic grocery in Tokyo. We would like 500 L for our spring season.'
                ),
            )
            OfferMessage.objects.create(offer=offer, author=tokyo, body=offer.message, price_tnd=Decimal('15.00'), event='offer')
            OfferMessage.objects.create(
                offer=offer, author=oil.farmer, price_tnd=Decimal('16.00'), event='counter',
                body=(
                    'Merci ! Thank you! Our oil is first cold press, harvested 8 November. '
                    'I can do 16 TND/L FOB Radès with the organic certificate and lab analysis.'
                ),
            )
            offer.offer_price_tnd = Decimal('16.00')
            offer.save()
            made += 1
        if dates and not BuyerRequest.objects.filter(buyer=tokyo, product=dates).exists():
            offer = BuyerRequest.objects.create(
                buyer=tokyo, farmer=dates.farmer, product=dates, quantity=Decimal('300'),
                offer_price_tnd=Decimal('9.00'), currency='JPY', destination='jp_air', incoterm='CIF',
                status=BuyerRequest.Status.ACCEPTED,
                message='Deglet Nour for a Ramadan and gift-box collection in Tokyo. 300 kg by air.',
            )
            OfferMessage.objects.create(offer=offer, author=tokyo, body=offer.message, price_tnd=Decimal('9.00'), event='offer')
            OfferMessage.objects.create(
                offer=offer, author=dates.farmer, event='accept',
                body='Accepté avec plaisir. ありがとうございます！ Expédition depuis Tunis-Carthage sous 5 jours.',
            )
            made += 1
        marseille = buyers['marseille.epicerie']
        harissa = products.get('Piment séché pour harissa (Baklouti)')
        if harissa and not BuyerRequest.objects.filter(buyer=marseille, product=harissa).exists():
            offer = BuyerRequest.objects.create(
                buyer=marseille, farmer=harissa.farmer, product=harissa, quantity=Decimal('60'),
                offer_price_tnd=Decimal('20.00'), currency='EUR', destination='fr', incoterm='FOB',
                message='Bonjour, épicerie fine à Marseille. Pouvez-vous envoyer 60 kg avant décembre ?',
            )
            OfferMessage.objects.create(offer=offer, author=marseille, body=offer.message, price_tnd=Decimal('20.00'), event='offer')
            made += 1

        if options.get('verbosity', 1) == 0:
            return
        self.stdout.write(self.style.SUCCESS(
            f'Bourse KIZUNA : {made} élément(s) créé(s). Comptes de démo : '
            f'zitouna.sfax, oasis.tozeur, capbon.harissa, kairouan.herbes (agriculteurs), '
            f'tokyo.buyer, marseille.epicerie (acheteurs). Mot de passe : {PASSWORD}'
        ))
