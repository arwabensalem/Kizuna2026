from apps.accounts.permissions import nav_for, sees_business, sees_farm, user_is_admin


def platform(request):
    user = request.user
    return {
        'kizuna_nav': nav_for(user),
        'sees_farm': sees_farm(user),
        'sees_business': sees_business(user),
        'sees_platform': user_is_admin(user),
    }
