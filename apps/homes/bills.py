"""Facture prédite STEG (électricité) et SONEDE (eau) d'une maison.

Les volumes viennent des appareils saisis par le citoyen et d'une durée
d'usage typique par type d'appareil : ce sont des estimations, pas des
relevés de compteur. Les barèmes ci-dessous sont indicatifs (tarifs
résidentiels basse tension STEG et domestiques SONEDE) : mettez-les à jour
ici si les tarifs officiels changent.
"""

from dataclasses import dataclass
from datetime import date

# Heures d'usage par jour, par type d'appareil (moyenne sur l'année).
DAILY_HOURS = {
    'ac': 5.0,
    'tv': 4.0,
    'refrigerator': 9.0,      # le compresseur tourne environ 35 % du temps
    'washing_machine': 0.8,
    'dishwasher': 0.7,
    'water_heater': 2.0,
    'lights': 5.0,
    'pump': 1.0,
}
# Eau du quotidien hors appareils (douche, cuisine, ménage), par habitant.
LITERS_PER_PERSON_PER_DAY = 90

# STEG, tarif résidentiel, en kWh par mois et dinars par kWh.
# Jusqu'à 200 kWh/mois, les tranches sont progressives. Au-delà, toute la
# consommation est payée au prix de la tranche atteinte : d'où l'alerte.
STEG_TIERS = (
    (50, 0.062),
    (100, 0.096),
    (200, 0.176),
    (300, 0.218),
    (500, 0.341),
    (None, 0.414),
)
STEG_PROGRESSIVE_UP_TO = 200
STEG_FIXED_PER_MONTH = 0.700
STEG_TAX_RATE = 0.13
STEG_PERIOD_MONTHS = 2

# SONEDE, usage domestique, en m³ par trimestre et dinars par m³ (progressif).
SONEDE_TIERS = (
    (20, 0.200),
    (40, 0.740),
    (70, 1.040),
    (100, 1.490),
    (150, 1.770),
    (None, 2.310),
)
SONEDE_FIXED_PER_QUARTER = 4.500
SONEDE_TAX_RATE = 0.07
SONEDE_PERIOD_MONTHS = 3

# Alerte quand il reste moins de 15 % avant la tranche suivante.
WARN_MARGIN = 0.15


@dataclass
class Period:
    start: date
    end: date
    days: int
    elapsed: int


def _period(today, months):
    first_month = ((today.month - 1) // months) * months + 1
    start = date(today.year, first_month, 1)
    end_month = first_month + months
    end = date(today.year + (end_month - 1) // 12, (end_month - 1) % 12 + 1, 1)
    return Period(start, end, (end - start).days, (today - start).days + 1)


def daily_use(home):
    """kWh et litres par jour, à partir des appareils actifs et des habitants."""
    kwh = 0.0
    liters = home.residents * LITERS_PER_PERSON_PER_DAY
    for item in home.appliances.all():
        if not item.is_active:
            continue
        hours = DAILY_HOURS.get(item.kind, 2.0)
        kwh += item.power_watts * hours / 1000
        liters += float(item.water_liters_per_hour) * min(hours, 2.0)
    return round(kwh, 2), round(liters, 1)


def _tier_index(tiers, amount):
    for index, (limit, _price) in enumerate(tiers):
        if limit is None or amount <= limit:
            return index
    return len(tiers) - 1


def _progressive(tiers, amount):
    total, floor = 0.0, 0
    for limit, price in tiers:
        top = amount if limit is None else min(amount, limit)
        if top > floor:
            total += (top - floor) * price
        if limit is None or amount <= limit:
            break
        floor = limit
    return total


def steg_cost(kwh_per_month):
    if kwh_per_month <= STEG_PROGRESSIVE_UP_TO:
        energy = _progressive(STEG_TIERS, kwh_per_month)
    else:
        energy = kwh_per_month * STEG_TIERS[_tier_index(STEG_TIERS, kwh_per_month)][1]
    return (energy + STEG_FIXED_PER_MONTH) * (1 + STEG_TAX_RATE)


def sonede_cost(m3_per_quarter):
    return (_progressive(SONEDE_TIERS, m3_per_quarter) + SONEDE_FIXED_PER_QUARTER) * (1 + SONEDE_TAX_RATE)


def _tier_alert(tiers, projected, so_far, per_day, unit, days_left, label):
    """Prévient avant de passer à une tranche plus chère."""
    index = _tier_index(tiers, projected)
    limit, price = tiers[index]
    status = 'ok'
    message = f'Vous restez dans la tranche à {price:.3f} DT/{unit}.'
    previous_limit = tiers[index - 1][0] if index else 0
    # Tranche déjà dépassée par la projection : on dit quand cela arrivera.
    if index and so_far <= previous_limit < projected:
        remaining = previous_limit - so_far
        days = int(remaining / per_day) if per_day else days_left
        status = 'danger'
        message = (
            f'Au rythme actuel, vous passerez à la tranche {label} plus chère '
            f'({price:.3f} DT/{unit}) dans environ {days} jour{"s" if days > 1 else ""}. '
            f'Il vous reste {remaining:.0f} {unit} avant ce seuil.'
        )
    elif limit is not None and projected >= limit * (1 - WARN_MARGIN):
        next_price = tiers[index + 1][1]
        status = 'warning'
        message = (
            f'Attention : vous êtes à {limit - projected:.0f} {unit} de la tranche '
            f'suivante ({next_price:.3f} DT/{unit}). Réduisez un peu pour rester en dessous.'
        )
    return {'status': status, 'message': message, 'tier': index + 1, 'price': price}


def predict_bills(home, today=None):
    today = today or date.today()
    kwh_day, liters_day = daily_use(home)

    steg = _period(today, STEG_PERIOD_MONTHS)
    kwh_month = kwh_day * 30
    steg_alert = _tier_alert(
        STEG_TIERS,
        projected=kwh_month,
        so_far=kwh_day * today.day,
        per_day=kwh_day,
        unit='kWh',
        days_left=max(30 - today.day, 0),
        label='STEG',
    )
    if kwh_month > STEG_PROGRESSIVE_UP_TO and steg_alert['status'] != 'danger':
        steg_alert['status'] = 'warning'
        steg_alert['message'] += (
            ' Au-delà de 200 kWh par mois, toute votre consommation est payée au prix fort.'
        )

    sonede = _period(today, SONEDE_PERIOD_MONTHS)
    m3_quarter = liters_day * sonede.days / 1000
    m3_so_far = liters_day * sonede.elapsed / 1000
    sonede_alert = _tier_alert(
        SONEDE_TIERS,
        projected=m3_quarter,
        so_far=m3_so_far,
        per_day=liters_day / 1000,
        unit='m³',
        days_left=sonede.days - sonede.elapsed,
        label='SONEDE',
    )

    return {
        'estimated': True,
        'electricity': {
            'provider': 'STEG',
            'kwh_per_day': kwh_day,
            'kwh_period': round(kwh_day * steg.days),
            'amount': round(steg_cost(kwh_month) * STEG_PERIOD_MONTHS, 1),
            'cost_today': round(steg_cost(kwh_month) / 30, 2),
            'period_end': steg.end,
            'progress': round(100 * steg.elapsed / steg.days),
            'alert': steg_alert,
        },
        'water': {
            'provider': 'SONEDE',
            'liters_per_day': liters_day,
            'm3_period': round(m3_quarter, 1),
            'amount': round(sonede_cost(m3_quarter), 1),
            'period_end': sonede.end,
            'progress': round(100 * sonede.elapsed / sonede.days),
            'alert': sonede_alert,
        },
    }
