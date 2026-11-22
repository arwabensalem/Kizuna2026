"""Données complètes pour la démonstration devant le jury.

    python manage.py migrate
    python manage.py seed_demo

Crée (ou complète) un administrateur, des citoyens avec maison, pièces et
appareils, des agriculteurs avec fermes géolocalisées, cultures, capteurs et
annonces, et des acheteurs étrangers (Japon,
Royaume-Uni, Allemagne, France, Canada) avec leurs offres et leurs messages.

La commande ne supprime rien. Relancée, elle remet les mots de passe des
comptes de démonstration à leur valeur connue (voir DEMO_README.md).
"""

from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.farms.models import Crop, Farm, FarmSensor, FarmSolar, FarmTank, IrrigationSystem
from apps.homes.models import Appliance, Home, Room
from apps.marketplace.models import BuyerRequest, OfferMessage, Product

PASSWORD = 'Kizuna-demo-2026'
ADMIN = ('kizuna.admin', 'Kizuna-admin-2026')

D = Decimal

# ---------------------------------------------------------------- citoyens
CITIZENS = [
    {
        'user': ('amira', 'Amira', 'Ben Youssef', 'amira@kizuna.tn'),
        'home': {
            'name': 'Appartement El Menzah', 'home_type': Home.HomeType.APARTMENT,
            'address': 'El Menzah 6, Tunis', 'latitude': D('36.846000'), 'longitude': D('10.180000'),
            'area_m2': D('95'), 'residents': 4, 'bedrooms': 2, 'bathrooms': 1,
            'has_kitchen': True, 'has_living_room': True, 'has_water_tank': True,
            'autonomy_mode': Home.Autonomy.SMART, 'autopilot_enabled': True,
        },
        # (pièce, type, [(type d'appareil, libellé, W, L/h, consigne °C)])
        'rooms': [
            ('Salon', Room.Kind.LIVING_ROOM, [
                (Appliance.Kind.AC, 'Climatiseur du salon', 1500, 0, D('18')),  # réglé trop bas : alerte
                (Appliance.Kind.TV, 'Télévision', 120, 0, None),
                (Appliance.Kind.LIGHTS, 'Éclairage LED salon', 60, 0, None),
            ]),
            ('Cuisine', Room.Kind.KITCHEN, [
                (Appliance.Kind.REFRIGERATOR, 'Frigo combiné (ancien)', 420, 0, None),  # consomme trop : alerte
                (Appliance.Kind.WASHING_MACHINE, 'Machine à laver', 2000, D('50'), None),
                (Appliance.Kind.DISHWASHER, 'Lave-vaisselle', 1800, D('12'), None),
            ]),
            ('Salle de bain', Room.Kind.BATHROOM, [
                (Appliance.Kind.WATER_HEATER, 'Chauffe-eau électrique', 2000, D('40'), None),
            ]),
            ('Chambre parentale', Room.Kind.BEDROOM, [
                (Appliance.Kind.AC, 'Climatiseur chambre', 1200, 0, D('24')),
            ]),
            ('Chambre des enfants', Room.Kind.BEDROOM, [
                (Appliance.Kind.LIGHTS, 'Lampe de bureau', 15, 0, None),
            ]),
        ],
    },
    {
        'user': ('karim', 'Karim', 'Mejri', 'karim@kizuna.tn'),
        'home': {
            'name': 'Villa Sahloul', 'home_type': Home.HomeType.VILLA,
            'address': 'Sahloul, Sousse', 'latitude': D('35.836000'), 'longitude': D('10.593000'),
            'area_m2': D('240'), 'residents': 5, 'bedrooms': 4, 'bathrooms': 2,
            'has_kitchen': True, 'has_living_room': True, 'has_garden': True, 'has_pool': True,
            'has_garage': True, 'has_solar_panels': True, 'has_water_tank': True,
            'autonomy_mode': Home.Autonomy.AUTOPILOT, 'autopilot_enabled': True,
        },
        'rooms': [
            ('Séjour', Room.Kind.LIVING_ROOM, [
                (Appliance.Kind.AC, 'Climatiseur gainable', 3500, 0, D('23')),
                (Appliance.Kind.TV, 'Home cinéma', 250, 0, None),
            ]),
            ('Cuisine', Room.Kind.KITCHEN, [
                (Appliance.Kind.REFRIGERATOR, 'Réfrigérateur américain', 180, 0, None),
                (Appliance.Kind.DISHWASHER, 'Lave-vaisselle', 1800, D('10'), None),
                (Appliance.Kind.WASHING_MACHINE, 'Lave-linge', 2200, D('55'), None),
            ]),
            ('Jardin', Room.Kind.GARDEN, [
                (Appliance.Kind.PUMP, 'Pompe d’arrosage', 750, D('900'), None),
            ]),
            ('Piscine', Room.Kind.POOL, [
                (Appliance.Kind.PUMP, 'Pompe de filtration', 1100, D('0'), None),
            ]),
            ('Salle de bain', Room.Kind.BATHROOM, [
                (Appliance.Kind.WATER_HEATER, 'Chauffe-eau solaire (appoint)', 1500, D('45'), None),
            ]),
            ('Garage', Room.Kind.GARAGE, [
                (Appliance.Kind.LIGHTS, 'Éclairage garage', 80, 0, None),
            ]),
        ],
        'off': ('Climatiseur gainable', 'Lave-vaisselle', 'Lave-linge', 'Pompe d’arrosage',
                'Pompe de filtration', 'Chauffe-eau solaire (appoint)', 'Éclairage garage'),
    },
    {
        'user': ('leila', 'Leïla', 'Haddad', 'leila@kizuna.tn'),
        'home': {
            'name': 'Dar Leïla (maison à patio)', 'home_type': Home.HomeType.PATIO,
            'address': 'Médina de Kairouan', 'latitude': D('35.678000'), 'longitude': D('10.101000'),
            'area_m2': D('160'), 'residents': 3, 'bedrooms': 3, 'bathrooms': 1,
            'has_kitchen': True, 'has_living_room': True, 'has_solar_panels': True, 'has_water_tank': True,
            'autonomy_mode': Home.Autonomy.ASSIST,
        },
        'rooms': [
            ('Patio', Room.Kind.OTHER, [
                (Appliance.Kind.LIGHTS, 'Lanternes du patio', 90, 0, None),
            ]),
            ('Bit el kbira (salon)', Room.Kind.LIVING_ROOM, [
                (Appliance.Kind.AC, 'Climatiseur inverter', 1300, 0, D('25')),
            ]),
            ('Cuisine', Room.Kind.KITCHEN, [
                (Appliance.Kind.REFRIGERATOR, 'Réfrigérateur', 150, 0, None),
                (Appliance.Kind.WASHING_MACHINE, 'Machine à laver', 2000, D('45'), None),
            ]),
            ('Salle d’eau', Room.Kind.BATHROOM, [
                (Appliance.Kind.WATER_HEATER, 'Chauffe-eau à gaz', 0, D('35'), None),
            ]),
        ],
    },
]

# ---------------------------------------------------------------- agriculteurs
# Les quatre premiers viennent de seed_bourse (annonces et offres). On ajoute leur
# numéro de téléphone (connexion par téléphone), leurs cultures et leurs capteurs.
FARMERS = {
    'zitouna.sfax': {
        'phone': '+21698100201',
        'crops': [('Oliviers Chemlali', Farm.CropType.OLIVE, 95000, Crop.Stage.HARVEST),
                  ('Amandiers', Farm.CropType.ALMOND, 20000, Crop.Stage.VEGETATIVE)],
        'tank': ('Bassin de stockage', 60000),
        'sensors': [(FarmSensor.Kind.SOIL_MOISTURE_DEEP, 'Sonde sol 40 cm', False),
                    (FarmSensor.Kind.PUMP_FLOW, 'Débitmètre pompe', False),
                    (FarmSensor.Kind.WEATHER_STATION, 'Station météo partagée Agareb', True)],
    },
    'oasis.tozeur': {
        'phone': '+21698100202',
        'crops': [('Palmiers Deglet Nour', Farm.CropType.DATE, 32000, Crop.Stage.HARVEST),
                  ('Grenadiers sous palmiers', Farm.CropType.OTHER, 5000, Crop.Stage.FRUITING)],
        'tank': ('Réservoir de la source', 120000),
        'sensors': [(FarmSensor.Kind.SOIL_MOISTURE_DEEP, 'Sonde sol 40 cm', False),
                    (FarmSensor.Kind.PUMP_FLOW, 'Débitmètre forage', False)],
    },
    'capbon.harissa': {
        'phone': '+21698100203',
        'crops': [('Piments Baklouti', Farm.CropType.PEPPER, 9000, Crop.Stage.FRUITING),
                  ('Orangers Maltaise', Farm.CropType.CITRUS, 12000, Crop.Stage.FRUITING),
                  ('Tomates de saison', Farm.CropType.TOMATO, 3000, Crop.Stage.FLOWERING)],
        'tank': ('Citerne', 30000),
        'sensors': [(FarmSensor.Kind.SOIL_MOISTURE_DEEP, 'Sonde sol 40 cm', False),
                    (FarmSensor.Kind.WEATHER_STATION, 'Station météo partagée Nabeul', True)],
    },
    'kairouan.herbes': {
        'phone': '+21698100204',
        'crops': [('Blé dur', Farm.CropType.WHEAT, 40000, Crop.Stage.SEEDLING),
                  ('Orge', Farm.CropType.BARLEY, 12000, Crop.Stage.SEEDLING),
                  ('Romarin et thym', Farm.CropType.OTHER, 6000, Crop.Stage.VEGETATIVE)],
        'tank': ('Jesr (citerne enterrée)', 20000),
        'sensors': [(FarmSensor.Kind.WEATHER_STATION, 'Station météo coopérative', True)],
    },
}

NEW_FARMER = {
    'user': ('nizar.mateur', 'Nizar', 'Khemiri', '+21698100205'),
    'farm': {
        'name': 'Ferme Ichkeul', 'location': 'Mateur, Bizerte, Tunisie',
        'latitude': D('37.040000'), 'longitude': D('9.665000'), 'area_m2': D('80000'),
        'crop_type': Farm.CropType.TOMATO, 'soil_type': Farm.Soil.CLAY,
        'irrigation_type': Farm.IrrigationType.DRIP, 'tank_capacity_liters': 40000,
        'solar_capacity_watts': 5000,
    },
    'crops': [('Tomates industrielles', Farm.CropType.TOMATO, 30000, Crop.Stage.FLOWERING),
              ('Blé tendre', Farm.CropType.WHEAT, 35000, Crop.Stage.SEEDLING),
              ('Pommes de terre', Farm.CropType.POTATO, 10000, Crop.Stage.VEGETATIVE)],
    'systems': [('Goutte-à-goutte tomates', 'drip', 2800), ('Pivot blé', 'sprinkler', 6000)],
    'solar': ('Pompage solaire', 5000),
    'tank': ('Bassin', 40000),
    'sensors': [(FarmSensor.Kind.SOIL_MOISTURE, 'Sonde sol 20 cm', False),
                (FarmSensor.Kind.SOIL_MOISTURE_DEEP, 'Sonde sol 40 cm', False),
                (FarmSensor.Kind.PUMP_FLOW, 'Débitmètre pompe', False),
                (FarmSensor.Kind.WEATHER_STATION, 'Station météo partagée Mateur', True)],
    'products': [{
        'name': 'Tomates séchées au soleil', 'category': 'vegetable', 'unit': 'kg',
        'quantity': D('500'), 'price_tnd': D('14.00'), 'min_order': D('50'),
        'origin': 'Mateur, Bizerte', 'harvest_date': date(2026, 8, 20), 'export_ready': True,
        'certifications': 'globalgap',
        'description': 'Tomates de plein champ près du lac Ichkeul, séchées au soleil et conservées sans additif.',
    }],
}

# ---------------------------------------------------------------- acheteurs étrangers (en plus de seed_bourse)
BUYERS = [
    ('london.trade', 'Emma', 'Clarke', 'emma@kizuna-demo.uk'),
    ('hamburg.feinkost', 'Jonas', 'Becker', 'jonas@kizuna-demo.de'),
    ('montreal.epicerie', 'Sophie', 'Tremblay', 'sophie@kizuna-demo.ca'),
]


class Command(BaseCommand):
    help = 'Remplit la base avec un parcours de démonstration complet (sans rien supprimer).'

    def _account(self, username, first, last, role, email='', phone=''):
        user, created = User.objects.get_or_create(
            username=username, defaults={'first_name': first, 'last_name': last, 'role': role},
        )
        user.first_name, user.last_name, user.role = first, last, role
        user.email = email or user.email
        if phone:
            user.phone = phone
        user.is_active = True
        user.email_verified = True
        user.set_password(PASSWORD)
        user.save()
        self.accounts.append((role, username, phone))
        return user

    def _rooms(self, home, rooms):
        for room_name, room_kind, appliances in rooms:
            room, _ = Room.objects.get_or_create(home=home, name=room_name, defaults={'kind': room_kind})
            for kind, label, watts, liters, setpoint in appliances:
                Appliance.objects.get_or_create(
                    home=home, label=label,
                    defaults={
                        'room': room, 'kind': kind, 'power_watts': watts,
                        'water_liters_per_hour': D(liters), 'temperature_setpoint': setpoint,
                        'is_active': True,
                    },
                )

    def _farm_extras(self, farm, spec):
        for name, kind, area, stage in spec['crops']:
            Crop.objects.get_or_create(farm=farm, name=name, defaults={'kind': kind, 'area_m2': D(area), 'stage': stage})
        tank_name, capacity = spec['tank']
        FarmTank.objects.get_or_create(farm=farm, name=tank_name, defaults={'capacity_liters': capacity})
        for kind, label, shared in spec['sensors']:
            FarmSensor.objects.get_or_create(
                farm=farm, kind=kind, label=label, defaults={'shared_with_neighbors': shared},
            )
        # Les deux profondeurs de sol : 20 cm en plus de 40 cm.
        if not farm.farm_sensors.filter(kind=FarmSensor.Kind.SOIL_MOISTURE).exists():
            FarmSensor.objects.create(farm=farm, kind=FarmSensor.Kind.SOIL_MOISTURE, label='Sonde sol 20 cm')

    def _offer(self, buyer, product, quantity, price, currency, destination, incoterm, thread, status):
        if not product or BuyerRequest.objects.filter(buyer=buyer, product=product).exists():
            return
        first = thread[0][1]
        offer = BuyerRequest.objects.create(
            buyer=buyer, farmer=product.farmer, product=product, quantity=D(quantity),
            offer_price_tnd=D(price), currency=currency, destination=destination, incoterm=incoterm,
            status=status, message=first,
        )
        for who, body, msg_price, event in thread:
            OfferMessage.objects.create(
                offer=offer, author=buyer if who == 'buyer' else product.farmer, body=body,
                price_tnd=D(msg_price) if msg_price else None, event=event,
            )
            if msg_price:
                offer.offer_price_tnd = D(msg_price)
        offer.save()

    @transaction.atomic
    def handle(self, *args, **options):
        self.accounts = []

        # 1. Administrateur
        username, admin_password = ADMIN
        admin, _ = User.objects.get_or_create(username=username, defaults={'email': 'admin@kizuna.tn'})
        admin.role, admin.is_staff, admin.is_superuser, admin.is_active = User.Role.ADMIN, True, True, True
        admin.first_name, admin.last_name = 'Équipe', 'KIZUNA'
        admin.set_password(admin_password)
        admin.save()

        # 2. Bourse : agriculteurs, annonces, acheteurs de Tokyo et Marseille, premières offres.
        call_command('seed_bourse', verbosity=0)

        # 3. Citoyens, maisons, pièces, appareils
        for spec in CITIZENS:
            name, first, last, email = spec['user']
            user = self._account(name, first, last, User.Role.CITIZEN, email=email)
            home, _ = Home.objects.get_or_create(owner=user, name=spec['home']['name'], defaults=spec['home'])
            self._rooms(home, spec['rooms'])
            # Appareils éteints au départ : ils attendent le soleil (conseil « vos panneaux produisent »).
            home.appliances.filter(label__in=spec.get('off', ())).update(is_active=False)

        # 4. Agriculteurs de la bourse : téléphone, cultures, capteurs
        for username, spec in FARMERS.items():
            user = User.objects.get(username=username)
            self._account(username, user.first_name, user.last_name, User.Role.FARMER, phone=spec['phone'])
            for farm in user.farms.all():
                self._farm_extras(farm, spec)

        # 5. Un nouvel agriculteur, complet
        name, first, last, phone = NEW_FARMER['user']
        nizar = self._account(name, first, last, User.Role.FARMER, phone=phone)
        farm, _ = Farm.objects.get_or_create(owner=nizar, name=NEW_FARMER['farm']['name'], defaults=NEW_FARMER['farm'])
        self._farm_extras(farm, NEW_FARMER)
        for system_name, method, flow in NEW_FARMER['systems']:
            IrrigationSystem.objects.get_or_create(
                farm=farm, name=system_name,
                defaults={'method': method, 'flow_liters_per_hour': D(flow), 'is_active': True},
            )
        FarmSolar.objects.get_or_create(farm=farm, name=NEW_FARMER['solar'][0], defaults={'capacity_watts': NEW_FARMER['solar'][1]})
        for item in NEW_FARMER['products']:
            fields = dict(item)
            Product.objects.get_or_create(farmer=nizar, name=fields.pop('name'), defaults={**fields, 'farm': farm})

        # Anciens comptes de démo « entreprise » (partie retirée) : on les enlève.
        User.objects.filter(username__in=('hotel.hammamet', 'resto.lac'), role=User.Role.BUSINESS).delete()

        # 6. Acheteurs étrangers : ceux de seed_bourse + Londres, Hambourg, Montréal
        for username, first, last in (('tokyo.buyer', 'Yuki', 'Tanaka'), ('marseille.epicerie', 'Claire', 'Martin')):
            self._account(username, first, last, User.Role.BUSINESS, email=f'{username}@kizuna-demo.com')
        buyers = {u: self._account(u, f, l, User.Role.BUSINESS, email=e) for u, f, l, e in BUYERS}

        products = {p.name: p for p in Product.objects.all()}
        oil = products.get('Huile d’olive extra vierge Chemlali')
        dates = products.get('Dattes Deglet Nour en branchettes')
        herbs = products.get('Romarin et thym sauvages séchés')
        tomatoes = products.get('Tomates séchées au soleil')
        self._offer(buyers['london.trade'], dates, '400', '9.50', 'USD', 'fr', 'CIF', [
            ('buyer', 'Hello Salma, we import Medjool and Deglet Nour for UK supermarkets. Could you supply 400 kg in branches before Christmas?', '9.50', 'offer'),
            ('farmer', 'Hello Emma! Yes, harvested 28 October, organic and GlobalG.A.P. I can confirm 400 kg at 9.80 TND/kg CIF.', '9.80', 'counter'),
            ('buyer', 'Deal at 9.80. Please send the lot passport with the irrigation data.', '9.80', 'accept'),
        ], BuyerRequest.Status.ACCEPTED)
        self._offer(buyers['hamburg.feinkost'], oil, '300', '15.50', 'EUR', 'de', 'FOB', [
            ('buyer', 'Guten Tag! Feinkostladen in Hamburg. Wir suchen 300 L Bio-Olivenöl extra vergine.', '15.50', 'offer'),
        ], BuyerRequest.Status.PENDING)
        self._offer(buyers['montreal.epicerie'], herbs, '40', '17.00', 'USD', 'ca', 'CIF', [
            ('buyer', 'Bonjour Mourad, épicerie fine à Montréal. Vos herbes sauvages bio nous intéressent : 40 kg pour commencer.', '17.00', 'offer'),
            ('farmer', 'Bonjour Sophie, avec plaisir. Coopérative de femmes, cueillette de juin. Je propose 18 TND/kg.', '18.00', 'counter'),
        ], BuyerRequest.Status.COUNTERED)
        self._offer(buyers['hamburg.feinkost'], tomatoes, '120', '13.00', 'EUR', 'de', 'FOB', [
            ('buyer', 'Sonnengetrocknete Tomaten: 120 kg für unser Wintersortiment?', '13.00', 'offer'),
        ], BuyerRequest.Status.PENDING)

        if options.get('verbosity', 1):
            self.stdout.write(self.style.SUCCESS('Démo KIZUNA prête.'))
            self.stdout.write(f'  Administrateur : {ADMIN[0]} / {ADMIN[1]}   (http://127.0.0.1:8000/admin/)')
            self.stdout.write(f'  Tous les autres comptes : mot de passe {PASSWORD}')
            for role, username, phone in self.accounts:
                self.stdout.write(f'  {role:9} {username:20} {phone}')
