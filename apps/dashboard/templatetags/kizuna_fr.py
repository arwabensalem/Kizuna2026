"""Affichage en français des mots techniques venus de la simulation.

Les données restent en anglais en base et dans l'API ; seule la page
les montre en français. Le même dictionnaire existe côté navigateur
dans static/js/main.js (window.kzFr) pour les mises à jour en direct.
"""

import re

from django import template

register = template.Library()

WORDS = {
    'COMBINED_CRISIS': 'Crise combinée',
    'POWER_OUTAGE': 'Coupure de courant',
    'HEAVY_RAIN': 'Fortes pluies',
    'REAL_WEATHER': 'Météo réelle',
    'HEATWAVE': 'Canicule',
    'DROUGHT': 'Sécheresse',
    'NORMAL': 'Normal',
    'WATCH': 'Vigilance',
    'ALERT': 'Alerte',
    'CRISIS': 'Crise',
    'CONTAINED': 'maîtrisée',
    'ACTIVE': 'en cours',
    'AVAILABLE': 'Disponible',
    'OUT': 'Coupé',
    'HIGH': 'Bon',
    'MEDIUM': 'Moyen',
    'LOW': 'Faible',
    'Up': 'En service',
    'Down': 'Coupé',
    'On': 'En marche',
    'Off': 'À l’arrêt',
    'Scenario': 'Situation :',
    'Water availability': 'Eau disponible',
    'Solar production': 'Production solaire',
    'Soil moisture': 'Humidité du sol',
    'Rain probability': 'Risque de pluie',
    'Rainfall': 'Pluie',
    'Temperature': 'Température',
    'Grid': 'Réseau électrique',
    'home tank': 'réservoir de la maison',
    'power reserve available': 'réserve d’énergie disponible',
    'no power reserve': 'pas de réserve d’énergie',
    'crops watered or soil': 'cultures arrosées ou sol',
    'and the pump is off': 'et pompe à l’arrêt',
    'Running': 'En marche',
    'Idle': 'À l’arrêt',
    'Configured': 'Configurée',
    'Not set': 'Non définie',
    'Stable': 'Stable',
    'Watch': 'À surveiller',
    'Stressed': 'En difficulté',
}

FLOW_WORDS = {
    'Battery': 'Batterie',
    'Home': 'Maison',
    'Farm': 'Ferme',
    'Business': 'Atelier',
    'Workshop': 'Atelier',
    'Tank': 'Réservoir',
    'Solar': 'Solaire',
    'Grid': 'Réseau',
    'Neighbourhood': 'Quartier',
    'Neighborhood': 'Quartier',
}


def _pattern(words):
    keys = sorted(words, key=len, reverse=True)
    return re.compile(r'(?<![\w])(' + '|'.join(re.escape(k) for k in keys) + r')(?![\w])')


_WORDS_RE = _pattern(WORDS)
_FLOW_RE = _pattern(FLOW_WORDS)


@register.filter
def fr(value):
    if value is None:
        return value
    return _WORDS_RE.sub(lambda m: WORDS[m.group(1)], str(value))


@register.filter
def fr_flow(value):
    if value is None:
        return value
    return _FLOW_RE.sub(lambda m: FLOW_WORDS[m.group(1)], str(value))


# Types de pièces et d'appareils, par valeur enregistrée.
KINDS = {
    'bedroom': 'Chambre',
    'bathroom': 'Salle de bain',
    'kitchen': 'Cuisine',
    'living_room': 'Salon',
    'garden': 'Jardin',
    'pool': 'Piscine',
    'garage': 'Garage',
    'other': 'Autre',
    'ac': 'Climatiseur',
    'tv': 'Télévision',
    'refrigerator': 'Réfrigérateur',
    'washing_machine': 'Machine à laver',
    'dishwasher': 'Lave-vaisselle',
    'water_heater': 'Chauffe-eau',
    'lights': 'Éclairage',
    'pump': 'Pompe',
    'seedling': 'semis',
    'vegetative': 'croissance',
    'flowering': 'floraison',
    'fruiting': 'fructification',
    'harvest': 'récolte',
}


@register.filter
def fr_choice(value):
    """Libellé anglais d'un choix de modèle (get_..._display) en français."""
    from apps.accounts.fr import CHOICES
    return CHOICES.get(str(value), value)


@register.filter
def fr_kind(value):
    return KINDS.get(str(value), value)


@register.filter
def fr_appliance(item):
    """Nom d'un appareil : son nom libre, sinon son type en français."""
    return item.label or KINDS.get(item.kind, item.get_kind_display())
