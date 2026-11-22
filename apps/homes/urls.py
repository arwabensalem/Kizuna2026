from django.urls import path

from apps.homes import views

app_name = 'homes'

urlpatterns = [
    path('', views.home_list, name='list'),
    path('new/', views.home_create, name='create'),
    path('factures/', views.bills_shortcut, name='bills'),
    path('appliances/', views.appliance_list, name='appliances'),
    path('appliances/new/', views.appliance_create, name='appliance_create'),
    path('appliances/<int:pk>/edit/', views.ApplianceUpdateView.as_view(), name='appliance_edit'),
    path('appliances/<int:pk>/delete/', views.ApplianceDeleteView.as_view(), name='appliance_delete'),
    path('appliances/<int:pk>/toggle/', views.appliance_toggle, name='appliance_toggle'),
    path('<int:pk>/', views.home_detail, name='detail'),
    path('<int:pk>/anomalies/', views.anomaly_board, name='anomalies'),
    path('<int:pk>/anomalies/check/', views.anomaly_evaluate, name='anomaly_check'),
    path('<int:pk>/anomalies/autopilot/', views.anomaly_autopilot, name='anomaly_autopilot'),
    path('<int:pk>/anomalies/valve/', views.anomaly_valve, name='anomaly_valve'),
    path('<int:pk>/anomalies/<int:event_pk>/acknowledge/', views.anomaly_acknowledge, name='anomaly_acknowledge'),
    path('<int:pk>/edit/', views.HomeUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.HomeDeleteView.as_view(), name='delete'),
    path('<int:pk>/rooms/new/', views.room_create, name='room_create'),
    path('rooms/<int:pk>/edit/', views.RoomUpdateView.as_view(), name='room_edit'),
    path('rooms/<int:pk>/delete/', views.RoomDeleteView.as_view(), name='room_delete'),
]
