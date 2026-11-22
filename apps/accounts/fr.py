"""Libellés français des formulaires.

Les modèles gardent leurs noms anglais (base de données, API, tests) ;
les formulaires les affichent en français grâce à ces deux tables.
"""

LABELS = {
    'Active': 'Actif',
    'Amount': 'Quantité',
    'Area (m²)': 'Surface (m²)',
    'Availability': 'Disponibilité',
    'Battery (kWh)': 'Batterie (kWh)',
    'Battery charge (%)': 'Charge de la batterie (%)',
    'Building area (m²)': 'Surface du bâtiment (m²)',
    'Business': 'Acheteur',
    'Buyer': 'Acheteur',
    'Capacity (L)': 'Capacité (L)',
    'Capacity (W)': 'Puissance (W)',
    'Category': 'Catégorie',
    'Crop type': 'Culture principale',
    'Description': 'Description',
    'Energy used kwh': 'Énergie utilisée (kWh)',
    'Events per hour': 'Passages par heure',
    'Farm': 'Ferme',
    'Flow (L/h)': 'Débit (L/h)',
    'Harvest date': 'Date de récolte',
    'Harvester': 'Récupérateur',
    'Home': 'Maison',
    'Irrigation type': "Type d'irrigation",
    'Kind': 'Type',
    'Location': 'Lieu',
    'Message to the farmer': "Message à l'agriculteur",
    'Method': 'Méthode',
    'Name': 'Nom',
    'Origin': 'Origine',
    'Period label': 'Période',
    'Power kw': 'Puissance (kW)',
    'Product name': 'Nom du produit',
    'Quantity': 'Quantité',
    'Quantity to request': 'Quantité souhaitée',
    'Recorded on': 'Date',
    'Resource': 'Ressource',
    'Running': 'En marche',
    'Sector note': 'Remarque sur le secteur',
    'Sensor': 'Capteur',
    'Soil type': 'Type de sol',
    'Solar (kW)': 'Solaire (kW)',
    'Solar capacity (W)': 'Puissance solaire (W)',
    'Stage': 'Stade',
    'Storage fill (%)': 'Remplissage du stockage (%)',
    'Tank capacity (L)': 'Capacité du réservoir (L)',
    'Tiles or pads': 'Dalles',
    'Type': 'Type',
    'Unit': 'Unité',
    'Water consumption (L/h)': "Consommation d'eau (L/h)",
    'Water storage (L)': "Stockage d'eau (L)",
    'Water used m3': 'Eau utilisée (m³)',
}

CHOICES = {
    'AC': 'Climatiseur', 'TV': 'Télévision', 'Refrigerator': 'Réfrigérateur',
    'Washing machine': 'Machine à laver', 'Dishwasher': 'Lave-vaisselle',
    'Water heater': 'Chauffe-eau', 'Lights': 'Éclairage', 'Pump': 'Pompe',
    'Bedroom': 'Chambre', 'Bathroom': 'Salle de bain', 'Kitchen': 'Cuisine',
    'Living room': 'Salon', 'Garden': 'Jardin', 'Pool': 'Piscine', 'Garage': 'Garage',
    'Other': 'Autre', 'None': 'Aucune',
    'Available': 'Disponible', 'Limited': 'Limitée', 'Unavailable': 'Indisponible',
    'Barley': 'Orge', 'Citrus': 'Agrumes', 'Olive': 'Olivier', 'Olives': 'Olives',
    'Pepper': 'Piment', 'Tomato': 'Tomate', 'Wheat': 'Blé',
    'Date palm': 'Palmier dattier', 'Almond': 'Amandier', 'Grape': 'Vigne',
    'Potato': 'Pomme de terre', 'Fig': 'Figuier',
    'Fruit': 'Fruits', 'Grain': 'Céréales', 'Herbs': 'Herbes', 'Oil': 'Huile',
    'Vegetables': 'Légumes',
    'Clay': 'Argileux', 'Loam': 'Limoneux-argileux', 'Rocky': 'Rocailleux',
    'Sand': 'Sableux', 'Silt': 'Limoneux',
    'Drip': 'Goutte-à-goutte', 'Furrow': 'Par sillons', 'Sprinkler': 'Aspersion',
    'Seedling': 'Semis', 'Vegetative': 'Croissance', 'Flowering': 'Floraison',
    'Fruiting': 'Fructification', 'Harvest': 'Récolte',
    'Humidity': 'Humidité', 'Rainfall': 'Pluie', 'Soil moisture': 'Humidité du sol (20 cm)',
    'Soil moisture 40 cm': 'Humidité du sol (40 cm)', 'Pump flow meter': 'Débitmètre de la pompe',
    'Weather station': 'Station météo',
    'Solar production': 'Production solaire', 'Tank level': 'Niveau du réservoir',
    'Temperature': 'Température',
    'Energy': 'Énergie', 'Water': 'Eau',
    'Factory': 'Usine', 'Gym': 'Salle de sport', 'Hotel': 'Hôtel',
    'Parking facility': 'Parking', 'Restaurant': 'Restaurant', 'School': 'École',
    'Kinetic floor': 'Sol cinétique', 'Pressure pad': 'Dalle à pression',
    'bunch': 'botte', 'crate': 'caisse', 'litre': 'litre', 'piece': 'pièce',
    'kg': 'kg', '---------': '— Choisir —',
}


def french_form(form):
    for field in form.fields.values():
        label = str(field.label) if field.label is not None else ''
        if label in LABELS:
            field.label = LABELS[label]
        choices = getattr(field, 'choices', None)
        if choices is not None and not hasattr(field, 'queryset'):
            try:
                field.choices = [(value, CHOICES.get(str(text), text)) for value, text in choices]
            except (TypeError, ValueError):
                pass
        elif hasattr(field, 'empty_label') and field.empty_label == '---------':
            field.empty_label = '— Choisir —'
