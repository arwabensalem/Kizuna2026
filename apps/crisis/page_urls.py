from django.urls import path

from apps.crisis import views

app_name = 'crisis'

urlpatterns = [
    path('', views.lab, name='lab'),
    path('day/', views.crisis_day, name='day'),
]
