"""Queries for the agricultural marketplace.

No crisis-lab or simulation imports. Listings are records farmers saved.
"""

from django.db.models import Q

from apps.marketplace.models import Product


def search_products(query='', category='', availability='', export_only=False):
    products = Product.objects.select_related('farmer', 'farm')
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(origin__icontains=query)
            | Q(description__icontains=query)
            | Q(farmer__username__icontains=query)
        )
    if category in Product.Category.values:
        products = products.filter(category=category)
    if availability in Product.Availability.values:
        products = products.filter(availability=availability)
    if export_only:
        products = products.filter(export_ready=True)
    return products
