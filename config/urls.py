from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.crisis.views import hackathon_demo
from config.api_urls import health

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),
    path('api/simulation/', include('apps.simulation.api_urls')),
    path('api/ai/', include('apps.ai_engine.api_urls')),
    path('api/v1/', include('config.api_urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('homes/', include('apps.homes.urls')),
    path('farms/', include('apps.farms.urls')),
    path('sensors/', include('apps.sensors.urls')),
    path('resources/', include('apps.resources.urls')),
    path('simulation/', include('apps.simulation.urls')),
    path('ai/', include('apps.ai_engine.urls')),
    path('autopilot/', include('apps.actuators.urls')),
    path('weather/', include('apps.weather.urls')),
    path('twin/', include('apps.digital_twin.page_urls')),
    path('api/twin/', include('apps.digital_twin.urls')),
    path('brain/', include('apps.brain.urls')),
    path('api/brain/', include('apps.brain.api_urls')),
    path('crisis/', include('apps.crisis.page_urls')),
    path('api/crisis/', include('apps.crisis.api_urls')),
    path('network/', include('apps.marketplace.page_urls')),
    path('api/network/', include('apps.marketplace.network_urls')),
    path('tunisia/', include('apps.tunisia.urls')),
    path('passport/', include('apps.resources.passport_urls')),
    path('league/', include('apps.resources.league_urls')),
    path('market/', include('apps.marketplace.catalog_urls')),
    path('api/tunisia/', include('apps.tunisia.api_urls')),
    path('demo/', hackathon_demo, name='demo'),
    path('', include('apps.dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
