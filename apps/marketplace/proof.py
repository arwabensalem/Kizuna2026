"""Les données de la ferme deviennent la preuve de qualité vue par l'acheteur étranger.

Un importateur (Tokyo, Gdańsk, Montréal…) voit comment la culture a été irriguée,
quels capteurs suivent la parcelle et quelle énergie fait tourner la pompe.
Lecture seule des modèles de la ferme ; rien n'est inventé : sans donnée, la ligne
n'apparaît pas.
"""

from decimal import Decimal

from django.db.models import Sum

LABELS = {
    'fr': {
        'title': 'Preuves de la ferme (données des capteurs)',
        'intro': "Ces chiffres viennent du jumeau numérique de la ferme, pas d'une déclaration.",
        'irrigation': 'Irrigation',
        'water': 'Eau apportée (relevés)',
        'per_ha': 'par hectare',
        'systems': 'Systèmes actifs',
        'sensors': 'Capteurs sur la parcelle',
        'solar': 'Pompage solaire',
        'soil': 'Sol',
        'crops': 'Cultures suivies',
        'none': 'La ferme n’a pas encore partagé de données de capteurs.',
        'drip': 'Goutte-à-goutte (économe en eau)',
        'sprinkler': 'Aspersion',
        'furrow': 'Par sillons',
        'no_irrigation': 'Pluvial, sans irrigation (culture en sec)',
        'sensor_soil_moisture': 'humidité du sol',
        'sensor_temperature': 'température',
        'sensor_humidity': 'humidité de l’air',
        'sensor_rainfall': 'pluviomètre',
        'sensor_tank_level': 'niveau du réservoir',
        'sensor_solar_production': 'production solaire',
    },
    'en': {
        'title': 'Farm evidence (sensor data)',
        'intro': "These figures come from the farm's digital twin, not from a claim.",
        'irrigation': 'Irrigation',
        'water': 'Water applied (records)',
        'per_ha': 'per hectare',
        'systems': 'Active systems',
        'sensors': 'Sensors on the plot',
        'solar': 'Solar pumping',
        'soil': 'Soil',
        'crops': 'Crops tracked',
        'none': 'The farm has not shared sensor data yet.',
        'drip': 'Drip (water-saving)',
        'sprinkler': 'Sprinkler',
        'furrow': 'Furrow',
        'no_irrigation': 'Rain-fed, no irrigation (dry farming)',
        'sensor_soil_moisture': 'soil moisture',
        'sensor_temperature': 'temperature',
        'sensor_humidity': 'air humidity',
        'sensor_rainfall': 'rain gauge',
        'sensor_tank_level': 'tank level',
        'sensor_solar_production': 'solar output',
    },
    'ja': {
        'title': '農園の証拠（センサーデータ）',
        'intro': 'これらの数値は自己申告ではなく、農園のデジタルツインから取得したものです。',
        'irrigation': '灌漑',
        'water': '散水量（記録）',
        'per_ha': '1ヘクタールあたり',
        'systems': '稼働中の設備',
        'sensors': '圃場のセンサー',
        'solar': '太陽光ポンプ',
        'soil': '土壌',
        'crops': '管理中の作物',
        'none': 'この農園はまだセンサーデータを公開していません。',
        'drip': '点滴灌漑（節水型）',
        'sprinkler': 'スプリンクラー',
        'furrow': '畝間灌漑',
        'no_irrigation': '天水栽培（無灌漑）',
        'sensor_soil_moisture': '土壌水分',
        'sensor_temperature': '気温',
        'sensor_humidity': '湿度',
        'sensor_rainfall': '雨量計',
        'sensor_tank_level': 'タンク水位',
        'sensor_solar_production': '太陽光発電量',
    },
}

SOILS = {
    'sand': {'fr': 'Sableux', 'en': 'Sandy', 'ja': '砂質'},
    'loam': {'fr': 'Limoneux-argileux', 'en': 'Loam', 'ja': 'ローム'},
    'silt': {'fr': 'Limoneux', 'en': 'Silt', 'ja': 'シルト'},
    'clay': {'fr': 'Argileux', 'en': 'Clay', 'ja': '粘土質'},
    'rocky': {'fr': 'Rocailleux', 'en': 'Rocky', 'ja': '礫質'},
}


def farm_proof(farm, lang='fr'):
    """Lignes (libellé, valeur) prouvant comment la culture a été conduite. Liste vide si aucune donnée."""
    if farm is None:
        return []
    words = LABELS.get(lang, LABELS['fr'])
    rows = []
    method = farm.irrigation_type
    rows.append((words['irrigation'], words['no_irrigation'] if method == 'none' else words.get(method, method)))
    total = farm.irrigation_events.aggregate(total=Sum('water_m3'))['total']
    if total:
        text = f'{total:,.0f} m³'.replace(',', ' ')
        hectares = Decimal(farm.area_m2) / Decimal(10000) if farm.area_m2 else None
        if hectares:
            text += f' · {total / hectares:,.0f} m³ {words["per_ha"]}'.replace(',', ' ')
        rows.append((words['water'], text))
    systems = [s for s in farm.irrigation_systems.all() if s.is_active]
    if systems:
        rows.append((words['systems'], ', '.join(
            f'{s.name} ({s.flow_liters_per_hour:.0f} L/h)' for s in systems
        )))
    sensors = sorted({s.kind for s in farm.farm_sensors.all() if s.is_active})
    if sensors:
        rows.append((words['sensors'], ', '.join(words.get('sensor_' + k, k) for k in sensors)))
    solar = sum(unit.capacity_watts for unit in farm.solar_units.all()) or farm.solar_capacity_watts
    if solar:
        rows.append((words['solar'], f'{solar / 1000:.1f} kW'))
    rows.append((words['soil'], SOILS.get(farm.soil_type, {}).get(lang, farm.soil_type)))
    crops = list(farm.crops.all()[:4])
    if crops:
        rows.append((words['crops'], ', '.join(c.name for c in crops)))
    return rows


def proof_labels(lang='fr'):
    return LABELS.get(lang, LABELS['fr'])
