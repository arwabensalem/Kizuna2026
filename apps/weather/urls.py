from django.urls import path

from apps.weather import views

app_name = 'weather'

urlpatterns = [
    path('', views.board, name='board'),
    path('collection/', views.save_collection, name='collection'),
    path('authorize/', views.authorize, name='authorize'),
    path('start/', views.start, name='start'),
    path('advance/', views.advance, name='advance'),
]
