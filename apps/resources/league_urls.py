from django.urls import path

from apps.resources.league_views import league_board

app_name = 'league'

urlpatterns = [
    path('', league_board, name='board'),
]
