from django.urls import path

from apps.resources.passport_views import passport_board

app_name = 'passport'

urlpatterns = [
    path('', passport_board, name='board'),
]
