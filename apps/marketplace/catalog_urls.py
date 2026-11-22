from django.urls import path

from apps.marketplace import catalog_views

app_name = 'market'

urlpatterns = [
    path('', catalog_views.marketplace, name='board'),
    path('products/new/', catalog_views.product_create, name='create'),
    path('products/<int:pk>/', catalog_views.product_detail, name='detail'),
    path('products/<int:pk>/edit/', catalog_views.product_edit, name='edit'),
    path('products/<int:pk>/delete/', catalog_views.product_delete, name='delete'),
    path('products/<int:pk>/simulation/', catalog_views.simulation, name='simulation'),
    path('products/<int:pk>/simulation/say/', catalog_views.simulation_say, name='simulation_say'),
    path('ai-check/', catalog_views.ai_check, name='ai_check'),
    path('negotiation/', catalog_views.negotiation_start, name='negotiation'),
    path('fair-price/', catalog_views.fair_price, name='fair_price'),
    path('offers/', catalog_views.offers, name='offers'),
    path('offers/<int:pk>/', catalog_views.offer_detail, name='offer'),
    path('farmers/<int:pk>/', catalog_views.farmer_profile, name='farmer'),
]
