"""Gestion des utilisateurs par l'administrateur, depuis le site (sans passer par /admin/).

L'administrateur crée les comptes des agriculteurs (vendeurs) et des acheteurs,
change un rôle, active ou suspend un compte, et réinitialise un mot de passe.
On suspend au lieu de supprimer : les offres et les conversations restent lisibles.
"""

import secrets

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.forms import normalize_phone, style_form
from apps.accounts.models import User
from apps.accounts.permissions import user_is_admin

ROLE_LABELS = {
    User.Role.FARMER: 'Agriculteur (vendeur)',
    User.Role.BUSINESS: 'Acheteur (étranger)',
    User.Role.CITIZEN: 'Citoyen',
    User.Role.ADMIN: 'Administrateur',
}
ROLE_CHOICES = tuple(ROLE_LABELS.items())


def _admin_only(request):
    if not request.user.is_authenticated:
        return False
    if not user_is_admin(request.user):
        raise PermissionDenied('Seul un administrateur gère les utilisateurs.')
    return True


def temporary_password():
    """Mot de passe provisoire lisible, à transmettre à la personne (elle le change ensuite)."""
    return f'Kz-{secrets.token_urlsafe(6)}-{secrets.randbelow(90) + 10}'


class ManagedUserForm(forms.ModelForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, label='Rôle')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'role', 'email', 'phone', 'is_active')
        labels = {
            'username': "Nom d'utilisateur",
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'email': 'Adresse e-mail',
            'phone': 'Téléphone',
            'is_active': 'Compte actif (peut se connecter)',
        }

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        style_form(self)
        self.fields['phone'].help_text = (
            'Obligatoire pour un agriculteur (8 chiffres tunisiens). Format international accepté pour un acheteur.'
        )
        self.fields['email'].help_text = 'Obligatoire pour un acheteur.'

    def clean_phone(self):
        return (self.cleaned_data.get('phone') or '').strip()

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        phone = cleaned.get('phone') or ''
        email = (cleaned.get('email') or '').strip()
        others = User.objects.exclude(pk=self.instance.pk)
        if role == User.Role.FARMER:
            normalized = normalize_phone(phone)
            if not phone:
                self.add_error('phone', "Entrez le numéro de l'agriculteur.")
            elif not normalized:
                self.add_error('phone', 'Numéro invalide : 8 chiffres, par exemple 98 123 456.')
            else:
                cleaned['phone'] = normalized
        elif phone:
            cleaned['phone'] = normalize_phone(phone) or ' '.join(phone.split())
        if role == User.Role.BUSINESS and not email:
            self.add_error('email', "Entrez l'adresse e-mail de l'acheteur.")
        if cleaned.get('phone') and others.filter(phone=cleaned['phone']).exists():
            self.add_error('phone', 'Un autre compte utilise déjà ce numéro.')
        if email and others.filter(email__iexact=email).exists():
            self.add_error('email', 'Un autre compte utilise déjà cette adresse.')
        if self.editor is not None and self.instance.pk == self.editor.pk:
            if role != User.Role.ADMIN:
                self.add_error('role', 'Vous ne pouvez pas retirer votre propre rôle administrateur.')
            if not cleaned.get('is_active'):
                self.add_error('is_active', 'Vous ne pouvez pas suspendre votre propre compte.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data['role']
        user.phone = self.cleaned_data.get('phone', '')
        if commit:
            user.save()
        return user


def users_list(request):
    if not _admin_only(request):
        return redirect('accounts:login')
    role = request.GET.get('role', '')
    query = (request.GET.get('q') or '').strip()
    users = User.objects.order_by('-date_joined')
    if role in ROLE_LABELS:
        users = users.filter(role=role)
    if query:
        users = users.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)
            | Q(email__icontains=query) | Q(phone__icontains=query)
        )
    counts = dict(User.objects.values_list('role').annotate(n=Count('id')))
    tabs = [{'code': '', 'label': 'Tous', 'count': sum(counts.values())}] + [
        {'code': code, 'label': label, 'count': counts.get(code, 0)} for code, label in ROLE_CHOICES
    ]
    rows = [{'user': u, 'role_label': ROLE_LABELS.get(u.role, u.role)} for u in users[:300]]
    return render(request, 'accounts/users_list.html', {
        'rows': rows, 'tabs': tabs, 'role': role, 'q': query,
        'inactive': User.objects.filter(is_active=False).count(),
    })


def user_create(request):
    if not _admin_only(request):
        return redirect('accounts:login')
    initial = {'role': request.GET.get('role') if request.GET.get('role') in ROLE_LABELS else User.Role.FARMER,
               'is_active': True}
    form = ManagedUserForm(request.POST or None, initial=initial, editor=request.user)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        password = temporary_password()
        user.set_password(password)
        user.email_verified = True  # créé et vérifié par l'administrateur
        user.save()
        messages.success(
            request,
            f'Compte « {user.username} » créé ({ROLE_LABELS[user.role]}). '
            f'Mot de passe provisoire : {password} — transmettez-le à la personne, il ne sera plus affiché.',
        )
        return redirect('accounts:users')
    return render(request, 'accounts/user_form.html', {'form': form, 'creating': True})


def user_edit(request, pk):
    if not _admin_only(request):
        return redirect('accounts:login')
    target = get_object_or_404(User, pk=pk)
    form = ManagedUserForm(request.POST or None, instance=target, initial={'role': target.role}, editor=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Compte « {target.username} » mis à jour.')
        return redirect('accounts:users')
    return render(request, 'accounts/user_form.html', {
        'form': form, 'creating': False, 'target': target, 'is_self': target.pk == request.user.pk,
    })


@require_POST
def user_toggle(request, pk):
    if not _admin_only(request):
        return redirect('accounts:login')
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, 'Vous ne pouvez pas suspendre votre propre compte.')
    else:
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        messages.success(
            request, f'Compte « {target.username} » {"réactivé" if target.is_active else "suspendu"}.',
        )
    return redirect('accounts:users')


@require_POST
def user_reset_password(request, pk):
    if not _admin_only(request):
        return redirect('accounts:login')
    target = get_object_or_404(User, pk=pk)
    password = temporary_password()
    target.set_password(password)
    target.save(update_fields=['password'])
    messages.success(
        request,
        f'Nouveau mot de passe provisoire pour « {target.username} » : {password} — il ne sera plus affiché.',
    )
    return redirect('accounts:user_edit', pk=target.pk)
