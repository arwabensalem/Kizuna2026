from django.urls import path

from apps.brain import views

app_name = 'brain'

urlpatterns = [
    path('', views.board, name='board'),
    path('panels/', views.panels, name='panels'),
]
