from django.urls import path

from apps.farms import views

app_name = 'farms'

urlpatterns = [
    path('', views.farm_list, name='list'),
    path('new/', views.farm_create, name='create'),
    path('conseils/', views.advice_shortcut, name='advice_first'),
    path('crops/', views.crop_list, name='crops'),
    path('crops/new/', views.crop_create, name='crop_create'),
    path('crops/<int:pk>/edit/', views.CropUpdateView.as_view(), name='crop_edit'),
    path('crops/<int:pk>/delete/', views.CropDeleteView.as_view(), name='crop_delete'),
    path('irrigation/', views.irrigation_list, name='irrigation'),
    path('irrigation/new/', views.irrigation_create, name='irrigation_create'),
    path('irrigation/<int:pk>/edit/', views.IrrigationSystemUpdateView.as_view(), name='irrigation_edit'),
    path('irrigation/<int:pk>/delete/', views.IrrigationSystemDeleteView.as_view(), name='irrigation_delete'),
    path('irrigation/<int:pk>/toggle/', views.irrigation_toggle, name='irrigation_toggle'),
    path('sensors/', views.sensor_list, name='sensors'),
    path('sensors/new/', views.sensor_create, name='sensor_create'),
    path('sensors/<int:pk>/edit/', views.FarmSensorUpdateView.as_view(), name='sensor_edit'),
    path('sensors/<int:pk>/delete/', views.FarmSensorDeleteView.as_view(), name='sensor_delete'),
    path('tanks/', views.tank_list, name='tanks'),
    path('tanks/new/', views.tank_create, name='tank_create'),
    path('tanks/<int:pk>/edit/', views.FarmTankUpdateView.as_view(), name='tank_edit'),
    path('tanks/<int:pk>/delete/', views.FarmTankDeleteView.as_view(), name='tank_delete'),
    path('solar/', views.solar_list, name='solar'),
    path('solar/new/', views.solar_create, name='solar_create'),
    path('solar/<int:pk>/edit/', views.FarmSolarUpdateView.as_view(), name='solar_edit'),
    path('solar/<int:pk>/delete/', views.FarmSolarDeleteView.as_view(), name='solar_delete'),
    path('<int:pk>/', views.farm_detail, name='detail'),
    path('<int:pk>/conseils/', views.farm_advice, name='advice'),
    path('<int:pk>/edit/', views.farm_edit, name='edit'),
    path('<int:pk>/delete/', views.FarmDeleteView.as_view(), name='delete'),
]
