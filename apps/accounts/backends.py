"""Connexion avec le nom d'utilisateur ou le numéro de téléphone."""

from django.contrib.auth.backends import ModelBackend

from apps.accounts.models import User


class UsernameOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None or not username:
            return user
        from apps.accounts.forms import normalize_phone

        phone = normalize_phone(username)
        if not phone:
            return None
        candidate = User.objects.filter(phone=phone).first()
        if candidate and candidate.check_password(password) and self.user_can_authenticate(candidate):
            return candidate
        return None
