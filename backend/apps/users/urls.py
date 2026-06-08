from django.urls import path

from . import views
from . import admin_views


urlpatterns = [
    path('register/', views.register, name='auth-register'),
    path('login/', views.login, name='auth-login'),
    path('refresh/', views.refresh_token, name='auth-refresh'),
    path('logout/', views.logout, name='auth-logout'),
    path('me/', views.get_me, name='auth-me'),
    path('profile/', views.update_profile, name='auth-profile'),
    path('dev-database-export/', views.export_dev_database, name='auth-dev-database-export'),
    # Admin user management
    path('admin/stats/', admin_views.admin_stats, name='admin-stats'),
    path('admin/users/', admin_views.admin_users_list, name='admin-users-list'),
    path('admin/users/<int:pk>/', admin_views.admin_user_detail, name='admin-user-detail'),
]
