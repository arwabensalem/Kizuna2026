from django.urls import path

from apps.actuators import views

app_name = 'actuators'

urlpatterns = [
    path('', views.board, name='board'),
    path('mode/', views.set_mode, name='mode'),
    path('authorize/', views.authorize, name='authorize'),
    path('run/', views.run, name='run'),
]
