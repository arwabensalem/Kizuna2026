"""Conseiller de la ferme : quand arroser, combien, quand récolter et à quel prix.

Méthode FAO-56 simplifiée : besoin = ET0 du mois × coefficient de la culture,
corrigé par l'humidité du sol (deux profondeurs) et la pluie prévue. Les
rendements et prix de référence sont des moyennes indicatives pour la
Tunisie ; quand le Marché KIZUNA contient des offres de la même culture,
leur prix moyen remplace la référence.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Avg

# Évapotranspiration de référence ET0 (mm/jour), moyenne Tunisie, par mois.
ET0_BY_MONTH = {1: 1.6, 2: 2.2, 3: 3.1, 4: 4.2, 5: 5.4, 6: 6.5,
                7: 7.1, 8: 6.6, 9: 5.0, 10: 3.6, 11: 2.3, 12: 1.6}

# Coefficient cultural Kc par culture et stade.
KC = {
    'olive': {'seedling': 0.5, 'vegetative': 0.6, 'flowering': 0.65, 'fruiting': 0.7, 'harvest': 0.55},
    'tomato': {'seedling': 0.6, 'vegetative': 0.85, 'flowering': 1.15, 'fruiting': 1.1, 'harvest': 0.8},
    'wheat': {'seedling': 0.4, 'vegetative': 0.8, 'flowering': 1.15, 'fruiting': 0.9, 'harvest': 0.3},
    'pepper': {'seedling': 0.6, 'vegetative': 0.8, 'flowering': 1.05, 'fruiting': 1.0, 'harvest': 0.85},
    'barley': {'seedling': 0.4, 'vegetative': 0.8, 'flowering': 1.1, 'fruiting': 0.85, 'harvest': 0.3},
    'citrus': {'seedling': 0.6, 'vegetative': 0.65, 'flowering': 0.7, 'fruiting': 0.7, 'harvest': 0.65},
    'date': {'seedling': 0.8, 'vegetative': 0.9, 'flowering': 0.95, 'fruiting': 0.95, 'harvest': 0.9},
    'almond': {'seedling': 0.4, 'vegetative': 0.75, 'flowering': 0.9, 'fruiting': 0.9, 'harvest': 0.65},
    'grape': {'seedling': 0.3, 'vegetative': 0.6, 'flowering': 0.7, 'fruiting': 0.7, 'harvest': 0.45},
    'potato': {'seedling': 0.5, 'vegetative': 0.9, 'flowering': 1.15, 'fruiting': 1.0, 'harvest': 0.75},
    'fig': {'seedling': 0.5, 'vegetative': 0.65, 'flowering': 0.75, 'fruiting': 0.75, 'harvest': 0.6},
    'other': {'seedling': 0.6, 'vegetative': 0.8, 'flowering': 0.95, 'fruiting': 0.9, 'harvest': 0.7},
}

EFFICIENCY = {'drip': 0.9, 'sprinkler': 0.75, 'furrow': 0.6, 'none': 0.6}

# Humidité volumique visée (%) : en dessous de LOW on arrose, au-dessus de HIGH c'est inutile.
TARGET = {'sand': (18, 28), 'loam': (28, 40), 'silt': (30, 42), 'clay': (34, 46), 'rocky': (16, 26)}
ROOT_DEPTH_MM = 400
DEFAULT_PUMP_M3_PER_HOUR = 2.0

# Rendement (kg/m²), prix local de référence (DT/kg), mois habituels de récolte.
REFERENCE = {
    'olive': (0.35, 1.6, (11, 12, 1), 'olive'),
    'tomato': (6.0, 1.2, (6, 7, 8), 'vegetable'),
    'wheat': (0.28, 0.95, (6, 7), 'grain'),
    'pepper': (2.5, 1.8, (7, 8, 9), 'vegetable'),
    'barley': (0.22, 0.8, (5, 6), 'grain'),
    'citrus': (2.5, 1.3, (12, 1, 2, 3), 'fruit'),
    'date': (0.6, 5.5, (10, 11, 12), 'fruit'),
    'almond': (0.12, 9.0, (8, 9), 'fruit'),
    'grape': (1.2, 2.2, (8, 9), 'fruit'),
    'potato': (2.5, 1.1, (3, 4, 5, 6), 'vegetable'),
    'fig': (0.8, 3.5, (8, 9), 'fruit'),
    'other': (1.0, 1.0, (), 'other'),
}
DAYS_TO_HARVEST = {'seedling': 110, 'vegetative': 75, 'flowering': 50, 'fruiting': 25, 'harvest': 0}


def soil_reading(shallow, deep):
    """Moyenne pondérée : les racines puisent surtout entre 0 et 30 cm."""
    return round(0.6 * shallow + 0.4 * deep, 1)


def pump_flow(farm):
    flows = [float(item.flow_liters_per_hour) for item in farm.irrigation_systems.all() if item.flow_liters_per_hour]
    return round(sum(flows) / 1000, 2) if flows else DEFAULT_PUMP_M3_PER_HOUR


def _next_harvest_month(months, today):
    for offset in range(0, 13):
        month = (today.month - 1 + offset) % 12 + 1
        if month in months:
            year = today.year + (today.month - 1 + offset) // 12
            return date(year, month, 15)
    return None


def _market_price(category, fallback):
    from apps.marketplace.models import Product

    # Seules les offres comparables comptent : un produit transformé (piment séché,
    # tomates séchées…) vaut bien plus cher au kilo que la récolte fraîche.
    low, high = round(fallback * 0.5, 2), round(fallback * 3, 2)
    found = Product.objects.filter(
        category=category, unit='kg', price_tnd__isnull=False,
        price_tnd__gte=low, price_tnd__lte=high,
    )
    average = found.aggregate(value=Avg('price_tnd'))['value']
    if average:
        return round(float(average), 2), f'moyenne de {found.count()} offre(s) du Marché KIZUNA'
    return fallback, 'prix de référence du marché local'


def advise(farm, shallow, deep, rain_mm_48h, today=None, now_hour=12):
    today = today or date.today()
    low, high = TARGET.get(farm.soil_type, TARGET['loam'])
    moisture = soil_reading(shallow, deep)
    et0 = ET0_BY_MONTH[today.month]
    efficiency = EFFICIENCY.get(farm.irrigation_type, 0.75)
    flow = pump_flow(farm)

    crops = list(farm.crops.all())
    if not crops:
        crops = [_WholeFarm(farm)]

    parcels, total_m3 = [], 0.0
    for crop in crops:
        kind = _kind(crop, farm)
        kc = KC.get(kind, KC['other']).get(crop.stage, 0.8)
        need_mm_day = et0 * kc
        # Déficit pour remonter le sol jusqu'au haut de la zone visée.
        deficit_mm = max(high - moisture, 0) / 100 * ROOT_DEPTH_MM
        net_mm = max(deficit_mm - rain_mm_48h * 0.8, 0)
        volume = net_mm * float(crop.area_m2) / 1000 / efficiency
        minutes = round(volume / flow * 60) if flow else 0
        total_m3 += volume
        parcels.append({
            'name': crop.name,
            'area_m2': float(crop.area_m2),
            'stage': crop.stage,
            'need_mm_day': round(need_mm_day, 1),
            'volume_m3': round(volume, 1),
            'minutes': minutes,
            'duration': _duration(minutes),
        })

    if rain_mm_48h >= 5 and moisture >= low - 4:
        decision = {
            'status': 'rain', 'title': 'Inutile d’arroser, la pluie arrive',
            'text': f'{rain_mm_48h:g} mm de pluie sont prévus dans les 48 heures : votre sol ({moisture:g} %) tiendra jusque-là.',
        }
        for parcel in parcels:
            parcel.update(volume_m3=0, minutes=0, duration='—')
        total_m3 = 0
    elif moisture >= high:
        decision = {
            'status': 'ok', 'title': 'Pas besoin d’arroser aujourd’hui',
            'text': f'Le sol est assez humide ({moisture:g} %, zone idéale {low}–{high} %). Revérifiez demain.',
        }
        total_m3 = 0
    elif moisture >= low:
        decision = {
            'status': 'soon', 'title': 'Arrosez demain matin',
            'text': f'Le sol commence à sécher ({moisture:g} %). Arrosez demain entre 5 h et 8 h, quand l’évaporation est la plus faible.',
        }
    else:
        when = 'ce soir après 19 h' if now_hour >= 11 else 'maintenant, avant 9 h'
        decision = {
            'status': 'now', 'title': 'Arrosez aujourd’hui',
            'text': f'Le sol est sec ({moisture:g} %, en dessous de {low} %). Arrosez {when} pour limiter l’évaporation.',
        }
    if decision['status'] == 'soon' and deep < shallow - 8:
        decision['text'] += ' Le sol profond est plus sec que la surface : préférez un arrosage long et lent.'

    harvests = [_harvest(farm, crop, today) for crop in crops]
    return {
        'moisture': moisture,
        'target': (low, high),
        'et0': et0,
        'rain_mm_48h': rain_mm_48h,
        'pump_m3_per_hour': flow,
        'decision': decision,
        'parcels': parcels,
        'total_m3': round(total_m3, 1),
        'total_duration': _duration(round(total_m3 / flow * 60) if flow else 0),
        'harvests': harvests,
    }


def _harvest(farm, crop, today):
    kind = _kind(crop, farm)
    per_m2, ref_price, months, category = REFERENCE.get(kind, REFERENCE['other'])
    by_stage = today + timedelta(days=DAYS_TO_HARVEST.get(crop.stage, 60))
    seasonal = _next_harvest_month(months, by_stage) if months else None
    when = max(by_stage, seasonal) if seasonal else by_stage
    stress = 1.0
    yield_kg = round(per_m2 * float(crop.area_m2) * stress)
    price, source = _market_price(category, ref_price)
    return {
        'name': crop.name,
        'date': when,
        'yield_kg': yield_kg,
        'price_kg': price,
        'price_source': source,
        'revenue': round(yield_kg * price),
    }


def _kind(crop, farm):
    kind = getattr(crop, 'kind', None)
    return kind if kind and kind != 'other' else farm.crop_type


def _duration(minutes):
    if minutes <= 0:
        return '—'
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f'{rest} min'
    return f'{hours} h {rest:02d}' if rest else f'{hours} h'


class _WholeFarm:
    """Quand aucune parcelle n'est saisie, la ferme entière compte pour une parcelle."""

    def __init__(self, farm):
        self.name = 'Toute la ferme'
        self.area_m2 = farm.area_m2 or Decimal('0')
        self.stage = 'vegetative'
        self.kind = farm.crop_type
