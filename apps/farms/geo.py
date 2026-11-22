"""Lieux de Tunisie pour placer une ferme sur la carte.

Coordonnées approximatives du centre de chaque ville. Utilisées quand
l'agriculteur tape un lieu (« Bizerte », « Menzel Bourguiba »…) et pour
refuser des coordonnées hors de Tunisie.
"""

import re
import unicodedata

# Rectangle qui contient toute la Tunisie (terre et îles).
BOUNDS = {'south': 30.2, 'north': 37.6, 'west': 7.5, 'east': 11.7}
CENTER = (34.0, 9.5)

PLACES = {
    # Chefs-lieux des 24 gouvernorats
    'Tunis': (36.8065, 10.1815), 'Ariana': (36.8625, 10.1956), 'Ben Arous': (36.7531, 10.2189),
    'Manouba': (36.8080, 10.0972), 'Nabeul': (36.4561, 10.7376), 'Bizerte': (37.2744, 9.8739),
    'Sousse': (35.8256, 10.6369), 'Monastir': (35.7643, 10.8113), 'Mahdia': (35.5047, 11.0622),
    'Sfax': (34.7406, 10.7603), 'Béja': (36.7256, 9.1817), 'Jendouba': (36.5011, 8.7802),
    'Le Kef': (36.1742, 8.7049), 'Siliana': (36.0849, 9.3708), 'Zaghouan': (36.4029, 10.1429),
    'Kairouan': (35.6781, 10.0963), 'Kasserine': (35.1676, 8.8365), 'Sidi Bouzid': (35.0382, 9.4849),
    'Gabès': (33.8815, 10.0982), 'Médenine': (33.3549, 10.5055), 'Tataouine': (32.9297, 10.4518),
    'Gafsa': (34.4250, 8.7842), 'Tozeur': (33.9197, 8.1335), 'Kébili': (33.7044, 8.9690),
    # Villes agricoles et délégations fréquentes
    'Menzel Bourguiba': (37.1536, 9.7856), 'Mateur': (37.0400, 9.6650), 'Ras Jebel': (37.2150, 10.1200),
    'Ghar El Melh': (37.1690, 10.1900), 'Utique': (37.0560, 10.0620), 'Sejnane': (37.0560, 9.2380),
    'Hammamet': (36.4000, 10.6167), 'Kélibia': (36.8475, 11.0939), 'Korba': (36.5786, 10.8586),
    'Menzel Temime': (36.7826, 10.9874), 'Grombalia': (36.6000, 10.5000), 'Soliman': (36.6942, 10.4906),
    'El Haouaria': (37.0500, 11.0100), 'Béni Khalled': (36.6500, 10.6000), 'Takelsa': (36.7900, 10.6300),
    'Testour': (36.5508, 9.4431), 'Medjez El Bab': (36.6500, 9.6167), 'Téboursouk': (36.4570, 9.2480),
    'Bou Salem': (36.6110, 8.9700), 'Tabarka': (36.9544, 8.7580), 'Aïn Draham': (36.7790, 8.6870),
    'Fernana': (36.6550, 8.6950), 'Dahmani': (35.9450, 8.8300), 'Tajerouine': (35.8920, 8.5530),
    'Makthar': (35.8580, 9.2050), 'Gaâfour': (36.3220, 9.3260), 'El Fahs': (36.3740, 9.9060),
    'Enfida': (36.1350, 10.3810), 'Msaken': (35.7290, 10.5800), 'Kalâa Kebira': (35.8700, 10.5300),
    'Sidi Bou Ali': (35.9570, 10.4730), 'Moknine': (35.6290, 10.9000), 'Jemmal': (35.6230, 10.7590),
    'Ksar Hellal': (35.6430, 10.8910), 'El Jem': (35.2967, 10.7128), 'Chebba': (35.2370, 11.1150),
    'Ksour Essef': (35.4180, 10.9940), 'Sbeitla': (35.2300, 9.1300), 'Fériana': (34.9500, 8.5670),
    'Thala': (35.5730, 8.6710), 'Regueb': (34.8590, 9.7860), 'Meknassy': (34.6060, 9.6050),
    'Menzel Bouzaiane': (34.5780, 9.4450), 'Haffouz': (35.6330, 9.6750), 'Sbikha': (35.9330, 10.0200),
    'Hajeb El Ayoun': (35.3900, 9.5450), 'Bou Hajla': (35.3190, 10.0490), 'Jebeniana': (35.0350, 10.9080),
    'Mahrès': (34.5290, 10.5000), 'Agareb': (34.7440, 10.5280), 'Skhira': (34.2990, 10.0700),
    'Bir Ali Ben Khalifa': (34.7370, 10.1000), 'El Hencha': (35.0010, 10.7330), 'Menzel Chaker': (34.9640, 10.3600),
    'Kerkennah': (34.7080, 11.1650), 'Mareth': (33.6280, 10.2950), 'El Hamma': (33.8920, 9.7960),
    'Matmata': (33.5440, 9.9670), 'Zarzis': (33.5036, 11.1122), 'Djerba': (33.8070, 10.8500),
    'Houmt Souk': (33.8750, 10.8570), 'Ben Gardane': (33.1380, 11.2190), 'Remada': (32.3060, 10.3960),
    'Metlaoui': (34.3200, 8.4000), 'Redeyef': (34.3830, 8.1560), 'El Guettar': (34.3370, 8.9500),
    'Nefta': (33.8730, 7.8770), 'Degache': (33.9790, 8.2150), 'Douz': (33.4570, 9.0230),
    'Souk Lahad': (33.7890, 8.8460), 'La Marsa': (36.8782, 10.3247), 'Mornag': (36.6800, 10.2900),
    'Mohamedia': (36.6750, 10.1560), 'Tebourba': (36.8290, 9.8410), 'Mornaguia': (36.7590, 10.0130),
}

ALIASES = {
    'el kef': 'Le Kef', 'kef': 'Le Kef', 'jerba': 'Djerba', 'kerkena': 'Kerkennah',
    'medenine': 'Médenine', 'gabes': 'Gabès', 'beja': 'Béja', 'kebili': 'Kébili',
    'menzel bourguiba': 'Menzel Bourguiba', 'kelibia': 'Kélibia', 'mahres': 'Mahrès',
    'ben arous': 'Ben Arous', 'bizert': 'Bizerte', 'binzart': 'Bizerte', 'banzart': 'Bizerte',
    'benzart': 'Bizerte', 'souse': 'Sousse', 'sousa': 'Sousse', 'qayrawan': 'Kairouan', 'kairawan': 'Kairouan',
    'nabel': 'Nabeul', 'monastyr': 'Monastir', 'safaqis': 'Sfax',
}


def _key(text):
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode()
    text = re.sub(r'[^a-z0-9 ]+', ' ', text.lower())
    return ' '.join(text.split())


_INDEX = {_key(name): name for name in PLACES}
_INDEX.update({_key(alias): name for alias, name in ALIASES.items()})


def find_place(text):
    """(nom, lat, lng) du lieu reconnu dans le texte, ou None."""
    key = _key(text)
    if not key:
        return None
    if key in _INDEX:
        name = _INDEX[key]
        return (name, *PLACES[name])
    # « Ferme près de Mateur, Bizerte » : le premier lieu cité est le plus précis.
    padded = f' {key} '
    found = [
        (padded.index(f' {candidate} '), -len(candidate), candidate)
        for candidate in _INDEX if f' {candidate} ' in padded
    ]
    if not found:
        return None
    name = _INDEX[min(found)[2]]
    return (name, *PLACES[name])


def in_tunisia(lat, lng):
    if lat is None or lng is None:
        return False
    lat, lng = float(lat), float(lng)
    return BOUNDS['south'] <= lat <= BOUNDS['north'] and BOUNDS['west'] <= lng <= BOUNDS['east']


def farm_point(farm):
    """Position à afficher : coordonnées saisies si elles sont en Tunisie, sinon le lieu tapé."""
    if in_tunisia(farm.latitude, farm.longitude):
        return float(farm.latitude), float(farm.longitude), True
    place = find_place(farm.location)
    if place:
        return place[1], place[2], False
    return None


def places_json():
    return [{'name': name, 'lat': lat, 'lng': lng} for name, (lat, lng) in sorted(PLACES.items())]
