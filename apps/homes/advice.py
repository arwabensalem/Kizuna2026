"""Alertes et conseils du jour pour une maison.

Règles simples et lisibles, calculées sur les appareils saisis, l'heure
locale et les anomalies déjà détectées. Rien n'est inventé : sans donnée,
pas de conseil.
"""

import math

from django.urls import reverse
from django.utils import timezone

from apps.homes.simulation import simulate_home

FRIDGE_NORMAL_WATTS = 150
FRIDGE_ABNORMAL_WATTS = 250
AC_ECO_SETPOINT = 24
AC_SAVING_PER_DEGREE = 7  # % d'électricité économisée par degré en plus
SHIFTABLE = {
    'washing_machine': 'la machine à laver',
    'dishwasher': 'le lave-vaisselle',
    'water_heater': 'le chauffe-eau',
    'pump': 'la pompe du réservoir',
}


def solar_now(home, hour):
    """Production solaire attendue à cette heure (courbe en cloche 6 h → 19 h)."""
    peak = simulate_home(home)['solar_watts']
    if hour < 6 or hour > 19:
        return 0
    return round(peak * math.sin(math.pi * (hour - 6) / 13))


def home_advice(home, now=None):
    now = timezone.localtime(now) if now else timezone.localtime()
    hour = now.hour
    appliances = list(home.appliances.all())
    tips = []

    # Fuite : l'eau coule en continu pendant la nuit.
    leak = home.anomaly_events.filter(
        status='open', resource='water', type__in=('possible_leak', 'critical_abnormal'),
    ).order_by('-id').first()
    if leak:
        tips.append({
            'level': 'danger', 'icon': 'alert', 'title': 'Fuite d’eau probable',
            'text': leak.summary or 'L’eau coule en continu alors que personne ne l’utilise.',
            'link': reverse('homes:anomalies', args=[home.pk]), 'action': 'Voir et fermer la vanne',
        })

    for item in appliances:
        if item.kind == 'refrigerator' and item.power_watts >= FRIDGE_ABNORMAL_WATTS:
            extra = round(100 * (item.power_watts - FRIDGE_NORMAL_WATTS) / FRIDGE_NORMAL_WATTS)
            tips.append({
                'level': 'warning', 'icon': 'alert', 'title': f'{item.display_name} consomme anormalement',
                'text': (
                    f'{item.power_watts} W, soit environ {extra} % de plus qu’un frigo normal '
                    f'(~{FRIDGE_NORMAL_WATTS} W). Vérifiez le joint de la porte, le givre et '
                    'la grille arrière.'
                ),
            })
        if item.kind == 'ac' and item.is_active and item.temperature_setpoint is not None:
            setpoint = float(item.temperature_setpoint)
            if setpoint < AC_ECO_SETPOINT:
                gap = round(AC_ECO_SETPOINT + 2 - setpoint)
                tips.append({
                    'level': 'warning', 'icon': 'sun', 'title': f'{item.display_name} réglée trop bas',
                    'text': (
                        f'Réglée à {setpoint:g} °C. Passez à {AC_ECO_SETPOINT + 2} °C : '
                        f'environ {gap * AC_SAVING_PER_DEGREE} % d’électricité en moins, '
                        'pour un confort presque identique.'
                    ),
                })

    # Solaire intelligent : décaler les gros appareils quand les panneaux produisent.
    solar = solar_now(home, hour)
    load = sum(item.power_watts for item in appliances if item.is_active)
    spare = solar - load
    waiting = [item for item in appliances if item.kind in SHIFTABLE and not item.is_active]
    if not home.has_solar_panels:
        waiting = []
    if waiting and spare >= 500:
        item = waiting[0]
        tips.append({
            'level': 'success', 'icon': 'sun', 'title': 'Vos panneaux produisent',
            'text': (
                f'Lancez {SHIFTABLE[item.kind]} maintenant : il reste environ {spare} W de '
                'production solaire gratuite.'
            ),
        })
    elif waiting and 6 <= hour < 11:
        tips.append({
            'level': 'info', 'icon': 'sun', 'title': 'Attendez le soleil',
            'text': f'Programmez {SHIFTABLE[waiting[0].kind]} entre 11 h et 15 h, quand vos panneaux produisent le plus.',
        })
    return {'tips': tips, 'solar_watts': solar, 'hour': hour}
