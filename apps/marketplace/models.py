"""Agricultural marketplace.

Farmers list a harvest. Buyers search those listings and send a request.
This module does not read the crisis lab or the resource-network clock.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    class Category(models.TextChoices):
        OLIVE = 'olive', 'Olives'
        OIL = 'oil', 'Oil'
        VEGETABLE = 'vegetable', 'Vegetables'
        FRUIT = 'fruit', 'Fruit'
        GRAIN = 'grain', 'Grain'
        HERB = 'herb', 'Herbs'
        OTHER = 'other', 'Other'

    class Unit(models.TextChoices):
        KG = 'kg', 'kg'
        LITRE = 'litre', 'litre'
        CRATE = 'crate', 'crate'
        BUNCH = 'bunch', 'bunch'
        PIECE = 'piece', 'piece'

    class Availability(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        LIMITED = 'limited', 'Limited'
        UNAVAILABLE = 'unavailable', 'Unavailable'

    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='products',
    )
    name = models.CharField('Product name', max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    unit = models.CharField(max_length=20, choices=Unit.choices)
    origin = models.CharField(max_length=160)
    harvest_date = models.DateField('Harvest date')
    availability = models.CharField(
        max_length=20,
        choices=Availability.choices,
        default=Availability.AVAILABLE,
    )
    description = models.TextField(blank=True)
    # Bourse directe : prix juste fixé par l'agriculteur, traçabilité, export.
    price_tnd = models.DecimalField(
        'Farm-gate price (TND per unit)',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
    )
    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
    )
    certifications = models.CharField(max_length=120, blank=True)
    export_ready = models.BooleanField(default=False)
    min_order = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'name']

    def __str__(self):
        return self.name

    @property
    def lot_code(self):
        return f'KZ-TN-{self.category[:3].upper()}-{self.pk or 0:05d}'

    @property
    def certification_codes(self):
        return [code for code in self.certifications.split(',') if code]


class BuyerRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        COUNTERED = 'countered', 'Contre-offre'
        ACCEPTED = 'accepted', 'Acceptée'
        DECLINED = 'declined', 'Refusée'

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buyer_requests',
    )
    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='incoming_requests',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='requests',
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
    )
    message = models.TextField(blank=True)
    # Offre directe d'un acheteur (souvent étranger) à l'agriculteur.
    offer_price_tnd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
    )
    currency = models.CharField(max_length=3, default='TND')
    destination = models.CharField(max_length=20, blank=True)
    incoterm = models.CharField(max_length=3, default='FOB')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.buyer} → {self.farmer}'

    @property
    def total_tnd(self):
        if self.offer_price_tnd is None or self.quantity is None:
            return None
        return self.offer_price_tnd * self.quantity


class OfferMessage(models.Model):
    """Un message du fil de négociation entre l'acheteur et l'agriculteur."""

    offer = models.ForeignKey(BuyerRequest, on_delete=models.CASCADE, related_name='thread')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='offer_messages',
    )
    body = models.TextField(blank=True)
    price_tnd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    event = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']

    def __str__(self):
        return f'{self.author}: {self.body[:40]}'
