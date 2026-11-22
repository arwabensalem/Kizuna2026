from django.urls import path

from apps.resources import views

app_name = 'resources'

urlpatterns = [
    path('passports/', views.passport_list, name='passports'),
    path('passports/<int:pk>/edit/', views.PassportUpdateView.as_view(), name='passport_edit'),
    path('passports/<int:pk>/delete/', views.PassportDeleteView.as_view(), name='passport_delete'),
]
