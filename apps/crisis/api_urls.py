from django.urls import path

from apps.crisis import views

urlpatterns = [
    path('simulate/', views.simulate, name='crisis_simulate'),
    path('day/', views.crisis_day_state, name='crisis_day'),
]
