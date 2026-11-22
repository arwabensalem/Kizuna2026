from django.urls import path

from apps.digital_twin import views

urlpatterns = [
    path('homes/<int:pk>/', views.twin_state, name='twin_state'),
]
