"""Places on the Tunisia map.

Governorate names match the boundary file. City coordinates are the
approximate centre of the city. Neighbourhoods are demo anchors at that
centre, except Lafayette, which holds the shared simulation clock.

The profiles are a fixed demo spread. They are not statistics.
"""

FEATURED = 'Tunis'
FEATURED_NEIGHBOURHOOD = 'Lafayette'

# water, energy, agriculture, climate. Demo starting points before the scenario.
PROFILES = {
    'coast_north': {'water': 68, 'energy': 64, 'agriculture': 42, 'climate': 58},
    'coast_central': {'water': 58, 'energy': 60, 'agriculture': 55, 'climate': 52},
    'interior': {'water': 46, 'energy': 52, 'agriculture': 62, 'climate': 48},
    'south': {'water': 34, 'energy': 70, 'agriculture': 38, 'climate': 40},
}

# lat, lng of the city centre.
GOVERNORATES = {
    'Tunis': ('coast_north', 'Tunis', 36.8065, 10.1815, 'Lafayette'),
    'Ariana': ('coast_north', 'Ariana', 36.8625, 10.1956, 'Ariana centre'),
    'Ben Arous': ('coast_north', 'Ben Arous', 36.7531, 10.2189, 'Ben Arous centre'),
    'Manouba': ('coast_north', 'Manouba', 36.8080, 10.0972, 'Manouba centre'),
    'Nabeul': ('coast_north', 'Nabeul', 36.4561, 10.7376, 'Nabeul centre'),
    'Bizerte': ('coast_north', 'Bizerte', 37.2744, 9.8739, 'Bizerte centre'),
    'Sousse': ('coast_central', 'Sousse', 35.8256, 10.6369, 'Sousse centre'),
    'Monastir': ('coast_central', 'Monastir', 35.7643, 10.8113, 'Monastir centre'),
    'Mahdia': ('coast_central', 'Mahdia', 35.5047, 11.0622, 'Mahdia centre'),
    'Sfax': ('coast_central', 'Sfax', 34.7406, 10.7603, 'Sfax centre'),
    'Béja': ('interior', 'Béja', 36.7256, 9.1817, 'Béja centre'),
    'Jendouba': ('interior', 'Jendouba', 36.5011, 8.7802, 'Jendouba centre'),
    'El Kef': ('interior', 'El Kef', 36.1742, 8.7049, 'El Kef centre'),
    'Siliana': ('interior', 'Siliana', 36.0849, 9.3708, 'Siliana centre'),
    'Zaghouan': ('interior', 'Zaghouan', 36.4029, 10.1429, 'Zaghouan centre'),
    'Kairouan': ('interior', 'Kairouan', 35.6781, 10.0963, 'Kairouan centre'),
    'Kasserine': ('interior', 'Kasserine', 35.1676, 8.8365, 'Kasserine centre'),
    'Sidi Bouzid': ('interior', 'Sidi Bouzid', 35.0382, 9.4849, 'Sidi Bouzid centre'),
    'Gabès': ('south', 'Gabès', 33.8815, 10.0982, 'Gabès centre'),
    'Médenine': ('south', 'Médenine', 33.3549, 10.5055, 'Médenine centre'),
    'Tataouine': ('south', 'Tataouine', 32.9297, 10.4518, 'Tataouine centre'),
    'Gafsa': ('south', 'Gafsa', 34.4250, 8.7842, 'Gafsa centre'),
    'Tozeur': ('south', 'Tozeur', 33.9197, 8.1335, 'Tozeur centre'),
    'Kébili': ('south', 'Kébili', 33.7044, 8.9690, 'Kébili centre'),
}

COUNTRY = {'name': 'Tunisia', 'lat': 34.05, 'lng': 9.45, 'zoom': 6.6}
ZOOMS = {'governorate': 8.6, 'city': 11.5, 'neighborhood': 14.2, 'node': 16.4}

PILLARS = ('water', 'energy', 'agriculture', 'climate')
