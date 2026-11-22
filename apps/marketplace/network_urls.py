from django.urls import path

from apps.marketplace import views

urlpatterns = [
    path('', views.network_state, name='network_state'),
]
