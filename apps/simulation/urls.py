from django.urls import path

from apps.simulation import views

app_name = 'simulation'

urlpatterns = [
    path('', views.board, name='board'),
]
