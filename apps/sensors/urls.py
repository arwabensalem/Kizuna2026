from django.urls import path

from apps.sensors import views

app_name = 'sensors'

urlpatterns = [
    path('home/', views.home_sensor_list, name='home'),
    path('farm/', views.farm_sensor_list, name='farm'),
    path('<int:pk>/edit/', views.SensorUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.SensorDeleteView.as_view(), name='delete'),
]
