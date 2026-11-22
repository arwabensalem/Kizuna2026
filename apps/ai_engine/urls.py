from django.urls import path

from apps.ai_engine import views

app_name = 'ai'

urlpatterns = [
    path('', views.board, name='board'),
]
