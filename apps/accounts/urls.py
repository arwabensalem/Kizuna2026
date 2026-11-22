from django.urls import path

from apps.accounts import user_admin, views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.KizunaLoginView.as_view(), name='login'),
    path('logout/', views.KizunaLogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    # Gestion des utilisateurs (administrateur uniquement)
    path('users/', user_admin.users_list, name='users'),
    path('users/new/', user_admin.user_create, name='user_create'),
    path('users/<int:pk>/', user_admin.user_edit, name='user_edit'),
    path('users/<int:pk>/toggle/', user_admin.user_toggle, name='user_toggle'),
    path('users/<int:pk>/password/', user_admin.user_reset_password, name='user_reset_password'),
]
