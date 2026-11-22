import logging

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.forms import (
    KizunaLoginForm,
    KizunaPasswordChangeForm,
    ProfileForm,
    RegisterForm,
)
from apps.accounts.models import User

logger = logging.getLogger(__name__)

# Après l'inscription, chacun arrive sur le premier formulaire de son rôle.
FIRST_STEP = {
    User.Role.CITIZEN: 'homes:create',
    User.Role.FARMER: 'farms:create',
    User.Role.BUSINESS: 'market:board',
}


class KizunaLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True
    form_class = KizunaLoginForm


class KizunaLogoutView(LogoutView):
    pass


def register(request):
    """Inscription : le compte est actif tout de suite, sans e-mail ni SMS à confirmer."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='apps.accounts.backends.UsernameOrPhoneBackend')
        messages.success(request, f'Bienvenue {user.first_name or user.username} ! Votre compte est prêt.')
        if user.role in FIRST_STEP:
            messages.info(request, 'Première étape : décrivez votre lieu. Cela prend environ 5 minutes.')
            return redirect(FIRST_STEP[user.role])
        return redirect('dashboard')
    return render(request, 'accounts/registration.html', {'form': form})


@login_required
def profile(request):
    editing_profile = request.method == 'POST' and request.POST.get('action') == 'profile'
    editing_password = request.method == 'POST' and request.POST.get('action') == 'password'
    profile_form = ProfileForm(
        request.POST if editing_profile else None,
        instance=request.user,
    )
    password_form = KizunaPasswordChangeForm(
        request.user,
        request.POST if editing_password else None,
    )
    if editing_profile and profile_form.is_valid():
        profile_form.save()
        messages.success(request, 'Vos informations sont enregistrées.')
        return redirect('accounts:profile')
    if editing_password and password_form.is_valid():
        user = password_form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Votre mot de passe a été changé.')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })


def csrf_failure(request, reason=''):
    """Jeton de sécurité périmé (autre onglet, retour arrière, changement de compte).

    Pour la déconnexion, on déconnecte quand même : il n'y a rien à protéger.
    Ailleurs, on explique simplement qu'il faut recharger la page.
    """
    if request.path == reverse('accounts:logout'):
        logout(request)
        messages.info(request, 'Vous êtes déconnecté.')
        return redirect('home')
    back = request.META.get('HTTP_REFERER', '')
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        back = ''
    return render(request, 'accounts/csrf_failure.html', {'back': back or request.path}, status=403)
