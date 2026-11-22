# KIZUNA · Guide de démonstration pour le jury

KIZUNA relie l'eau, l'énergie et l'agriculture en Tunisie. Ce guide donne de quoi lancer le site, les comptes de démonstration et un parcours de 10 à 12 minutes.

> Les comptes ci-dessous sont des comptes **de démonstration**, avec des données fictives. Ne réutilisez pas ces mots de passe en production.

---

## 1. Lancer le site

Dans le dossier du projet (`kizuna`), avec votre environnement Python activé :

```bash
pip install -r requirements.txt      # première fois seulement
python manage.py migrate             # crée ou met à jour la base
python manage.py seed_demo           # remplit la base avec toutes les données de démo
python manage.py runserver           # démarre le site
```

Ouvrez ensuite **http://127.0.0.1:8000/**. Si vous lancez `runserver 8001`, remplacez 8000 par 8001 dans tous les liens.

`seed_demo` ne supprime rien. Vous pouvez la relancer avant la présentation : elle complète ce qui manque et remet les mots de passe de démonstration à leur valeur.

L'inscription ne demande **aucune confirmation**, ni par e-mail ni par SMS : un nouveau compte est actif tout de suite.

---

## 2. Comptes et mots de passe

### Administrateur

| Rôle | Identifiant | Mot de passe | Où aller |
|---|---|---|---|
| Administrateur (tout voir, gérer les utilisateurs) | `kizuna.admin` | `Kizuna-admin-2026` | http://127.0.0.1:8000/accounts/users/ et http://127.0.0.1:8000/admin/ |

### Tous les autres comptes, avec le mot de passe `Kizuna-demo-2026`

**Citoyens** (connexion avec le nom d'utilisateur)

| Identifiant | Personne | Maison |
|---|---|---|
| `amira` | Amira Ben Youssef | Appartement El Menzah, Tunis : 5 pièces, climatiseur réglé trop bas, frigo trop gourmand |
| `karim` | Karim Mejri | Villa Sahloul, Sousse : panneaux solaires, piscine, jardin, pilote automatique |
| `leila` | Leïla Haddad | Dar Leïla, maison à patio, médina de Kairouan, avec solaire |

**Agriculteurs** (connexion avec le **numéro de téléphone** ou le nom d'utilisateur)

| Téléphone | Identifiant | Ferme | Cultures |
|---|---|---|---|
| `+216 98 100 201` | `zitouna.sfax` | Oliveraie Zitouna, Sfax | Oliviers Chemlali, amandiers |
| `+216 98 100 202` | `oasis.tozeur` | Palmeraie de Tozeur | Palmiers Deglet Nour, grenadiers |
| `+216 98 100 203` | `capbon.harissa` | Jardins du Cap Bon, Nabeul | Piments Baklouti, orangers Maltaise, tomates |
| `+216 98 100 204` | `kairouan.herbes` | Domaine Gharbi, Kairouan | Blé dur, orge, romarin et thym |
| `+216 98 100 205` | `nizar.mateur` | Ferme Ichkeul, Mateur (Bizerte) | Tomates, blé tendre, pommes de terre |

**Acheteurs étrangers** (marché export direct, comptes créés par l'administrateur)

| Identifiant | Acheteur | Pays | Offre en cours |
|---|---|---|---|
| `tokyo.buyer` | Yuki Tanaka | Japon | Huile d'olive (contre-offre), dattes (acceptée) |
| `london.trade` | Emma Clarke | Royaume-Uni | Dattes Deglet Nour (acceptée) |
| `hamburg.feinkost` | Jonas Becker | Allemagne | Huile d'olive et tomates séchées (en attente) |
| `marseille.epicerie` | Claire Martin | France | Piment pour harissa (en attente) |
| `montreal.epicerie` | Sophie Tremblay | Canada | Herbes sauvages (contre-offre) |

---

## 3. Liens utiles

| Page | Lien |
|---|---|
| Accueil | http://127.0.0.1:8000/ |
| Connexion | http://127.0.0.1:8000/accounts/login/ |
| Inscription | http://127.0.0.1:8000/accounts/register/ |
| Tableau de bord | http://127.0.0.1:8000/dashboard/ |
| Ma maison | http://127.0.0.1:8000/homes/ |
| Maison 3D (jumeau vivant) | http://127.0.0.1:8000/twin/ |
| Factures STEG et SONEDE | http://127.0.0.1:8000/homes/factures/ |
| Météo | http://127.0.0.1:8000/weather/ |
| Pilote automatique | http://127.0.0.1:8000/autopilot/ |
| Ma ferme | http://127.0.0.1:8000/farms/ |
| Quand arroser, combien, quand récolter | http://127.0.0.1:8000/farms/conseils/ |
| Marché export direct | http://127.0.0.1:8000/market/ |
| Offres et négociations | http://127.0.0.1:8000/market/offers/ |
| Chat traduit avec un acheteur | http://127.0.0.1:8000/market/negotiation/ |
| Prix juste | http://127.0.0.1:8000/market/fair-price/ |
| Démonstration (sans compte) | http://127.0.0.1:8000/demo/ |
| Gestion des utilisateurs (admin) | http://127.0.0.1:8000/accounts/users/ |
| Administration Django | http://127.0.0.1:8000/admin/ |
| Carte de la Tunisie (admin) | http://127.0.0.1:8000/tunisia/ |
| Labo de crise, journée de crise (admin) | http://127.0.0.1:8000/crisis/ et http://127.0.0.1:8000/crisis/day/ |
| Réseau de ressources, ligue (admin) | http://127.0.0.1:8000/network/ et http://127.0.0.1:8000/league/ |

---

## 4. Scénario pour le jury (10 à 12 minutes)

### Acte 1 · Le citoyen : « ma maison en un coup d'œil » (4 min)

1. Ouvrez l'**accueil**, puis **Se connecter** avec `amira` / `Kizuna-demo-2026`.
2. **Tableau de bord** : eau, énergie, production solaire et score de résilience de la maison.
3. **Ma maison** › *Appartement El Menzah* :
   - les pièces et les appareils de l'appartement ;
   - **Alertes et conseils** : le climatiseur du salon est réglé à 18 °C (passer à 26 °C fait économiser environ la moitié de l'électricité), et le vieux frigo consomme 420 W au lieu d'environ 150 W ;
   - **Mes prochaines factures** : estimation STEG et SONEDE, avec l'alerte avant de passer à une tranche plus chère.
4. **Maison 3D** : chaque pièce prend une couleur selon sa consommation, du vert au rouge, avec le coût en dinars. Le solaire apparaît en jaune sur le toit.
5. Bouton **Détecter une fuite** : simulez une fuite nocturne. KIZUNA la repère et, en mode Smart ou Autopilot, ferme la vanne.
6. *Option* : déconnectez-vous et connectez-vous avec `karim`. Sa villa a des panneaux solaires. En journée, le conseil **« Vos panneaux produisent : lancez le lave-vaisselle maintenant »** apparaît sur sa maison. Montrez aussi le **pilote automatique**.

### Acte 2 · L'agriculteur : « quand arroser, combien, quand récolter » (3 min)

1. Connectez-vous avec le **numéro de téléphone** `+216 98 100 205` / `Kizuna-demo-2026`. Il n'y a pas d'e-mail : c'est voulu pour les agriculteurs.
2. **Ma ferme** › *Ferme Ichkeul* :
   - la carte de la Tunisie montre la position exacte de la ferme, près du lac Ichkeul ;
   - trois cultures, chacune avec sa surface exacte ;
   - les capteurs : sol à 20 cm et 40 cm, débitmètre sur la pompe, station météo partagée avec les voisins.
3. **Quand arroser ?** : le conseil du jour (arroser ou non, combien de mètres cubes) et la date et le prix de récolte conseillés.
4. *Option* : montrez l'inscription d'un nouvel agriculteur, actif tout de suite. Tapez un lieu, par exemple « Mateur » : la carte se place directement à la bonne position.

### Acte 3 · Le marché export direct (3 min)

1. Connectez-vous avec `zitouna.sfax` (ou `+216 98 100 201`).
2. **Vendre et échanger** : l'annonce « Huile d'olive extra vierge Chemlali », avec son passeport de lot. Les données de la ferme (irrigation, sol, capteurs) servent de **preuve de qualité**.
3. **Offres** : la négociation avec Yuki Tanaka (Tokyo), en japonais et en anglais, avec la contre-offre de l'agriculteur.
4. **Chat traduit avec un acheteur** : choisissez un acheteur (japonais, anglais, allemand), écrivez en derja ou en français. Le message est traduit pour l'acheteur, et sa réponse est traduite pour l'agriculteur. *La traduction automatique a besoin d'Internet et de la clé IA dans `.env`.*
5. *Côté acheteur* : connectez-vous avec `london.trade` ou `tokyo.buyer` et ouvrez **Offres** pour voir la même négociation depuis l'autre côté.

### Acte 4 · L'administrateur (1 à 2 min)

1. Connectez-vous avec `kizuna.admin` / `Kizuna-admin-2026`.
2. **Utilisateurs** : l'administrateur voit tous les comptes par rôle (citoyens, agriculteurs et acheteurs étrangers). C'est lui qui ajoute les acheteurs, en ajoute, suspend un compte ou remet un mot de passe provisoire.
3. Pour finir : **Tunisie** (carte nationale), **Journée de crise** (une crise d'eau et de chaleur qui se propage), puis **Démonstration**.

---

## 5. En cas de souci le jour J

- **« no such column » ou page d'erreur après une mise à jour** : lancez `python manage.py migrate`, puis `python manage.py seed_demo`.
- **Mot de passe refusé** : relancez `python manage.py seed_demo`, qui remet tous les mots de passe de démo.
- **La carte reste grise** : il faut Internet pour les fonds Esri. Le contour des gouvernorats reste visible même hors ligne.
- **La traduction ne répond pas** : vérifiez la connexion Internet et la clé IA dans `.env`. Le reste de la démo marche sans Internet.
- **Mise en page ancienne** : faites Ctrl+F5 pour recharger les styles.
