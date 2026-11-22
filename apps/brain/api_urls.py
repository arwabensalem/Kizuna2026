from django.urls import path

from apps.brain import views

urlpatterns = [
    path('', views.state, name='brain_state'),
]
