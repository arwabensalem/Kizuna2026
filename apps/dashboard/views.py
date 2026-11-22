from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.accounts.permissions import nav_for, sections_for
from apps.dashboard.briefing import build_briefing


@ensure_csrf_cookie
def home(request):
    return render(request, 'dashboard/home.html')


@login_required
@ensure_csrf_cookie
def dashboard(request):
    # Les liens déjà présents dans le menu ne sont pas répétés plus bas.
    in_menu = {item['url'] for item in nav_for(request.user)}
    sections = [item for item in sections_for(request.user) if item['url'] not in in_menu]
    return render(request, 'dashboard/dashboard.html', {
        'sections': sections,
        'brief': build_briefing(request.user),
    })
