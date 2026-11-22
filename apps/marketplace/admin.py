from django.contrib import admin

from apps.marketplace.models import BuyerRequest, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'farmer', 'category', 'quantity', 'unit', 'availability', 'harvest_date')
    list_filter = ('category', 'availability')
    search_fields = ('name', 'origin', 'farmer__username')


@admin.register(BuyerRequest)
class BuyerRequestAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'farmer', 'product', 'quantity', 'created_at')
    search_fields = ('buyer__username', 'farmer__username', 'message')
