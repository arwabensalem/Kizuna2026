from django.urls import path

from apps.tunisia import views

urlpatterns = [
    path('', views.state, name='tunisia_state'),
]
