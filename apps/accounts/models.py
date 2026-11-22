from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class KizunaUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', self.model.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """Person using KIZUNA. A person has one role.

    Passwords are stored with Django's password hashers. Call
    create_user or set_password. Never assign a raw password to the field.
    """

    class Role(models.TextChoices):
        CITIZEN = 'citizen', 'Citizen'
        FARMER = 'farmer', 'Farmer'
        # Acheteurs (souvent étrangers), ajoutés par l'administrateur. La valeur
        # « business » est gardée pour ne pas toucher aux comptes existants.
        BUSINESS = 'business', 'Buyer'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CITIZEN)
    # Conservé pour l'historique : plus aucune confirmation n'est demandée.
    email_verified = models.BooleanField('e-mail confirmé', default=True)
    # Les agriculteurs se connectent avec leur numéro de téléphone (format +216XXXXXXXX).
    phone = models.CharField('téléphone', max_length=20, blank=True, db_index=True)

    objects = KizunaUserManager()

    def __str__(self):
        return self.username
