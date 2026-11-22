from django.urls import path

from apps.marketplace import views

app_name = 'network'

urlpatterns = [
    path('', views.network_board, name='board'),
]
