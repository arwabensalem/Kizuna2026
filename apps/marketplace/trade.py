"""Bourse KIZUNA : commerce direct entre agriculteurs tunisiens et acheteurs étrangers.

Fonctions pures, sans base de données : conversion de devises, chaîne de valeur
(classique contre vente directe), logistique export et libellés FR / EN / JA.

Tous les chiffres sont des ordres de grandeur indicatifs, présentés comme tels
dans l'interface. Ils servent à rendre visible l'écart entre ce que touche
l'agriculteur et le prix payé en rayon à l'étranger.
"""

from decimal import ROUND_HALF_UP, Decimal

# --------------------------------------------------------------------------
# Devises (taux indicatifs : 1 TND = x devise)
# --------------------------------------------------------------------------

CURRENCIES = {
    'TND': {'rate': Decimal('1'), 'symbol': 'TND', 'decimals': 2, 'flag': '🇹🇳'},
    'EUR': {'rate': Decimal('0.29'), 'symbol': '€', 'decimals': 2, 'flag': '🇪🇺'},
    'USD': {'rate': Decimal('0.32'), 'symbol': '$', 'decimals': 2, 'flag': '🇺🇸'},
    'JPY': {'rate': Decimal('48'), 'symbol': '¥', 'decimals': 0, 'flag': '🇯🇵'},
}
DEFAULT_CURRENCY = 'TND'
RATES_NOTE = 'Taux indicatifs : 1 TND ≈ 0,29 € ≈ 0,32 $ ≈ 48 ¥'


def clean_currency(code):
    code = (code or '').upper()
    return code if code in CURRENCIES else DEFAULT_CURRENCY


def convert(amount_tnd, currency):
    """Montant en dinars converti dans la devise demandée (Decimal arrondi)."""
    if amount_tnd is None:
        return None
    info = CURRENCIES[clean_currency(currency)]
    quantum = Decimal('1') if info['decimals'] == 0 else Decimal('0.01')
    return (Decimal(amount_tnd) * info['rate']).quantize(quantum, ROUND_HALF_UP)


def to_tnd(amount, currency):
    """Montant saisi dans une devise étrangère, ramené en dinars."""
    if amount is None:
        return None
    info = CURRENCIES[clean_currency(currency)]
    return (Decimal(amount) / info['rate']).quantize(Decimal('0.01'), ROUND_HALF_UP)


def money(amount_tnd, currency):
    """Texte prêt à afficher : « 1 234 ¥ », « 3,48 € », « 12,00 TND »."""
    value = convert(amount_tnd, currency)
    if value is None:
        return '—'
    info = CURRENCIES[clean_currency(currency)]
    if info['decimals'] == 0:
        text = f'{value:,.0f}'.replace(',', ' ')
    else:
        text = f'{value:,.2f}'.replace(',', ' ').replace('.', ',')
    if currency in ('EUR', 'USD', 'JPY'):
        return f'{text} {info["symbol"]}'
    return f'{text} TND'


def all_prices(amount_tnd):
    return [
        {'code': code, 'flag': info['flag'], 'text': money(amount_tnd, code)}
        for code, info in CURRENCIES.items()
    ]


# --------------------------------------------------------------------------
# Chaîne de valeur : où va l'argent ?
# --------------------------------------------------------------------------

# Multiplicateur cumulé du prix départ ferme à chaque maillon (ordre de grandeur).
TRADITIONAL_CHAIN = (
    ('farmer', 1.0),
    ('collector', 1.4),
    ('wholesaler', 2.3),
    ('exporter', 3.4),
    ('importer', 5.2),
    ('retail', 9.5),
)

# Le dernier maillon varie un peu selon le produit (huile et dattes très valorisées).
RETAIL_MULTIPLIER = {
    'oil': 10.0,
    'fruit': 9.5,
    'olive': 9.0,
    'herb': 9.0,
    'vegetable': 7.5,
    'grain': 6.0,
    'other': 8.0,
}

KIZUNA_FEE_RATE = Decimal('0.05')        # commission de la plateforme
PACKING_RATE = Decimal('0.08')           # conditionnement export, contrôle qualité
HANDLING_PER_UNIT = Decimal('0.40')      # dédouanement, manutention (TND / unité)


def traditional_chain(price_tnd, category):
    """Prix par maillon dans la chaîne classique, du champ au rayon."""
    price = Decimal(price_tnd)
    retail = Decimal(str(RETAIL_MULTIPLIER.get(category, 8.0)))
    steps = []
    for index, (key, factor) in enumerate(TRADITIONAL_CHAIN):
        mult = retail if key == 'retail' else Decimal(str(factor))
        steps.append({
            'key': key,
            'multiplier': mult,
            'price': (price * mult).quantize(Decimal('0.01')),
        })
    final = steps[-1]['price']
    previous = Decimal('0')
    for step in steps:
        step['margin'] = step['price'] - previous
        step['share'] = int(round(float(step['margin'] / final * 100))) if final else 0
        step['width'] = max(2, step['share'])
        previous = step['price']
    return steps


def direct_deal(price_tnd, category, destination):
    """Vente directe KIZUNA : ce que paie l'acheteur, ce que touche l'agriculteur."""
    price = Decimal(price_tnd)
    route = DESTINATIONS.get(destination) or DESTINATIONS[DEFAULT_DESTINATION]
    lines = [
        ('farmer', price),
        ('packing', (price * PACKING_RATE).quantize(Decimal('0.01'))),
        ('transport', Decimal(str(route['freight_tnd']))),
        ('handling', HANDLING_PER_UNIT),
        ('kizuna', (price * KIZUNA_FEE_RATE).quantize(Decimal('0.01'))),
    ]
    landed = sum(amount for _, amount in lines)
    rows = []
    for key, amount in lines:
        share = int(round(float(amount / landed * 100))) if landed else 0
        rows.append({'key': key, 'price': amount, 'share': share, 'width': max(2, share)})
    chain = traditional_chain(price, category)
    shelf = chain[-1]['price']
    return {
        'rows': rows,
        'landed': landed,
        'farmer_share': rows[0]['share'],
        'shelf_price': shelf,
        'traditional_share': chain[0]['share'],
        'saving': shelf - landed,
        'multiplier': chain[-1]['multiplier'],
    }


def farmer_share(price_tnd, category, destination=None):
    if price_tnd is None:
        return None
    return direct_deal(price_tnd, category, destination or DEFAULT_DESTINATION)['farmer_share']


# --------------------------------------------------------------------------
# Logistique export
# --------------------------------------------------------------------------

COMMON_DOCS = ('invoice', 'packing_list', 'origin', 'bill')

DESTINATIONS = {
    'jp_sea': {
        'flag': '🇯🇵', 'city': 'Tokyo / Yokohama', 'port': 'Radès → Yokohama',
        'mode': 'sea', 'days': '35–45', 'freight_tnd': 1.60,
        'docs': COMMON_DOCS + ('phyto', 'jp_notice', 'jp_residue', 'jp_jas'),
    },
    'jp_air': {
        'flag': '🇯🇵', 'city': 'Tokyo (Narita)', 'port': 'Tunis-Carthage → Narita',
        'mode': 'air', 'days': '2–4', 'freight_tnd': 11.50,
        'docs': COMMON_DOCS + ('phyto', 'jp_notice', 'jp_residue', 'jp_jas'),
    },
    'fr': {
        'flag': '🇫🇷', 'city': 'Marseille', 'port': 'Radès → Marseille',
        'mode': 'sea', 'days': '2–3', 'freight_tnd': 0.55,
        'docs': COMMON_DOCS + ('eur1', 'phyto', 'eu_oil'),
    },
    'it': {
        'flag': '🇮🇹', 'city': 'Gênes / Palerme', 'port': 'Radès → Gênes',
        'mode': 'sea', 'days': '1–3', 'freight_tnd': 0.50,
        'docs': COMMON_DOCS + ('eur1', 'phyto', 'eu_oil'),
    },
    'de': {
        'flag': '🇩🇪', 'city': 'Hambourg / Munich', 'port': 'Radès → Gênes → camion',
        'mode': 'sea', 'days': '5–8', 'freight_tnd': 0.90,
        'docs': COMMON_DOCS + ('eur1', 'phyto', 'eu_oil'),
    },
    'ae': {
        'flag': '🇦🇪', 'city': 'Dubaï', 'port': 'Radès → Jebel Ali',
        'mode': 'sea', 'days': '14–20', 'freight_tnd': 1.10,
        'docs': COMMON_DOCS + ('phyto', 'halal'),
    },
    'pl': {
        'flag': '🇵🇱', 'city': 'Gdańsk / Varsovie', 'port': 'Radès → Gdańsk',
        'mode': 'sea', 'days': '9–14', 'freight_tnd': 1.00,
        'docs': COMMON_DOCS + ('eur1', 'phyto', 'eu_oil'),
    },
    'ca': {
        'flag': '🇨🇦', 'city': 'Montréal / Toronto', 'port': 'Radès → Montréal',
        'mode': 'sea', 'days': '18–25', 'freight_tnd': 1.40,
        'docs': COMMON_DOCS + ('phyto', 'ca_cfia', 'ca_label'),
    },
}
DEFAULT_DESTINATION = 'jp_sea'


def clean_destination(code):
    return code if code in DESTINATIONS else DEFAULT_DESTINATION


def destination_choices(lang='fr'):
    words = STRINGS[clean_lang(lang)]
    return [
        (code, f"{info['flag']} {info['city']} · {words['mode_' + info['mode']]}")
        for code, info in DESTINATIONS.items()
    ]


def route(code, lang='fr'):
    words = STRINGS[clean_lang(lang)]
    info = DESTINATIONS[clean_destination(code)]
    return {
        'code': clean_destination(code),
        'flag': info['flag'],
        'city': info['city'],
        'port': info['port'],
        'mode': words['mode_' + info['mode']],
        'days': info['days'],
        'freight_tnd': Decimal(str(info['freight_tnd'])),
        'freight_text': money(Decimal(str(info['freight_tnd'])), 'TND'),
        'docs': [words['doc_' + key] for key in info['docs']],
    }


# --------------------------------------------------------------------------
# Certifications
# --------------------------------------------------------------------------

CERTIFICATIONS = {
    'organic': {'fr': 'Bio', 'en': 'Organic', 'ja': '有機'},
    'aop': {'fr': 'AOP / IG', 'en': 'PDO / GI', 'ja': '原産地呼称'},
    'globalgap': {'fr': 'GlobalG.A.P.', 'en': 'GlobalG.A.P.', 'ja': 'GlobalG.A.P.'},
    'fairtrade': {'fr': 'Commerce équitable', 'en': 'Fair trade', 'ja': 'フェアトレード'},
    'halal': {'fr': 'Halal', 'en': 'Halal', 'ja': 'ハラール'},
}


def certification_labels(codes, lang='fr'):
    lang = clean_lang(lang)
    return [CERTIFICATIONS[c][lang] for c in codes if c in CERTIFICATIONS]


# Centres approximatifs des régions agricoles, utilisés quand l'annonce n'est
# reliée à aucune ferme géolocalisée.
REGION_COORDS = {
    'sfax': (34.74, 10.76), 'tozeur': (33.92, 8.13), 'kebili': (33.70, 8.97),
    'nabeul': (36.45, 10.73), 'cap bon': (36.85, 10.95), 'kairouan': (35.68, 10.10),
    'sousse': (35.83, 10.64), 'monastir': (35.77, 10.83), 'mahdia': (35.50, 11.06),
    'bizerte': (37.27, 9.87), 'beja': (36.73, 9.18), 'béja': (36.73, 9.18),
    'jendouba': (36.50, 8.78), 'zaghouan': (36.40, 10.14), 'sidi bouzid': (35.04, 9.48),
    'gafsa': (34.43, 8.78), 'gabes': (33.88, 10.10), 'gabès': (33.88, 10.10),
    'medenine': (33.35, 10.50), 'djerba': (33.81, 10.85), 'tunis': (36.81, 10.18),
    'ariana': (36.86, 10.19), 'manouba': (36.81, 10.10), 'ben arous': (36.75, 10.22),
    'kasserine': (35.17, 8.83), 'siliana': (36.08, 9.37), 'le kef': (36.17, 8.70),
    'tataouine': (32.93, 10.45), 'zarzis': (33.50, 11.11),
}


def origin_coords(text):
    lowered = (text or '').lower()
    for name, coords in REGION_COORDS.items():
        if name in lowered:
            return coords
    return None


# --------------------------------------------------------------------------
# Libellés FR / EN / JA (vue acheteur international)
# --------------------------------------------------------------------------

LANGUAGES = (('fr', 'FR'), ('en', 'EN'), ('ja', '日本語'))


def clean_lang(code):
    return code if code in STRINGS else 'fr'


STRINGS = {
    'fr': {
        'kicker': 'Bourse KIZUNA',
        'title': 'Vendre et échanger',
        'lead': "Les agriculteurs proposent leurs récoltes. Les acheteurs cherchent un produit, l'ouvrent et envoient une demande.",
        'mission': "Du champ tunisien à votre table, sans intermédiaire.",
        'problem': "Aujourd'hui, sur 10 € payés en rayon en Europe, l'agriculteur tunisien touche souvent moins de 1 €.",
        'promise': 'Avec KIZUNA, l’acheteur étranger traite directement avec l’agriculteur : prix visible, origine prouvée, contrat en direct.',
        'stat_farmers': 'agriculteurs vendent en direct',
        'stat_listings': 'récoltes en ligne',
        'stat_offers': 'offres d’acheteurs étrangers',
        'stat_share': 'du prix revient à l’agriculteur (contre ~10 %)',
        'how': 'Comment ça marche',
        'how_1': "L'agriculteur publie sa récolte et fixe son prix juste.",
        'how_2': "L'acheteur étranger voit l'origine, la chaîne de prix et la logistique.",
        'how_3': 'Il envoie une offre ; l’agriculteur accepte ou fait une contre-offre.',
        'search': "Rechercher un produit, une région ou un agriculteur",
        'all_categories': 'Toutes les catégories',
        'all_availability': 'Toutes disponibilités',
        'search_btn': 'Rechercher',
        'export_only': 'Prêt à l’export',
        'no_result': 'Aucune annonce ne correspond à cette recherche.',
        'harvested': 'récolté le',
        'per': 'le',
        'farmgate': 'Prix départ ferme',
        'price_on_request': 'Prix sur demande',
        'farmer_gets': "de votre paiement va à l'agriculteur",
        'my_offers': 'Mes offres',
        'calculator': 'Calculateur de prix juste',
        'language': 'Langue',
        'currency': 'Devise',
        'back': '← Vendre et échanger',
        'origin': 'Origine',
        'harvest_date': 'Date de récolte',
        'farmer': 'Agriculteur',
        'passport': "Passeport d'origine",
        'lot': 'N° de lot',
        'farm': 'Ferme',
        'certifications': 'Certifications',
        'none': 'Aucune déclarée',
        'min_order': 'Commande minimum',
        'timeline_harvest': 'Récolte',
        'timeline_listed': 'Mise en vente',
        'timeline_ship': 'Expédition possible',
        'timeline_arrival': 'Arrivée estimée',
        'chain_title': 'Où va votre argent ?',
        'chain_classic': 'Chaîne classique (5 intermédiaires)',
        'chain_direct': 'Vente directe KIZUNA',
        'chain_note': 'Ordres de grandeur indicatifs, pour une unité livrée.',
        'shelf_price': 'Prix final en rayon',
        'landed_price': 'Prix rendu acheteur',
        'farmer_share_label': "Part de l'agriculteur",
        'times': 'fois le prix payé à l’agriculteur',
        'step_farmer': 'Agriculteur',
        'step_collector': 'Collecteur local',
        'step_wholesaler': 'Grossiste / huilerie',
        'step_exporter': 'Exportateur',
        'step_importer': 'Importateur',
        'step_retail': 'Distributeur et magasin',
        'step_packing': 'Conditionnement export',
        'step_transport': 'Transport',
        'step_handling': 'Douane et manutention',
        'step_kizuna': 'Commission KIZUNA (5 %)',
        'prices_in': 'Prix dans votre devise',
        'logistics': 'Logistique export',
        'destination': 'Destination',
        'route': 'Trajet',
        'transit': 'Délai',
        'days': 'jours',
        'freight': 'Fret estimé',
        'documents': 'Documents nécessaires',
        'mode_sea': 'mer (conteneur)',
        'mode_air': 'avion',
        'doc_invoice': 'Facture commerciale',
        'doc_packing_list': 'Liste de colisage',
        'doc_origin': "Certificat d'origine",
        'doc_bill': 'Connaissement ou lettre de transport aérien',
        'doc_phyto': 'Certificat phytosanitaire (produits frais)',
        'doc_eur1': 'EUR.1 (accord UE–Tunisie, droits réduits)',
        'doc_eu_oil': "Contrôle de conformité huile d'olive (normes UE)",
        'doc_jp_notice': "Déclaration d'importation alimentaire (MHLW, quarantaine)",
        'doc_jp_residue': 'Analyse des résidus de pesticides (liste positive japonaise)',
        'doc_jp_jas': 'Certification JAS pour vendre « organic » au Japon',
        'doc_halal': 'Certificat halal',
        'doc_ca_cfia': "Exigences d'importation ACIA (Agence canadienne d'inspection des aliments)",
        'doc_ca_label': 'Étiquetage bilingue anglais / français obligatoire au Canada',
        'request_title': 'Demander une quantité',
        'request_intro': "Votre offre va directement à l'agriculteur, sans intermédiaire. Elle ne réserve pas encore la récolte.",
        'send': 'Envoyer la demande',
        'own_listing': "C'est votre annonce. Les acheteurs vous écrivent depuis cette page.",
        'closed': "Cette récolte n'est plus disponible : les demandes sont fermées.",
        'write_to': 'Écrire à',
        'edit': 'Modifier l’annonce',
        'remove': 'Retirer l’annonce',
        'story': "L'histoire de cette récolte",
        'rates_note': RATES_NOTE,
        'export_ready': 'Prêt à l’export',        'tonne_title': 'Pour 1 tonne (ou 1 000 litres)',
        'tonne_shelf': 'Prix payé en rayon via la chaîne classique',
        'tonne_direct': 'Coût pour l’acheteur en direct KIZUNA',
        'tonne_double': 'Même en payant l’agriculteur 2 fois plus, l’acheteur paie',
        'tonne_farmer': 'L’agriculteur touche alors',
        'tonne_instead': 'au lieu de',
    },
    'en': {
        'kicker': 'KIZUNA Exchange',
        'title': 'Buy direct from Tunisian farmers',
        'lead': 'Farmers list their harvest. Buyers find a product, open it and send an offer.',
        'mission': 'From Tunisian fields to your table, with no middlemen.',
        'problem': 'Today, out of €10 paid on a European shelf, a Tunisian farmer often receives less than €1.',
        'promise': 'With KIZUNA, foreign buyers deal directly with the farmer: transparent price, proven origin, direct contract.',
        'stat_farmers': 'farmers selling direct',
        'stat_listings': 'harvests online',
        'stat_offers': 'offers from foreign buyers',
        'stat_share': 'of the price goes to the farmer (vs ~10%)',
        'how': 'How it works',
        'how_1': 'The farmer lists the harvest and sets a fair price.',
        'how_2': 'The foreign buyer sees origin, price chain and logistics.',
        'how_3': 'The buyer sends an offer; the farmer accepts or counters.',
        'search': 'Search a product, region or farmer',
        'all_categories': 'All categories',
        'all_availability': 'Any availability',
        'search_btn': 'Search',
        'export_only': 'Export ready',
        'no_result': 'No listing matches this search.',
        'harvested': 'harvested on',
        'per': 'per',
        'farmgate': 'Farm-gate price',
        'price_on_request': 'Price on request',
        'farmer_gets': 'of your payment goes to the farmer',
        'my_offers': 'My offers',
        'calculator': 'Fair price calculator',
        'language': 'Language',
        'currency': 'Currency',
        'back': '← KIZUNA Exchange',
        'origin': 'Origin',
        'harvest_date': 'Harvest date',
        'farmer': 'Farmer',
        'passport': 'Origin passport',
        'lot': 'Lot no.',
        'farm': 'Farm',
        'certifications': 'Certifications',
        'none': 'None declared',
        'min_order': 'Minimum order',
        'timeline_harvest': 'Harvest',
        'timeline_listed': 'Listed',
        'timeline_ship': 'Can ship',
        'timeline_arrival': 'Estimated arrival',
        'chain_title': 'Where does your money go?',
        'chain_classic': 'Traditional chain (5 middlemen)',
        'chain_direct': 'KIZUNA direct trade',
        'chain_note': 'Indicative figures, per delivered unit.',
        'shelf_price': 'Final shelf price',
        'landed_price': 'Landed price to buyer',
        'farmer_share_label': 'Farmer share',
        'times': 'times what the farmer is paid',
        'step_farmer': 'Farmer',
        'step_collector': 'Local collector',
        'step_wholesaler': 'Wholesaler / mill',
        'step_exporter': 'Exporter',
        'step_importer': 'Importer',
        'step_retail': 'Distributor and shop',
        'step_packing': 'Export packing',
        'step_transport': 'Freight',
        'step_handling': 'Customs and handling',
        'step_kizuna': 'KIZUNA fee (5%)',
        'prices_in': 'Price in your currency',
        'logistics': 'Export logistics',
        'destination': 'Destination',
        'route': 'Route',
        'transit': 'Transit',
        'days': 'days',
        'freight': 'Estimated freight',
        'documents': 'Required documents',
        'mode_sea': 'sea (container)',
        'mode_air': 'air',
        'doc_invoice': 'Commercial invoice',
        'doc_packing_list': 'Packing list',
        'doc_origin': 'Certificate of origin',
        'doc_bill': 'Bill of lading or air waybill',
        'doc_phyto': 'Phytosanitary certificate (fresh produce)',
        'doc_eur1': 'EUR.1 (EU–Tunisia agreement, reduced duties)',
        'doc_eu_oil': 'Olive oil conformity check (EU standards)',
        'doc_jp_notice': 'Food import notification (MHLW quarantine station)',
        'doc_jp_residue': 'Pesticide residue test (Japan positive list)',
        'doc_jp_jas': 'JAS certification to sell as “organic” in Japan',
        'doc_halal': 'Halal certificate',
        'doc_ca_cfia': 'CFIA import requirements (Canadian Food Inspection Agency)',
        'doc_ca_label': 'Mandatory bilingual English / French labelling in Canada',
        'request_title': 'Make an offer',
        'request_intro': 'Your offer goes straight to the farmer, with no middleman. It does not reserve the harvest yet.',
        'send': 'Send offer',
        'own_listing': 'This is your listing. Buyers write to you from this page.',
        'closed': 'This harvest is no longer available: offers are closed.',
        'write_to': 'Write to',
        'edit': 'Edit listing',
        'remove': 'Remove listing',
        'story': 'The story of this harvest',
        'rates_note': 'Indicative rates: 1 TND ≈ €0.29 ≈ $0.32 ≈ ¥48',
        'export_ready': 'Export ready',        'tonne_title': 'For 1 tonne (or 1,000 litres)',
        'tonne_shelf': 'Shelf price through the traditional chain',
        'tonne_direct': 'Cost to the buyer with KIZUNA direct',
        'tonne_double': 'Even paying the farmer twice as much, the buyer pays',
        'tonne_farmer': 'The farmer then receives',
        'tonne_instead': 'instead of',
    },
    'ja': {
        'kicker': 'KIZUNA 取引所',
        'title': 'チュニジアの農家から直接購入',
        'lead': '農家が収穫物を出品し、バイヤーは商品を選んでオファーを送ります。',
        'mission': 'チュニジアの畑から食卓へ。中間業者なしで。',
        'problem': '現在、ヨーロッパの店頭で10ユーロの商品のうち、チュニジアの農家が受け取るのは1ユーロ未満のことが多いのです。',
        'promise': 'KIZUNAなら、海外のバイヤーが農家と直接取引。価格は透明、産地は証明済み、契約は直接。',
        'stat_farmers': '人の農家が直接販売',
        'stat_listings': '件の収穫物を掲載中',
        'stat_offers': '件の海外バイヤーからのオファー',
        'stat_share': 'が農家の手取り（従来は約10%）',
        'how': '仕組み',
        'how_1': '農家が収穫物を掲載し、公正な価格を設定します。',
        'how_2': '海外バイヤーは産地・価格の内訳・物流を確認できます。',
        'how_3': 'バイヤーがオファーを送り、農家が承諾または再提案します。',
        'search': '商品・地域・農家を検索',
        'all_categories': 'すべてのカテゴリー',
        'all_availability': 'すべての在庫状況',
        'search_btn': '検索',
        'export_only': '輸出対応',
        'no_result': '該当する商品はありません。',
        'harvested': '収穫日',
        'per': '/',
        'farmgate': '農場出荷価格',
        'price_on_request': '価格は要問合せ',
        'farmer_gets': 'がお支払いから農家へ',
        'my_offers': '私のオファー',
        'calculator': '公正価格シミュレーター',
        'language': '言語',
        'currency': '通貨',
        'back': '← KIZUNA 取引所',
        'origin': '産地',
        'harvest_date': '収穫日',
        'farmer': '生産者',
        'passport': '産地パスポート',
        'lot': 'ロット番号',
        'farm': '農園',
        'certifications': '認証',
        'none': '申告なし',
        'min_order': '最小注文数',
        'timeline_harvest': '収穫',
        'timeline_listed': '出品',
        'timeline_ship': '出荷可能',
        'timeline_arrival': '到着予定',
        'chain_title': 'あなたのお金はどこへ？',
        'chain_classic': '従来の流通（中間業者5社）',
        'chain_direct': 'KIZUNA 直接取引',
        'chain_note': '1単位あたりの参考値です。',
        'shelf_price': '最終店頭価格',
        'landed_price': 'バイヤー着価格',
        'farmer_share_label': '農家の取り分',
        'times': '倍（農家の受取額に対して）',
        'step_farmer': '農家',
        'step_collector': '地元の集荷業者',
        'step_wholesaler': '卸売・搾油所',
        'step_exporter': '輸出業者',
        'step_importer': '輸入業者',
        'step_retail': '流通・小売店',
        'step_packing': '輸出用梱包',
        'step_transport': '輸送',
        'step_handling': '通関・荷役',
        'step_kizuna': 'KIZUNA手数料（5%）',
        'prices_in': '各通貨での価格',
        'logistics': '輸出物流',
        'destination': '仕向地',
        'route': 'ルート',
        'transit': '輸送日数',
        'days': '日',
        'freight': '運賃（概算）',
        'documents': '必要書類',
        'mode_sea': '海上（コンテナ）',
        'mode_air': '航空',
        'doc_invoice': '商業送り状（インボイス）',
        'doc_packing_list': 'パッキングリスト',
        'doc_origin': '原産地証明書',
        'doc_bill': '船荷証券または航空運送状',
        'doc_phyto': '植物検疫証明書（生鮮品）',
        'doc_eur1': 'EUR.1（EU・チュニジア協定）',
        'doc_eu_oil': 'オリーブオイル適合検査（EU基準）',
        'doc_jp_notice': '食品等輸入届出（厚生労働省 検疫所）',
        'doc_jp_residue': '残留農薬検査（ポジティブリスト制度）',
        'doc_jp_jas': '「有機」表示には有機JAS認証が必要',
        'doc_halal': 'ハラール証明書',
        'doc_ca_cfia': 'CFIA（カナダ食品検査庁）の輸入要件',
        'doc_ca_label': 'カナダでは英語・フランス語の二言語表示が義務',
        'request_title': 'オファーを送る',
        'request_intro': 'オファーは中間業者を通さず農家に直接届きます。まだ在庫は確保されません。',
        'send': 'オファーを送信',
        'own_listing': 'あなたの出品です。バイヤーはこのページから連絡します。',
        'closed': 'この収穫物は販売終了です。',
        'write_to': 'メッセージを送る：',
        'edit': '出品を編集',
        'remove': '出品を取り下げる',
        'story': 'この収穫物の物語',
        'rates_note': '参考レート：1 TND ≈ 0.29ユーロ ≈ 0.32ドル ≈ 48円',
        'export_ready': '輸出対応',        'tonne_title': '1トン（1,000リットル）あたり',
        'tonne_shelf': '従来の流通での店頭価格',
        'tonne_direct': 'KIZUNA直接取引でのバイヤーのコスト',
        'tonne_double': '農家に2倍支払っても、バイヤーの支払いは',
        'tonne_farmer': '農家の受取額',
        'tonne_instead': '従来：',
    },
}

CATEGORY_LABELS = {
    'olive': {'fr': 'Olives', 'en': 'Olives', 'ja': 'オリーブ'},
    'oil': {'fr': 'Huile', 'en': 'Oil', 'ja': 'オイル'},
    'vegetable': {'fr': 'Légumes', 'en': 'Vegetables', 'ja': '野菜'},
    'fruit': {'fr': 'Fruits', 'en': 'Fruit', 'ja': '果物'},
    'grain': {'fr': 'Céréales', 'en': 'Grain', 'ja': '穀物'},
    'herb': {'fr': 'Herbes', 'en': 'Herbs', 'ja': 'ハーブ'},
    'other': {'fr': 'Autre', 'en': 'Other', 'ja': 'その他'},
}

UNIT_LABELS = {
    'kg': {'fr': 'kg', 'en': 'kg', 'ja': 'kg'},
    'litre': {'fr': 'litre', 'en': 'litre', 'ja': 'リットル'},
    'crate': {'fr': 'caisse', 'en': 'crate', 'ja': 'ケース'},
    'bunch': {'fr': 'botte', 'en': 'bunch', 'ja': '束'},
    'piece': {'fr': 'pièce', 'en': 'piece', 'ja': '個'},
}

AVAILABILITY_LABELS = {
    'available': {'fr': 'Disponible', 'en': 'Available', 'ja': '在庫あり'},
    'limited': {'fr': 'Limitée', 'en': 'Limited', 'ja': '残りわずか'},
    'unavailable': {'fr': 'Indisponible', 'en': 'Unavailable', 'ja': '在庫なし'},
}


def chain_labels(steps, lang):
    words = STRINGS[clean_lang(lang)]
    for step in steps:
        step['label'] = words['step_' + step['key']]
    return steps
