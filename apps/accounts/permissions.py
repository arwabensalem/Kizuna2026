from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.accounts.models import User


def user_is_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.role == User.Role.ADMIN
    )


def role_allows(user, roles):
    if not user.is_authenticated:
        return False
    if user_is_admin(user):
        return True
    return user.role in roles


def role_required(*roles):
    """Block a function view unless the user has one of these roles.

    Admin and superuser accounts pass every check.
    """

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not role_allows(request.user, roles):
                raise PermissionDenied('Your role cannot open this page.')
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


class RoleRequiredMixin(LoginRequiredMixin):
    """Block a class view unless the user has one of allowed_roles."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not role_allows(request.user, self.allowed_roles):
            raise PermissionDenied('Your role cannot open this page.')
        return super().dispatch(request, *args, **kwargs)


SECTION_CATALOG = (
    {
        'roles': (User.Role.CITIZEN,),
        'label': 'Mes maisons',
        'text': 'Les logements dont vous vous occupez.',
        'url_name': 'homes:list',
    },
    {
        'roles': (User.Role.CITIZEN,),
        'label': 'Appareils',
        'text': 'Les appareils de la maison.',
        'url_name': 'homes:appliances',
    },
    {
        'roles': (User.Role.CITIZEN,),
        'label': 'Capteurs',
        'text': 'Les compteurs installés dans la maison.',
        'url_name': 'sensors:home',
    },
    {
        'roles': (User.Role.CITIZEN,),
        'label': 'Passeport des ressources',
        'text': "L'eau et l'énergie utilisées par la maison.",
        'url_name': 'resources:passports',
    },
    {
        'roles': (User.Role.FARMER,),
        'label': 'Mes fermes',
        'text': 'Les terres que vous exploitez.',
        'url_name': 'farms:list',
    },
    {
        'roles': (User.Role.FARMER,),
        'label': 'Cultures',
        'text': 'Ce qui pousse sur chaque ferme.',
        'url_name': 'farms:crops',
    },
    {
        'roles': (User.Role.FARMER,),
        'label': 'Irrigation',
        'text': "Le matériel d'arrosage de la ferme.",
        'url_name': 'farms:irrigation',
    },
    {
        'roles': (User.Role.FARMER,),
        'label': 'Capteurs de la ferme',
        'text': 'Sol, météo, réservoir et solaire.',
        'url_name': 'farms:sensors',
    },
    {
        'roles': (User.Role.FARMER,),
        'label': 'Réservoirs',
        'text': "L'eau stockée sur la ferme.",
        'url_name': 'farms:tanks',
    },
    {
        'roles': (User.Role.FARMER,),
        'label': 'Panneaux solaires',
        'text': 'Les panneaux qui alimentent la ferme.',
        'url_name': 'farms:solar',
    },
)


def sections_for(user):
    sections = []
    for item in SECTION_CATALOG:
        if role_allows(user, item['roles']):
            sections.append({
                'label': item['label'],
                'text': item['text'],
                'url': reverse(item['url_name']),
            })
    return sections


def _link(label, url_name, key, icon='', primary=False):
    return {
        'label': label, 'url': reverse(url_name), 'key': key,
        'icon': icon, 'primary': primary,
    }


# Each role opens only its own world. Admin keeps the shared platform.
# The last value says whether the link sits in the main bar (True) or under
# the "Plus" menu (False), so the bar stays short and easy to read.
_ROLE_LINKS = {
    User.Role.CITIZEN: (
        ('Tableau de bord', 'dashboard', 'dashboard', 'chart', True),
        ('Ma maison', 'homes:list', 'homes', 'door', True),
        ('Maison 3D', 'twin:board', 'twin', 'cube', True),
        ('Factures et conseils', 'homes:bills', 'bills', 'bell', True),
        ('Météo', 'weather:board', 'weather', 'sun', False),
        ('Pilote automatique', 'actuators:board', 'autopilot', 'cpu', False),
        ('Passeport ressources', 'resources:passports', 'passport', 'book', False),
        ('Réglages', 'accounts:profile', 'profile', 'settings', False),
    ),
    User.Role.FARMER: (
        ('Tableau de bord', 'dashboard', 'dashboard', 'chart', True),
        ('Ma ferme', 'farms:list', 'farms', 'sprout', True),
        ('Quand arroser ?', 'farms:advice_first', 'advice', 'drop', True),
        ('Vendre et échanger', 'market:board', 'market', 'exchange', True),
        ('Chat traduit avec un acheteur', 'market:negotiation', 'negotiation', 'exchange', False),
        ('Pilote automatique', 'actuators:board', 'autopilot', 'cpu', False),
        ('Réglages', 'accounts:profile', 'profile', 'settings', False),
    ),
    User.Role.BUSINESS: (
        ('Tableau de bord', 'dashboard', 'dashboard', 'chart', True),
        ('Acheter en direct', 'market:board', 'market', 'exchange', True),
        ('Chat traduit avec un agriculteur', 'market:negotiation', 'negotiation', 'exchange', False),
        ('Réglages', 'accounts:profile', 'profile', 'settings', False),
    ),
}

_PLATFORM_LINKS = (
    ('Utilisateurs', 'accounts:users', 'users', 'user-plus'),
    ('Et si… ?', 'ai:board', 'ai', 'bulb'),
    ('Labo de crise', 'crisis:lab', 'crisis', 'flask'),
    ('Journée de crise', 'crisis:day', 'crisis-day', 'alert'),
    ('Réseau de ressources', 'network:board', 'network', 'network'),
    ('Ligue de résilience', 'league:board', 'league', 'trophy'),
    ('Tunisie', 'tunisia:map', 'tunisia', 'map'),
    ('Simulation', 'simulation:board', 'simulation', 'sliders'),
    ('Cerveau', 'brain:board', 'brain', 'spark'),
)

_DEMO = ('Démonstration', 'demo', 'demo', 'play', False)


def nav_for(user):
    """Links this person should see. Other roles and other accounts stay out."""
    if not getattr(user, 'is_authenticated', False):
        return []
    if user_is_admin(user):
        seen = set()
        links = []
        for role_links in _ROLE_LINKS.values():
            for label, url_name, key, icon, primary in role_links:
                if key in seen or key == 'profile':
                    continue
                seen.add(key)
                links.append(_link(label, url_name, key, icon, key == 'dashboard'))
        links.append(_link(*_DEMO))
        for label, url_name, key, icon in _PLATFORM_LINKS:
            links.append(_link(label, url_name, key, icon))
        links.append(_link('Réglages', 'accounts:profile', 'profile', 'settings'))
        return links
    role_links = _ROLE_LINKS.get(user.role, _ROLE_LINKS[User.Role.CITIZEN])
    return [*(_link(*item) for item in role_links), _link(*_DEMO)]


def sees_farm(user):
    return user_is_admin(user) or getattr(user, 'role', None) == User.Role.FARMER


def sees_business(user):
    return user_is_admin(user) or getattr(user, 'role', None) == User.Role.BUSINESS
