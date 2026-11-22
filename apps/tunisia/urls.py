from django.urls import path

from apps.tunisia import views

app_name = 'tunisia'

urlpatterns = [
    path('', views.board, name='map'),
]
