from django.urls import path

from apps.digital_twin import views

app_name = 'twin'

urlpatterns = [
    path('', views.board, name='board'),
]
