from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import views_database

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    
    # Main application URLs
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('prediction/', views.prediction_page, name='prediction_page'),
    path('prediction/create-alert/', views.create_alert, name='create_alert'),
    path('barangays/', views.barangays_page, name='barangays_page'),
    path('barangays/<int:barangay_id>/', views.barangay_detail, name='barangay_detail'),
    path('notifications/', views.notifications_page, name='notifications_page'),
    path('config/', views.config_page, name='config_page'),
    path('weather/', views.weather_dashboard, name='weather_dashboard'),
    path('resilience-scores/', views.resilience_scores_page, name='resilience_scores'),
    
    # User Management URLs
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('users/', views.user_management, name='user_management'),
    path('users/<int:user_id>/', views.view_user, name='view_user'),
    path('users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    
    # API endpoints for frontend
    path('api/chart-data/', views.get_chart_data, name='get_chart_data'),
    path('api/map-data/', views.get_map_data, name='get_map_data'),
    path('api/sensor-data/', views.get_latest_sensor_data, name='get_latest_sensor_data'),
    path('api/flood-alerts/', views.get_flood_alerts, name='get_flood_alerts'),
    path('api/create-municipality/', views.api_create_municipality, name='api_create_municipality'),
    path('api/create-barangay/', views.api_create_barangay, name='api_create_barangay'),
    path('sensors/add/', views.add_sensor, name='add_sensor'),
    path('municipalities/add/', views.add_municipality, name='add_municipality'),
    path('barangays/add/', views.add_barangay, name='add_barangay'),
    
    # Database Management URLs
    path('database/', views_database.database_management, name='database_management'),
    path('database/backup/', views_database.create_backup, name='create_backup'),
    path('database/restore/', views_database.restore_backup, name='restore_backup'),
    path('database/download/<str:filename>/', views_database.download_backup, name='download_backup'),
    path('database/delete/<str:filename>/', views_database.delete_backup, name='delete_backup'),
]
