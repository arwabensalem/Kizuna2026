from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({'status': 'ok', 'project': 'KIZUNA'})


urlpatterns = [
    path('health/', health, name='health'),
    path('accounts/', include('apps.accounts.api_urls')),
    path('homes/', include('apps.homes.api_urls')),
    path('farms/', include('apps.farms.api_urls')),
    path('resources/', include('apps.resources.api_urls')),
    path('sensors/', include('apps.sensors.api_urls')),
    path('actuators/', include('apps.actuators.api_urls')),
    path('crisis/', include('apps.crisis.urls')),
    path('twin/', include('apps.digital_twin.urls')),
    path('exchange/', include('apps.marketplace.urls')),
]
