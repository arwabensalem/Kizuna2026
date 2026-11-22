from django.urls import path

from apps.simulation import views

urlpatterns = [
    path('state/', views.state, name='simulation_state'),
    path('advance/', views.advance, name='simulation_advance'),
    path('reset/', views.reset, name='simulation_reset'),
]
