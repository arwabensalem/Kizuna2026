from django.urls import path

from apps.ai_engine import views

urlpatterns = [
    path('water/', views.water, name='ai_water'),
    path('energy/', views.energy, name='ai_energy'),
    path('farm-water/', views.farm_water, name='ai_farm_water'),
    path('crop-stress/', views.crop_stress, name='ai_crop_stress'),
    path('anomaly/', views.anomaly, name='ai_anomaly'),
]
