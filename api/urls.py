from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'sensors', views.SensorViewSet)
router.register(r'sensor-data', views.SensorDataViewSet)
router.register(r'municipalities', views.MunicipalityViewSet)
router.register(r'barangays', views.BarangayViewSet)
router.register(r'flood-alerts', views.FloodAlertViewSet)
router.register(r'flood-risk-zones', views.FloodRiskZoneViewSet)
router.register(r'threshold-settings', views.ThresholdSettingViewSet)
router.register(r'resilience-scores', views.ResilienceScoreViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('add-sensor-data/', views.add_sensor_data, name='add_sensor_data'),
    path('update-threshold/', views.update_threshold_setting, name='update_threshold_setting'),
    path('prediction/', views.flood_prediction, name='flood_prediction'),
    path('compare-algorithms/', views.compare_prediction_algorithms, name='compare_algorithms'),
    path('map-data/', views.get_map_data, name='get_map_data'),
    path('apply-thresholds/', views.apply_thresholds, name='apply_thresholds'),
    path('threshold-visualization/', views.threshold_visualization, name='threshold_visualization'),
    path('threshold-visualization/<str:parameter>/', views.threshold_visualization_parameter, name='threshold_visualization_parameter'),
    path('historical-suggestion/', views.historical_suggestion, name='historical_suggestion'),
    path('all-barangays/', views.get_all_barangays, name='get_all_barangays'),
]
