from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Max, Avg, Sum, Q, Count, Min
from django.views.decorators.csrf import csrf_exempt
import math
import logging
import requests
from datetime import timedelta

# Import ML model functions
from flood_monitoring.ml.flood_prediction_model import predict_flood_probability, get_affected_barangays as ml_get_affected_barangays
from flood_monitoring.ml.flood_prediction_model import ADVANCED_ALGORITHMS_AVAILABLE, TENSORFLOW_AVAILABLE
from flood_monitoring.ml.flood_prediction_model import DEFAULT_CLASSIFICATION_ALGORITHM

# Set up logging
logger = logging.getLogger(__name__)

from core.models import (
    Sensor, SensorData, Municipality, Barangay, FloodRiskZone, 
    FloodAlert, ThresholdSetting, NotificationLog, EmergencyContact,
    ResilienceScore
)
from .serializers import (
    SensorSerializer, SensorDataSerializer, MunicipalitySerializer, BarangaySerializer,
    FloodRiskZoneSerializer, FloodAlertSerializer, ThresholdSettingSerializer, 
    NotificationLogSerializer, EmergencyContactSerializer, ResilienceScoreSerializer
)

class SensorViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for sensors"""
    queryset = Sensor.objects.all()
    serializer_class = SensorSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = Sensor.objects.all()
        sensor_type = self.request.query_params.get('type', None)
        active = self.request.query_params.get('active', None)
        
        if sensor_type:
            queryset = queryset.filter(sensor_type=sensor_type)
        
        if active:
            active_bool = active.lower() == 'true'
            queryset = queryset.filter(active=active_bool)
            
        return queryset

class SensorDataViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for sensor data"""
    queryset = SensorData.objects.all()
    serializer_class = SensorDataSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = SensorData.objects.all().order_by('-timestamp')
        sensor_id = self.request.query_params.get('sensor_id', None)
        sensor_type = self.request.query_params.get('sensor_type', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        limit = self.request.query_params.get('limit', None)
        municipality_id = self.request.query_params.get('municipality_id', None)
        barangay_id = self.request.query_params.get('barangay_id', None)
        
        if sensor_id:
            queryset = queryset.filter(sensor_id=sensor_id)
        
        if sensor_type:
            queryset = queryset.filter(sensor__sensor_type=sensor_type)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
            
        # Filter by location if specified
        if municipality_id:
            queryset = queryset.filter(sensor__municipality_id=municipality_id)
            
        if barangay_id:
            queryset = queryset.filter(sensor__barangay_id=barangay_id)
        
        if limit:
            queryset = queryset[:int(limit)]
            
        return queryset

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def add_sensor_data(request):
    """API endpoint for adding new sensor data"""
    sensor_id = request.data.get('sensor_id')
    value = request.data.get('value')
    timestamp = request.data.get('timestamp', timezone.now())
    
    try:
        sensor = Sensor.objects.get(id=sensor_id)
    except Sensor.DoesNotExist:
        return Response(
            {'error': f'Sensor with ID {sensor_id} does not exist'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Create the new sensor data
    data = SensorData.objects.create(
        sensor=sensor,
        value=value,
        timestamp=timestamp
    )
    
    # Check if the new reading exceeds any thresholds
    check_thresholds(sensor, value)
    
    serializer = SensorDataSerializer(data)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

def check_thresholds(sensor, value):
    """Check if a sensor reading exceeds any thresholds and create alerts if needed"""
    try:
        threshold = ThresholdSetting.objects.get(parameter=sensor.sensor_type)
    except ThresholdSetting.DoesNotExist:
        # No threshold set for this sensor type
        return
    
    # Determine the severity level based on the thresholds
    severity_level = None
    
    if value >= threshold.catastrophic_threshold:
        severity_level = 5  # Catastrophic
    elif value >= threshold.emergency_threshold:
        severity_level = 4  # Emergency
    elif value >= threshold.warning_threshold:
        severity_level = 3  # Warning
    elif value >= threshold.watch_threshold:
        severity_level = 2  # Watch
    elif value >= threshold.advisory_threshold:
        severity_level = 1  # Advisory
    
    if severity_level:
        # Check if there's already an active alert for this sensor type
        existing_alert = FloodAlert.objects.filter(
            title__startswith=f"{sensor.sensor_type.title()} Alert",
            active=True
        ).first()
        
        if existing_alert:
            # Update the existing alert if the new severity is higher
            if severity_level > existing_alert.severity_level:
                existing_alert.severity_level = severity_level
                existing_alert.description = f"{sensor.sensor_type.title()} has reached {value} {threshold.unit}, which exceeds the {get_severity_name(severity_level)} threshold."
                existing_alert.updated_at = timezone.now()
                existing_alert.save()
        else:
            # Create a new alert
            alert = FloodAlert.objects.create(
                title=f"{sensor.sensor_type.title()} Alert: {get_severity_name(severity_level)}",
                description=f"{sensor.sensor_type.title()} has reached {value} {threshold.unit}, which exceeds the {get_severity_name(severity_level)} threshold.",
                severity_level=severity_level,
                active=True
            )
            
            # For simplicity, we'll add all barangays to the alert
            # In a real system, you'd determine which barangays are affected
            barangays = Barangay.objects.all()
            alert.affected_barangays.set(barangays)

def get_severity_name(severity_level):
    """Get the human-readable name for a severity level"""
    severity_names = {
        1: 'Advisory',
        2: 'Watch',
        3: 'Warning',
        4: 'Emergency',
        5: 'Catastrophic'
    }
    return severity_names.get(severity_level, 'Unknown')


@csrf_exempt
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def update_threshold_setting(request):
    """Create or update a ThresholdSetting by parameter.
    Expected JSON body:
    {
        "parameter": "rainfall|water_level|temperature|humidity|wind_speed",
        "advisory_threshold": float,
        "watch_threshold": float,
        "warning_threshold": float,
        "emergency_threshold": float,
        "catastrophic_threshold": float,
        "unit": "mm|m|°C|%|km/h"
    }
    """
    data = request.data if isinstance(request.data, dict) else {}
    param = (data.get('parameter') or '').strip()

    # Validate numeric inputs
    try:
        a = float(data.get('advisory_threshold'))
        w = float(data.get('watch_threshold'))
        wn = float(data.get('warning_threshold'))
        e = float(data.get('emergency_threshold'))
        c = float(data.get('catastrophic_threshold'))
    except (TypeError, ValueError):
        return Response({'success': False, 'message': 'All threshold values must be numeric.'}, status=status.HTTP_400_BAD_REQUEST)

    unit = (data.get('unit') or '').strip()

    if not param:
        return Response({'success': False, 'message': 'Parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    if not (a < w < wn < e < c):
        return Response({'success': False, 'message': 'Thresholds must be strictly increasing: Advisory < Watch < Warning < Emergency < Catastrophic.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        th = ThresholdSetting.objects.filter(parameter__iexact=param).first()
        created = False
        if th:
            th.advisory_threshold = a
            th.watch_threshold = w
            th.warning_threshold = wn
            th.emergency_threshold = e
            th.catastrophic_threshold = c
            th.unit = unit
            if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False):
                th.last_updated_by = request.user
            th.save()
        else:
            th = ThresholdSetting(
                parameter=param,
                advisory_threshold=a,
                watch_threshold=w,
                warning_threshold=wn,
                emergency_threshold=e,
                catastrophic_threshold=c,
                unit=unit,
            )
            if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False):
                th.last_updated_by = request.user
            th.save()
            created = True

        return Response({
            'success': True,
            'created': created,
            'data': {
                'id': th.id,
                'parameter': th.parameter,
                'advisory_threshold': th.advisory_threshold,
                'watch_threshold': th.watch_threshold,
                'warning_threshold': th.warning_threshold,
                'emergency_threshold': th.emergency_threshold,
                'catastrophic_threshold': th.catastrophic_threshold,
                'unit': th.unit,
                'updated_at': th.updated_at,
            }
        })
    except Exception as ex:
        logger.exception('Failed to update threshold setting')
        return Response({'success': False, 'message': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ---------------- Parameter Status (Compact) ----------------
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def parameter_status(request):
    """Return a compact Parameter Status list for dashboard display.
    Query params:
      - municipality_id (optional)
      - barangay_id (optional)
      - parameters (optional, comma-separated): default all configured in ThresholdSetting

    Response schema:
    {
      "generated_at": ISO8601,
      "filters": { municipality_id, barangay_id },
      "items": [
        {
          "parameter": "temperature|humidity|rainfall|water_level|wind_speed",
          "label": "Temperature",
          "unit": "°C|%|mm|m|km/h",
          "latest": value or null,
          "level": 0-5,
          "level_name": "Normal|Advisory|...|Catastrophic",
          "threshold": reference_threshold_for_level_or_null
        }, ...
      ],
      "max_level": 0-5
    }
    """
    municipality_id = request.GET.get('municipality_id')
    barangay_id = request.GET.get('barangay_id')
    param_filter = request.GET.get('parameters')

    # Build location filters
    sensor_filters = {}
    if municipality_id:
        sensor_filters['sensor__municipality_id'] = municipality_id
    if barangay_id:
        sensor_filters['sensor__barangay_id'] = barangay_id

    # Select thresholds/parameters to include
    qs = ThresholdSetting.objects.all()
    if param_filter:
        params = [p.strip() for p in param_filter.split(',') if p.strip()]
        qs = qs.filter(parameter__in=params)

    def compute_level(val, t):
        if val is None:
            return 0
        if val >= t.catastrophic_threshold: return 5
        if val >= t.emergency_threshold:    return 4
        if val >= t.warning_threshold:      return 3
        if val >= t.watch_threshold:        return 2
        if val >= t.advisory_threshold:     return 1
        return 0

    def level_name(n):
        return {0:'Normal',1:'Advisory',2:'Watch',3:'Warning',4:'Emergency',5:'Catastrophic'}.get(int(n), 'Normal')

    items = []
    for t in qs:
        # Latest reading with graceful fallback
        base = {'sensor__sensor_type': t.parameter}
        base.update(sensor_filters)
        latest = SensorData.objects.filter(**base).order_by('-timestamp').first()
        if not latest and barangay_id and municipality_id:
            muni_only = {
                'sensor__sensor_type': t.parameter,
                'sensor__municipality_id': municipality_id,
                'sensor__barangay__isnull': True,
            }
            latest = SensorData.objects.filter(**muni_only).order_by('-timestamp').first()
        if not latest:
            global_q = {
                'sensor__sensor_type': t.parameter,
                'sensor__municipality__isnull': True,
                'sensor__barangay__isnull': True,
            }
            latest = SensorData.objects.filter(**global_q).order_by('-timestamp').first()

        latest_val = latest.value if latest else None
        lvl = compute_level(latest_val, t)
        thr_map = {1: t.advisory_threshold, 2: t.watch_threshold, 3: t.warning_threshold, 4: t.emergency_threshold, 5: t.catastrophic_threshold}
        ref_threshold = thr_map.get(lvl)

        label = {
            'temperature': 'Temperature',
            'humidity': 'Humidity',
            'rainfall': 'Rainfall',
            'water_level': 'Water Level',
            'wind_speed': 'Wind Speed',
        }.get(t.parameter, t.parameter.replace('_',' ').title())

        items.append({
            'parameter': t.parameter,
            'label': label,
            'unit': t.unit,
            'latest': latest_val,
            'level': lvl,
            'level_name': level_name(lvl),
            'threshold': ref_threshold,
        })

    max_level = max([it['level'] for it in items], default=0)
    return Response({
        'generated_at': timezone.now(),
        'filters': {'municipality_id': municipality_id, 'barangay_id': barangay_id},
        'items': items,
        'max_level': max_level,
    })

class MunicipalityViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for municipalities"""
    queryset = Municipality.objects.all()
    serializer_class = MunicipalitySerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = Municipality.objects.all()
        name = self.request.query_params.get('name', None)
        province = self.request.query_params.get('province', None)
        is_active = self.request.query_params.get('is_active', None)
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        if province:
            queryset = queryset.filter(province__icontains=province)
        
        if is_active:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
            
        return queryset

REGION_1_PROVINCES = [
    'Ilocos Norte',
    'Ilocos Sur',
    'La Union',
    'Pangasinan'
]

class MunicipalityViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for municipalities"""
    queryset = Municipality.objects.all()
    serializer_class = MunicipalitySerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = Municipality.objects.all()
        name = self.request.query_params.get('name', None)
        province = self.request.query_params.get('province', None)
        is_active = self.request.query_params.get('is_active', None)
        region_1 = self.request.query_params.get('region_1', None)
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        if province:
            queryset = queryset.filter(province__icontains=province)
        elif region_1 and region_1.lower() == 'true':
            # Filter for all Region 1 provinces
            queryset = queryset.filter(province__in=REGION_1_PROVINCES)
        
        if is_active:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
            
        return queryset

class FloodAlertViewSet(viewsets.ModelViewSet):
    """API endpoint for flood alerts"""
    queryset = FloodAlert.objects.all().order_by('-issued_at')
    serializer_class = FloodAlertSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = FloodAlert.objects.all().order_by('-issued_at')
        active = self.request.query_params.get('active', None)
        severity = self.request.query_params.get('severity', None)
        municipality_id = self.request.query_params.get('municipality_id', None)
        barangay_id = self.request.query_params.get('barangay_id', None)
        
        if active:
            active_bool = active.lower() == 'true'
            queryset = queryset.filter(active=active_bool)
        
        if severity:
            queryset = queryset.filter(severity_level=severity)
            
        if municipality_id:
            # Filter alerts by affected barangays within the municipality
            queryset = queryset.filter(affected_barangays__municipality_id=municipality_id).distinct()
        
        if barangay_id:
            queryset = queryset.filter(affected_barangays__id=barangay_id)
            
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(issued_by=self.request.user)

class FloodRiskZoneViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for flood risk zones"""
    queryset = FloodRiskZone.objects.all()
    serializer_class = FloodRiskZoneSerializer
    permission_classes = [permissions.AllowAny]

class ThresholdSettingViewSet(viewsets.ModelViewSet):
    """API endpoint for threshold settings"""
    queryset = ThresholdSetting.objects.all()
    serializer_class = ThresholdSettingSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        qs = ThresholdSetting.objects.all()
        param = self.request.query_params.get('parameter', None)
        if param:
            qs = qs.filter(parameter__iexact=param.strip())
        return qs
    
    def perform_create(self, serializer):
        serializer.save(last_updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(last_updated_by=self.request.user)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def compare_prediction_algorithms(request):
    """API endpoint for comparing predictions from different ML algorithms"""
    
    # Get location filters from request parameters
    municipality_id = request.GET.get('municipality_id', None)
    barangay_id = request.GET.get('barangay_id', None)
    
    # Get the algorithms to compare
    algorithms = request.GET.getlist('algorithms', [])
    
    # Default to comparing all available algorithms if none specified
    if not algorithms:
        algorithms = ['random_forest']
        if ADVANCED_ALGORITHMS_AVAILABLE:
            algorithms.extend(['gradient_boosting', 'svm'])
            if TENSORFLOW_AVAILABLE:
                algorithms.append('lstm')
    
    # Query filters to apply to sensor data - same as flood_prediction
    sensor_filters = {}
    
    # Apply location filters if provided
    municipality = None
    if municipality_id:
        try:
            # Get the municipality
            municipality = Municipality.objects.get(id=municipality_id)
            # Filter sensors by municipality
            sensor_filters['sensor__municipality'] = municipality
        except Municipality.DoesNotExist:
            pass
    
    barangay = None
    if barangay_id:
        try:
            # Get the barangay
            barangay = Barangay.objects.get(id=barangay_id)
            # Filter sensors by barangay
            sensor_filters['sensor__barangay'] = barangay
        except Barangay.DoesNotExist:
            pass
    
    # Get recent rainfall data
    end_date = timezone.now()
    start_date_24h = end_date - timedelta(hours=24)
    start_date_48h = end_date - timedelta(hours=48)
    start_date_7d = end_date - timedelta(days=7)
    
    # Get rainfall data for different time periods
    rainfall_filters_24h = {
        'sensor__sensor_type': 'rainfall',
        'timestamp__gte': start_date_24h,
        'timestamp__lte': end_date
    }
    rainfall_filters_24h.update(sensor_filters)  # Add location filters
    
    rainfall_24h = SensorData.objects.filter(
        **rainfall_filters_24h
    ).aggregate(total=Sum('value'), avg=Avg('value'), max=Max('value'))
    
    rainfall_filters_48h = {
        'sensor__sensor_type': 'rainfall',
        'timestamp__gte': start_date_48h,
        'timestamp__lte': end_date
    }
    rainfall_filters_48h.update(sensor_filters)  # Add location filters
    
    rainfall_48h = SensorData.objects.filter(
        **rainfall_filters_48h
    ).aggregate(total=Sum('value'), avg=Avg('value'), max=Max('value'))
    
    rainfall_filters_7d = {
        'sensor__sensor_type': 'rainfall',
        'timestamp__gte': start_date_7d,
        'timestamp__lte': end_date
    }
    rainfall_filters_7d.update(sensor_filters)  # Add location filters
    
    rainfall_7d = SensorData.objects.filter(
        **rainfall_filters_7d
    ).aggregate(total=Sum('value'), avg=Avg('value'), max=Max('value'))
    
    # Get water level, soil saturation, and temperature data (same as in flood_prediction)
    water_level_filters = {
        'sensor__sensor_type': 'water_level',
        'timestamp__gte': start_date_24h
    }
    water_level_filters.update(sensor_filters)  # Add location filters
    
    water_level_data = SensorData.objects.filter(
        **water_level_filters
    ).order_by('-timestamp')
    
    water_level_current = 0
    water_level_24h_ago = 0
    
    # Get current water level and water level 24 hours ago
    if water_level_data.exists():
        water_level_current = water_level_data.first().value
        
        # Get water level 24 hours ago (approximately)
        old_water_level_data = water_level_data.filter(timestamp__lte=start_date_24h + timedelta(hours=1)).order_by('-timestamp').first()
        if old_water_level_data:
            water_level_24h_ago = old_water_level_data.value
    
    # Calculate water level change in 24 hours
    water_level_change_24h = water_level_current - water_level_24h_ago
    
    # Get soil saturation (using humidity as a proxy in our system)
    humidity_filters = {
        'sensor__sensor_type': 'humidity',
        'timestamp__gte': start_date_24h
    }
    humidity_filters.update(sensor_filters)  # Add location filters
    
    humidity_data = SensorData.objects.filter(
        **humidity_filters
    ).order_by('-timestamp')
    
    soil_saturation = 0
    
    if humidity_data.exists():
        # Using humidity as a proxy for soil saturation
        soil_saturation = humidity_data.first().value
    
    # Get temperature data
    temp_filters = {
        'sensor__sensor_type': 'temperature',
        'timestamp__gte': start_date_24h
    }
    temp_filters.update(sensor_filters)  # Add location filters
    
    temp_data = SensorData.objects.filter(
        **temp_filters
    ).order_by('-timestamp')
    
    temperature_value = 25  # Default temperature
    
    if temp_data.exists():
        temperature_value = temp_data.first().value
    
    # Create input data for ML prediction model
    input_data = {
        'rainfall_24h': rainfall_24h['total'] if rainfall_24h['total'] else 0,
        'rainfall_48h': rainfall_48h['total'] if rainfall_48h['total'] else 0,
        'rainfall_7d': rainfall_7d['total'] if rainfall_7d['total'] else 0,
        'water_level': water_level_current,
        'water_level_change_24h': water_level_change_24h,
        'temperature': temperature_value,
        'humidity': soil_saturation,
        'soil_saturation': soil_saturation,
        # Use a default elevation for the selected area
        'elevation': 25 if municipality else 20,
        # Add the month and day for seasonal patterns
        'month': end_date.month,
        'day_of_year': end_date.timetuple().tm_yday,
        # Historical floods (this would come from a database in a real system)
        'historical_floods_count': 2 if barangay_id else 1
    }
    
    logger.info(f"Input data for ML prediction comparison: {input_data}")
    
    # Compare predictions from different algorithms
    comparison_results = []
    
    for algorithm in algorithms:
        try:
            # Use the ML model to predict flood probability with this algorithm
            ml_prediction = predict_flood_probability(input_data, classification_algorithm=algorithm)
            logger.info(f"ML Prediction results using {algorithm} algorithm: {ml_prediction}")
            
            # Format the prediction result with algorithm info
            algorithm_result = {
                'algorithm': algorithm,
                'probability': ml_prediction['probability'],
                'severity_level': ml_prediction['severity_level'],
                'severity_name': get_severity_name(ml_prediction['severity_level']),
                'hours_to_flood': ml_prediction['hours_to_flood'],
                'impact': ml_prediction['impact'],
                'contributing_factors': ml_prediction['contributing_factors']
            }
            
            comparison_results.append(algorithm_result)
        except Exception as e:
            logger.error(f"Error using {algorithm} for prediction: {e}")
            # Skip this algorithm and continue with others
            comparison_results.append({
                'algorithm': algorithm,
                'error': str(e),
                'status': 'failed'
            })
    
    # Return the comparison results
    return Response({
        'input_data': input_data,
        'available_algorithms': algorithms,
        'results': comparison_results,
        'location': {
            'municipality': municipality.name if municipality else None,
            'municipality_id': municipality.id if municipality else None,
            'barangay': barangay.name if barangay else None,
            'barangay_id': barangay.id if barangay else None
        },
        'timestamp': end_date,
        'default_algorithm': DEFAULT_CLASSIFICATION_ALGORITHM
    })

@api_view(['GET', 'POST'])
@permission_classes([permissions.AllowAny])
def flood_prediction(request):
    """API endpoint for flood prediction based on real-time sensor data using ML models"""
    
    # Get parameters from request (either GET or POST)
    if request.method == 'POST':
        # Get data from POST request body
        municipality_id = request.data.get('municipality_id', None)
        barangay_id = request.data.get('barangay_id', None)
        algorithm = request.data.get('algorithm', None)
        # If user submitted actual prediction data directly, use that instead of sensors
        user_prediction_data = {
            'rainfall_24h': request.data.get('rainfall_24h'),
            'rainfall_48h': request.data.get('rainfall_48h'),
            'rainfall_7d': request.data.get('rainfall_7d'),
            'water_level': request.data.get('water_level'),
            'water_level_change_24h': request.data.get('water_level_change_24h'),
            'temperature': request.data.get('temperature'),
            'humidity': request.data.get('humidity'),
            'soil_saturation': request.data.get('soil_saturation'),
            'elevation': request.data.get('elevation'),
            'month': request.data.get('month'),
            'day_of_year': request.data.get('day_of_year'),
            'historical_floods_count': request.data.get('historical_floods_count')
        }
        # Remove None values
        user_prediction_data = {k: v for k, v in user_prediction_data.items() if v is not None}
    else:
        # Get data from GET parameters
        municipality_id = request.GET.get('municipality_id', None)
        barangay_id = request.GET.get('barangay_id', None)
        algorithm = request.GET.get('algorithm', None)  # Get algorithm selection if provided
        user_prediction_data = {}
    
    # Query filters to apply to sensor data
    sensor_filters = {}
    
    # Apply location filters if provided
    municipality = None
    if municipality_id:
        try:
            # Get the municipality
            municipality = Municipality.objects.get(id=municipality_id)
            # Filter sensors by municipality
            sensor_filters['sensor__municipality'] = municipality
        except Municipality.DoesNotExist:
            pass
    
    barangay = None
    if barangay_id:
        try:
            # Get the barangay
            barangay = Barangay.objects.get(id=barangay_id)
            # Filter sensors by barangay
            sensor_filters['sensor__barangay'] = barangay
        except Barangay.DoesNotExist:
            pass
    
    # Get recent rainfall data
    end_date = timezone.now()
    start_date_24h = end_date - timedelta(hours=24)
    start_date_48h = end_date - timedelta(hours=48)
    start_date_7d = end_date - timedelta(days=7)
    start_date_72h = end_date - timedelta(hours=72) # For backward compatibility
    
    # Get rainfall data for different time periods
    rainfall_filters_24h = {
        'sensor__sensor_type': 'rainfall',
        'timestamp__gte': start_date_24h,
        'timestamp__lte': end_date
    }
    rainfall_filters_24h.update(sensor_filters)  # Add location filters
    
    rainfall_24h = SensorData.objects.filter(
        **rainfall_filters_24h
    ).aggregate(total=Sum('value'), avg=Avg('value'), max=Max('value'))
    
    rainfall_filters_48h = {
        'sensor__sensor_type': 'rainfall',
        'timestamp__gte': start_date_48h,
        'timestamp__lte': end_date
    }
    rainfall_filters_48h.update(sensor_filters)  # Add location filters
    
    rainfall_48h = SensorData.objects.filter(
        **rainfall_filters_48h
    ).aggregate(total=Sum('value'), avg=Avg('value'), max=Max('value'))
    
    rainfall_filters_7d = {
        'sensor__sensor_type': 'rainfall',
        'timestamp__gte': start_date_7d,
        'timestamp__lte': end_date
    }
    rainfall_filters_7d.update(sensor_filters)  # Add location filters
    
    rainfall_7d = SensorData.objects.filter(
        **rainfall_filters_7d
    ).aggregate(total=Sum('value'), avg=Avg('value'), max=Max('value'))
    
    # For backward compatibility
    rainfall_filters_72h = {
        'sensor__sensor_type': 'rainfall',
        'timestamp__gte': start_date_72h,
        'timestamp__lte': end_date
    }
    rainfall_filters_72h.update(sensor_filters)
    
    rainfall_72h = SensorData.objects.filter(
        **rainfall_filters_72h
    ).aggregate(total=Sum('value'), avg=Avg('value'), max=Max('value'))
    
    # Get water level data
    water_level_filters = {
        'sensor__sensor_type': 'water_level',
        'timestamp__gte': start_date_24h
    }
    water_level_filters.update(sensor_filters)  # Add location filters
    
    water_level_data = SensorData.objects.filter(
        **water_level_filters
    ).order_by('-timestamp')
    
    water_level_current = 0
    water_level_24h_ago = 0
    
    # Get current water level and water level 24 hours ago
    if water_level_data.exists():
        water_level_current = water_level_data.first().value
        
        # Get water level 24 hours ago (approximately)
        old_water_level_data = water_level_data.filter(timestamp__lte=start_date_24h + timedelta(hours=1)).order_by('-timestamp').first()
        if old_water_level_data:
            water_level_24h_ago = old_water_level_data.value
    
    # Calculate water level change in 24 hours
    water_level_change_24h = water_level_current - water_level_24h_ago
    
    # Get soil saturation (using humidity as a proxy in our system)
    humidity_filters = {
        'sensor__sensor_type': 'humidity',
        'timestamp__gte': start_date_24h
    }
    humidity_filters.update(sensor_filters)  # Add location filters
    
    humidity_data = SensorData.objects.filter(
        **humidity_filters
    ).order_by('-timestamp')
    
    soil_saturation = 0
    
    if humidity_data.exists():
        # Using humidity as a proxy for soil saturation
        soil_saturation = humidity_data.first().value
    
    # Get temperature data
    temp_filters = {
        'sensor__sensor_type': 'temperature',
        'timestamp__gte': start_date_24h
    }
    temp_filters.update(sensor_filters)  # Add location filters
    
    temp_data = SensorData.objects.filter(
        **temp_filters
    ).order_by('-timestamp')
    
    temperature_value = 25  # Default temperature
    
    if temp_data.exists():
        temperature_value = temp_data.first().value
        
    # For backward compatibility
    humidity = {'current': soil_saturation, 'avg': soil_saturation}
    temperature = {'current': temperature_value, 'avg': temperature_value}
    water_level = {'current': water_level_current, 'avg': water_level_current}
    
    # Create input data for ML prediction model
    input_data = {
        'rainfall_24h': rainfall_24h['total'] if rainfall_24h['total'] else 0,
        'rainfall_48h': rainfall_48h['total'] if rainfall_48h['total'] else 0,
        'rainfall_7d': rainfall_7d['total'] if rainfall_7d['total'] else 0,
        'water_level': water_level_current,
        'water_level_change_24h': water_level_change_24h,
        'temperature': temperature_value,
        'humidity': soil_saturation,
        'soil_saturation': soil_saturation,
        # Use a default elevation for the selected area
        'elevation': 25 if municipality else 20,
        # Add the month and day for seasonal patterns
        'month': end_date.month,
        'day_of_year': end_date.timetuple().tm_yday,
        # Historical floods (this would come from a database in a real system)
        'historical_floods_count': 2 if barangay_id else 1
    }
    
    logger.info(f"Input data for ML prediction: {input_data}")
    
    try:
        # Use the ML model to predict flood probability
        # If algorithm is specified and supported, use it
        ml_prediction = predict_flood_probability(input_data, classification_algorithm=algorithm) if algorithm else predict_flood_probability(input_data)
        logger.info(f"ML Prediction results using {algorithm if algorithm else 'default'} algorithm: {ml_prediction}")
        
        # Extract prediction data
        probability = ml_prediction['probability']
        impact = ml_prediction['impact']
        hours_to_flood = ml_prediction['hours_to_flood']
        factors = ml_prediction['contributing_factors']
        severity_level = ml_prediction['severity_level']
        
    except Exception as e:
        logger.error(f"Error using ML model for prediction: {e}")
        
        # Fall back to the heuristic model if ML fails
        logger.info("Falling back to heuristic model for prediction")
        
        # Initialize probability
        probability = 0
        
        # Factor 1: Recent heavy rainfall (24-hour)
        if rainfall_24h['total']:
            if rainfall_24h['total'] > 50:  # More than 50mm in 24 hours is significant
                probability += 30
            elif rainfall_24h['total'] > 25:
                probability += 20
            elif rainfall_24h['total'] > 10:
                probability += 10
        
        # Factor 2: Sustained rainfall (72-hour)
        if rainfall_72h['total']:
            if rainfall_72h['total'] > 100:  # More than 100mm in 72 hours
                probability += 25
            elif rainfall_72h['total'] > 50:
                probability += 15
            elif rainfall_72h['total'] > 25:
                probability += 5
        
        # Factor 3: Current water level
        if water_level['current']:
            if water_level['current'] > 1.5:  # Above 1.5m is high
                probability += 30
            elif water_level['current'] > 1.0:
                probability += 20
            elif water_level['current'] > 0.5:
                probability += 10
        
        # Factor 4: Soil saturation (using humidity as a proxy)
        if humidity['current']:
            if humidity['current'] > 90:  # Very humid/saturated soil
                probability += 15
            elif humidity['current'] > 80:
                probability += 10
            elif humidity['current'] > 70:
                probability += 5
        
        # Cap the probability
        probability = min(probability, 100)
        
        # Based on probability, calculate ETA
        hours_to_flood = None
        if probability >= 60:
            # Estimate hours to flood based on current water level and rainfall rate
            if water_level['current'] and rainfall_24h['avg']:
                # Simple formula: time to flood decreases with higher water level and rainfall rate
                current_level = water_level['current']
                target_level = 1.8  # assumed flood level
                level_difference = max(0, target_level - current_level)
                
                rainfall_rate = rainfall_24h['avg'] / 24  # mm per hour
                if rainfall_rate > 0:
                    # Simplified conversion from rainfall to water level rise
                    # This would be more complex in a real model
                    estimated_rise_rate = rainfall_rate * 0.02  # 1mm rain -> 0.02m water rise
                    
                    if estimated_rise_rate > 0:
                        hours_to_flood = level_difference / estimated_rise_rate
                        hours_to_flood = max(1, min(48, hours_to_flood))  # Cap between 1-48 hours
        
        # Determine contributing factors based on real data
        factors = []
        
        if rainfall_24h['total'] and rainfall_24h['total'] > 10:
            factors.append(f"Rainfall in the past 24 hours: {rainfall_24h['total']:.1f}mm")
            
        if rainfall_72h['total'] and rainfall_72h['total'] > 30:
            factors.append(f"Sustained rainfall over 72 hours: {rainfall_72h['total']:.1f}mm")
            
        if water_level['current'] and water_level['current'] > 0.8:
            factors.append(f"Elevated water level: {water_level['current']:.2f}m")
            
        if humidity['current'] and humidity['current'] > 70:
            factors.append(f"High soil moisture/humidity: {humidity['current']:.0f}%")
        
        if rainfall_24h['max'] and rainfall_24h['max'] > 5:
            factors.append(f"Heavy rainfall intensity: {rainfall_24h['max']:.1f}mm")
            
        # If we don't have enough factors, add a default
        if len(factors) < 2:
            if probability < 30:
                factors.append("No significant contributing factors identified")
            else:
                factors.append("Limited sensor data available for analysis")
        
        # Calculate flood impact based on probability
        impact = ""
        if probability >= 75:
            impact = "Severe flooding likely with significant impact to infrastructure and possible evacuation requirements."
            severity_level = 4  # Emergency
        elif probability >= 60:
            impact = "Moderate to severe flooding expected with potential property damage and road closures."
            severity_level = 3  # Warning
        elif probability >= 50:
            impact = "Moderate flooding expected in low-lying areas with potential minor property damage."
            severity_level = 2  # Watch
        elif probability >= 30:
            impact = "Minor flooding possible in flood-prone areas, general population unlikely to be affected."
            severity_level = 1  # Advisory
        else:
            impact = "No significant flooding expected under current conditions."
            severity_level = 0  # Normal
    
    # Find potentially affected barangays using the ML model if available
    affected_barangays = []
    
    try:
        # Try to use the ML model to get affected barangays first
        if probability >= 30 and municipality_id:
            ml_affected_barangays = ml_get_affected_barangays(municipality_id=municipality_id, probability_threshold=30)
            if ml_affected_barangays:
                logger.info(f"Using ML model to get affected barangays: {len(ml_affected_barangays)} found")
                affected_barangays = ml_affected_barangays
    except Exception as e:
        logger.error(f"Error using ML model for affected barangays: {e}")
    
    # If ML model didn't find any barangays or failed, fall back to the traditional method
    if not affected_barangays and probability >= 30:
        logger.info("Using traditional method to get affected barangays")
        # In a real system, we would use more sophisticated logic to determine affected areas
        # For now, we'll query barangays based on predicted severity level
        # Get barangays with recent alerts of this severity or higher
        recent_alert_filters = {
            'severity_level__gte': severity_level,
            'issued_at__gte': start_date_72h
        }
        
        # If a municipality filter was provided, get alerts for that municipality's barangays
        if municipality_id:
            try:
                municipality = Municipality.objects.get(id=municipality_id)
                # Get all barangays in this municipality
                municipality_barangays = Barangay.objects.filter(municipality=municipality).values_list('id', flat=True)
                # Only include alerts that affect at least one barangay in this municipality
                recent_alert_filters['affected_barangays__in'] = municipality_barangays
            except Municipality.DoesNotExist:
                pass
        
        # If a specific barangay was requested, only get alerts for that barangay
        if barangay_id:
            try:
                barangay = Barangay.objects.get(id=barangay_id)
                recent_alert_filters['affected_barangays'] = barangay
            except Barangay.DoesNotExist:
                pass
        
        recent_alerts = FloodAlert.objects.filter(**recent_alert_filters)
        
        if recent_alerts.exists():
            # Use barangays from similar past alerts
            barangay_ids = set()
            for alert in recent_alerts:
                barangay_ids.update(alert.affected_barangays.values_list('id', flat=True))
                
            barangays = Barangay.objects.filter(id__in=barangay_ids)
        else:
            # Fallback to barangays near water sensors with high readings
            if water_level['current'] and water_level['current'] > 0.5:
                # Get sensors with high water level readings
                high_water_sensor_filters = {
                    'sensor__sensor_type': 'water_level',
                    'value__gte': 0.5,
                    'timestamp__gte': start_date_24h
                }
                high_water_sensor_filters.update(sensor_filters)  # Add location filters
                
                high_water_sensors = SensorData.objects.filter(
                    **high_water_sensor_filters
                ).values_list('sensor_id', flat=True).distinct()
                
                # Get barangays from the requested municipality or a subset of all barangays
                barangay_filters = {}
                
                # If a municipality filter was provided, use it for barangays too
                if municipality_id:
                    try:
                        municipality = Municipality.objects.get(id=municipality_id)
                        barangay_filters['municipality'] = municipality
                    except Municipality.DoesNotExist:
                        pass
                        
                # If a specific barangay was requested, prioritize it
                if barangay_id:
                    try:
                        specific_barangay = Barangay.objects.get(id=barangay_id)
                        barangays = [specific_barangay]
                    except Barangay.DoesNotExist:
                        # Fall back to filtered barangays
                        barangays = Barangay.objects.filter(**barangay_filters).order_by('name')[:5]
                else:
                    # Get barangays based on municipality filter
                    barangays = Barangay.objects.filter(**barangay_filters).order_by('name')[:5]
            else:
                # Get a smaller set of barangays if water level is not high
                barangay_filters = {}
                
                # If a municipality filter was provided, use it for barangays too
                if municipality_id:
                    try:
                        municipality = Municipality.objects.get(id=municipality_id)
                        barangay_filters['municipality'] = municipality
                    except Municipality.DoesNotExist:
                        pass
                
                if barangay_id:
                    try:
                        specific_barangay = Barangay.objects.get(id=barangay_id)
                        barangays = [specific_barangay]
                    except Barangay.DoesNotExist:
                        barangays = Barangay.objects.filter(**barangay_filters).order_by('name')[:3]
                else:
                    barangays = Barangay.objects.filter(**barangay_filters).order_by('name')[:3]
        
            # Format barangay data for response if we didn't get from ML model
            if not affected_barangays:
                for barangay in barangays:
                    risk_level = "High" if probability >= 70 else ("Moderate" if probability >= 40 else "Low")
                    evacuation_centers = 3 if risk_level == "High" else (2 if risk_level == "Moderate" else 1)
                    
                    affected_barangays.append({
                        "id": barangay.id,
                        "name": barangay.name,
                        "municipality": barangay.municipality.name,
                        "population": barangay.population,
                        "risk_level": risk_level,
                        "evacuation_centers": evacuation_centers
                    })
    
    # Calculate flood time if hours_to_flood is available
    flood_time = None
    if hours_to_flood:
        flood_time = timezone.now() + timedelta(hours=hours_to_flood)
    
    # Prepare and return the prediction response
    prediction_data = {
        "probability": probability,
        "severity_level": severity_level,
        "impact": impact,
        "hours_to_flood": hours_to_flood,
        "flood_time": flood_time.isoformat() if flood_time else None,
        "contributing_factors": factors,
        "affected_barangays": affected_barangays,
        "last_updated": timezone.now().isoformat(),
        "rainfall_24h": rainfall_24h['total'] if rainfall_24h['total'] else 0,
        "water_level": water_level['current'] if water_level['current'] else 0,
        "prediction_source": "machine_learning" if 'ml_prediction' in locals() else "heuristic"
    }
    
    return Response(prediction_data)


class ResilienceScoreViewSet(viewsets.ModelViewSet):
    """API endpoint for community resilience scores"""
    queryset = ResilienceScore.objects.all().order_by('-assessment_date')
    serializer_class = ResilienceScoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        # Set the assessed_by field to the current user
        serializer.save(assessed_by=self.request.user)
        
    def perform_update(self, serializer):
        # Don't change the assessed_by field on updates
        serializer.save()
    
    def get_queryset(self):
        queryset = ResilienceScore.objects.all().order_by('-assessment_date')
        
        # Filter parameters
        municipality_id = self.request.query_params.get('municipality_id', None)
        barangay_id = self.request.query_params.get('barangay_id', None)
        is_current = self.request.query_params.get('is_current', None)
        min_score = self.request.query_params.get('min_score', None)
        max_score = self.request.query_params.get('max_score', None)
        category = self.request.query_params.get('category', None)
        assessed_after = self.request.query_params.get('assessed_after', None)
        assessed_before = self.request.query_params.get('assessed_before', None)
        
        # Apply filters
        if municipality_id:
            queryset = queryset.filter(municipality_id=municipality_id)
        
        if barangay_id:
            queryset = queryset.filter(barangay_id=barangay_id)
        
        if is_current:
            is_current_bool = is_current.lower() == 'true'
            queryset = queryset.filter(is_current=is_current_bool)
        
        if min_score:
            queryset = queryset.filter(overall_score__gte=float(min_score))
        
        if max_score:
            queryset = queryset.filter(overall_score__lte=float(max_score))
        
        if category:
            queryset = queryset.filter(resilience_category=category)
        
        if assessed_after:
            queryset = queryset.filter(assessment_date__gte=assessed_after)
        
        if assessed_before:
            queryset = queryset.filter(assessment_date__lte=assessed_before)
            
        return queryset
    
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_map_data(request):
    """API endpoint for consolidated map data including sensors, risk zones, and barangays"""
    municipality_id = request.GET.get('municipality_id', None)
    barangay_id = request.GET.get('barangay_id', None)
    province = request.GET.get('province', None)
    region_1 = request.GET.get('region_1', None)

        # Base querysets
    sensors_queryset = Sensor.objects.filter(active=True)
    zones_queryset = FloodRiskZone.objects.all()
    barangays_queryset = Barangay.objects.all()
    
    # Apply filters if provided
    if municipality_id:
        barangays_queryset = barangays_queryset.filter(municipality_id=municipality_id)
        # For sensors and zones, we need to filter based on geographical coordinates
        # In a real system with proper GIS, this would use spatial queries
        # For this system, we'll just filter sensors by municipality association
        sensors_queryset = sensors_queryset.filter(
            Q(municipality_id=municipality_id) | Q(municipality_id__isnull=True))
        
        # For risk zones, we'll rely on the front-end to display only relevant zones
        # But we could add logic here to filter zones by municipality bounds
        
    if barangay_id:
        barangays_queryset = barangays_queryset.filter(id=barangay_id)
        # Similarly, filter sensors by barangay association
        sensors_queryset = sensors_queryset.filter(
            Q(barangay_id=barangay_id) | Q(barangay_id__isnull=True))
    
    # Prepare sensor data with latest readings
    sensor_data = []
    for sensor in sensors_queryset:
        # Get the latest reading for this sensor
        latest_reading = SensorData.objects.filter(sensor=sensor).order_by('-timestamp').first()
        
        # Prepare the sensor info with coordinates and value
        sensor_info = {
            'id': sensor.id,
            'name': sensor.name,
            'type': sensor.sensor_type,
            'lat': sensor.latitude,
            'lng': sensor.longitude,
            'unit': sensor.unit,
            'value': latest_reading.value if latest_reading else None,
            'timestamp': latest_reading.timestamp if latest_reading else None,
            'municipality_id': sensor.municipality_id,
            'barangay_id': sensor.barangay_id
        }
        
        sensor_data.append(sensor_info)
    
    # Prepare risk zone data
    zone_data = []
    for zone in zones_queryset:
        zone_info = {
            'id': zone.id,
            'name': zone.name,
            'severity': zone.severity_level,
            'geojson': zone.geojson,
            'municipality_id': zone.municipality_id if hasattr(zone, 'municipality_id') else None,
            'barangay_id': zone.barangay_id if hasattr(zone, 'barangay_id') else None
        }
        
        zone_data.append(zone_info)
    
    # Prepare barangay data with flood risk levels
    barangay_data = []
    for barangay in barangays_queryset:
        # In a real system, this would be calculated based on sensor readings,
        # active alerts, and historical data for this specific barangay
        # For now, we'll use a simplified approach
        
        # Check if there are any active alerts for this barangay
        active_alerts = FloodAlert.objects.filter(
            active=True,
            affected_barangays=barangay
        ).order_by('-severity_level')
        
        # Determine severity based on the highest alert level
        severity = 0
        if active_alerts.exists():
            severity = active_alerts.first().severity_level
        
        # Add some basic severity for demonstration if no alerts
        # This would normally be based on real-time risk analysis
        if severity == 0:
            # Create a deterministic but varied severity based on barangay id
            # This ensures consistent display while testing different views
            severity = (barangay.id % 5) if barangay.id % 7 == 0 else 0
        
        barangay_info = {
            'id': barangay.id,
            'name': barangay.name,
            'municipality_id': barangay.municipality_id,
            'municipality_name': barangay.municipality.name,
            'population': barangay.population,
            'contact_person': barangay.contact_person,
            'contact_number': barangay.contact_number,
            'lat': barangay.latitude,
            'lng': barangay.longitude,
            'severity': severity  # 0-5 scale of flood risk
        }
        
        barangay_data.append(barangay_info)
    
    return Response({
        'sensors': sensor_data,
        'zones': zone_data,
        'barangays': barangay_data
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def apply_thresholds(request):
    """Apply threshold evaluation for locations and create/update targeted alerts.
    Behavior:
    - If barangay_id is provided: evaluate only that barangay.
    - Else if municipality_id is provided: evaluate all barangays in that municipality.
    - Else: evaluate all barangays.

    Optional body fields:
    - dry_run: bool (default False) — when true, do not persist alerts, only report actions.
    """
    try:
        municipality_id = request.data.get('municipality_id')
        barangay_id = request.data.get('barangay_id')
        # process_scope: 'barangay' | 'municipality' | 'all'
        process_scope = (request.data.get('process_scope') or '').strip().lower()
        dry_run = bool(request.data.get('dry_run', False))

        # Load thresholds once
        thresholds = {t.parameter: t for t in ThresholdSetting.objects.all()}
        if not thresholds:
            return Response({
                'success': False,
                'message': 'No threshold settings configured.',
                'processed': 0,
                'created': 0,
                'updated': 0,
                'results': []
            }, status=status.HTTP_200_OK)

        # Build barangay queryset according to scope
        b_qs = Barangay.objects.all()
        if process_scope == 'barangay' and barangay_id:
            b_qs = b_qs.filter(id=barangay_id)
        elif process_scope == 'municipality' and municipality_id:
            b_qs = b_qs.filter(municipality_id=municipality_id)
        elif process_scope == 'all':
            pass  # all barangays
        else:
            # Backward-compatible default behavior
            if barangay_id:
                b_qs = b_qs.filter(id=barangay_id)
            elif municipality_id:
                b_qs = b_qs.filter(municipality_id=municipality_id)

        def evaluate_severity(value, ts):
            if value is None or ts is None:
                return 0
            if value >= ts.catastrophic_threshold:
                return 5
            if value >= ts.emergency_threshold:
                return 4
            if value >= ts.warning_threshold:
                return 3
            if value >= ts.watch_threshold:
                return 2
            if value >= ts.advisory_threshold:
                return 1
            return 0

        sev_name = {1: 'Advisory', 2: 'Watch', 3: 'Warning', 4: 'Emergency', 5: 'Catastrophic'}

        total_processed = 0
        total_created = 0
        total_updated = 0
        results = []
        now = timezone.now()

        for b in b_qs.iterator():
            total_processed += 1
            exceeded_details = []
            highest_severity = 0

            # Check latest reading per configured parameter
            # Fallback order: barangay -> municipality -> global
            for param, ts in thresholds.items():
                latest = SensorData.objects.filter(
                    sensor__sensor_type=param,
                    sensor__barangay=b,
                ).order_by('-timestamp').first()

                if not latest and b.municipality_id:
                    latest = SensorData.objects.filter(
                        sensor__sensor_type=param,
                        sensor__municipality_id=b.municipality_id,
                        sensor__barangay__isnull=True,
                    ).order_by('-timestamp').first()

                if not latest:
                    latest = SensorData.objects.filter(
                        sensor__sensor_type=param,
                        sensor__municipality__isnull=True,
                        sensor__barangay__isnull=True,
                    ).order_by('-timestamp').first()

                if not latest:
                    continue

                sev = evaluate_severity(latest.value, ts)
                if sev > 0:
                    exceeded_details.append({
                        'parameter': param,
                        'value': latest.value,
                        'unit': ts.unit,
                        'severity': sev,
                        'severity_name': sev_name[sev],
                    })
                    highest_severity = max(highest_severity, sev)

            if highest_severity == 0:
                results.append({
                    'barangay_id': b.id,
                    'barangay_name': b.name,
                    'action': 'none',
                    'message': 'No thresholds exceeded',
                    'exceeded': []
                })
                continue

            # Compose title/description
            title_prefix = f"Automated Alert for {b.name}"
            details_lines = [
                f"- {d['parameter'].replace('_',' ').title()}: {d['value']} {d['unit']} (>= {d['severity_name']})"
                for d in sorted(exceeded_details, key=lambda x: (-x['severity'], x['parameter']))
            ]
            description = (
                f"Automated threshold evaluation at {now.strftime('%Y-%m-%d %H:%M:%S %Z')} for {b.name}.\n"
                f"Highest severity: {sev_name[highest_severity]}.\n"
                f"Exceeded parameters:\n" + "\n".join(details_lines)
            )

            existing = (
                FloodAlert.objects.filter(
                    active=True,
                    affected_barangays=b,
                    title__startswith=title_prefix,
                )
                .order_by('-issued_at')
                .first()
            )

            if dry_run:
                action = 'create' if not existing else (
                    'update' if highest_severity > existing.severity_level or existing.description != description else 'none'
                )
                results.append({
                    'barangay_id': b.id,
                    'barangay_name': b.name,
                    'action': action,
                    'highest_severity': highest_severity,
                    'exceeded': exceeded_details,
                })
                continue

            if existing:
                if highest_severity > existing.severity_level or existing.description != description:
                    existing.severity_level = max(existing.severity_level, highest_severity)
                    existing.description = description
                    existing.updated_at = timezone.now()
                    existing.save()
                    total_updated += 1
                    results.append({
                        'barangay_id': b.id,
                        'barangay_name': b.name,
                        'action': 'updated',
                        'highest_severity': existing.severity_level,
                        'exceeded': exceeded_details,
                    })
                else:
                    results.append({
                        'barangay_id': b.id,
                        'barangay_name': b.name,
                        'action': 'none',
                        'message': 'Existing alert adequate',
                        'highest_severity': existing.severity_level,
                        'exceeded': exceeded_details,
                    })
            else:
                alert = FloodAlert.objects.create(
                    title=f"{title_prefix}: {sev_name[highest_severity]}",
                    description=description,
                    severity_level=highest_severity,
                    active=True,
                )
                alert.affected_barangays.set([b])
                total_created += 1
                results.append({
                    'barangay_id': b.id,
                    'barangay_name': b.name,
                    'action': 'created',
                    'highest_severity': highest_severity,
                    'exceeded': exceeded_details,
                })

        return Response({
            'success': True,
            'processed': total_processed,
            'created': total_created,
            'updated': total_updated,
            'dry_run': dry_run,
            'results': results,
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception('Error applying thresholds: %s', e)
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def threshold_visualization(request):
    """API endpoint providing threshold visualization data per parameter
    - Returns configured thresholds (Advisory < Watch < Warning < Emergency < Catastrophic)
    - Computes current/latest values from sensors with optional location filters
    - Computes severity level/name and progress toward next threshold level
    Optional query params:
      - municipality_id: filter sensors by municipality
      - barangay_id: filter sensors by barangay
      - parameter: comma-separated list of parameters to include (e.g., rainfall,water_level)
    """
    municipality_id = request.GET.get('municipality_id', None)
    barangay_id = request.GET.get('barangay_id', None)
    param_filter = request.GET.get('parameter', None)

    # Build sensor filters based on location
    sensor_filters = {}
    if municipality_id:
        sensor_filters['sensor__municipality_id'] = municipality_id
    if barangay_id:
        sensor_filters['sensor__barangay_id'] = barangay_id

    # Filter which parameters to include
    threshold_qs = ThresholdSetting.objects.all()
    if param_filter:
        params = [p.strip() for p in param_filter.split(',') if p.strip()]
        threshold_qs = threshold_qs.filter(parameter__in=params)

    end_date = timezone.now()
    start_date_24h = end_date - timedelta(hours=24)

    def compute_severity(val, t):
        if val is None:
            return 0  # Normal/no alert
        if val >= t.catastrophic_threshold:
            return 5
        elif val >= t.emergency_threshold:
            return 4
        elif val >= t.warning_threshold:
            return 3
        elif val >= t.watch_threshold:
            return 2
        elif val >= t.advisory_threshold:
            return 1
        return 0

    def severity_name(level):
        if level == 0:
            return 'Normal'
        return get_severity_name(level)

    parameters = []

    for t in threshold_qs:
        base_filters = {
            'sensor__sensor_type': t.parameter,
        }
        base_filters.update(sensor_filters)

        # Latest reading with fallback chain (barangay -> municipality (barangay null) -> global)
        latest = SensorData.objects.filter(**base_filters).order_by('-timestamp').first()
        if not latest:
            # If barangay filter is present but no data, try municipality-only sensors
            if barangay_id and municipality_id:
                muni_only = {
                    'sensor__sensor_type': t.parameter,
                    'sensor__municipality_id': municipality_id,
                    'sensor__barangay__isnull': True,
                }
                latest = SensorData.objects.filter(**muni_only).order_by('-timestamp').first()
        if not latest:
            # Fallback to global sensors (no municipality/barangay)
            global_filters = {
                'sensor__sensor_type': t.parameter,
                'sensor__municipality__isnull': True,
                'sensor__barangay__isnull': True,
            }
            latest = SensorData.objects.filter(**global_filters).order_by('-timestamp').first()

        # 24h stats
        stats_filters = base_filters.copy()
        stats_filters.update({
            'timestamp__gte': start_date_24h,
            'timestamp__lte': end_date
        })
        stats = SensorData.objects.filter(**stats_filters).aggregate(
            avg=Avg('value'), max=Max('value'), count=Count('id')
        )

        latest_value = latest.value if latest else None
        latest_timestamp = latest.timestamp if latest else None
        sev_level = compute_severity(latest_value, t)
        sev_name = severity_name(sev_level)

        # Compute progress toward next threshold
        levels = [
            (1, 'Advisory', t.advisory_threshold),
            (2, 'Watch', t.watch_threshold),
            (3, 'Warning', t.warning_threshold),
            (4, 'Emergency', t.emergency_threshold),
            (5, 'Catastrophic', t.catastrophic_threshold),
        ]

        next_level_info = None
        if latest_value is None:
            # No data - progress unknown
            next_level_info = {
                'name': 'Advisory',
                'value': t.advisory_threshold,
                'delta': None,
                'progress_pct': None
            }
        else:
            if sev_level == 0:
                cur_base = 0.0
                nxt_val = t.advisory_threshold
                denom = max(nxt_val - cur_base, 1e-9)
                progress = max(0.0, min(100.0, (latest_value - cur_base) / denom * 100.0))
                next_level_info = {
                    'name': 'Advisory',
                    'value': nxt_val,
                    'delta': max(0.0, nxt_val - latest_value),
                    'progress_pct': round(progress, 2)
                }
            elif sev_level < 5:
                # Between current level threshold and next level threshold
                cur_idx = sev_level - 1  # 0-based index in levels list
                cur_val = levels[cur_idx][2]
                nxt_val = levels[cur_idx + 1][2]
                denom = max(nxt_val - cur_val, 1e-9)
                progress = max(0.0, min(100.0, (latest_value - cur_val) / denom * 100.0))
                next_level_info = {
                    'name': levels[cur_idx + 1][1],
                    'value': nxt_val,
                    'delta': max(0.0, nxt_val - latest_value),
                    'progress_pct': round(progress, 2)
                }
            else:
                # Already at highest level
                next_level_info = {
                    'name': None,
                    'value': None,
                    'delta': 0.0,
                    'progress_pct': 100.0
                }

        parameters.append({
            'parameter': t.parameter,
            'unit': t.unit,
            'thresholds': {
                'advisory': t.advisory_threshold,
                'watch': t.watch_threshold,
                'warning': t.warning_threshold,
                'emergency': t.emergency_threshold,
                'catastrophic': t.catastrophic_threshold,
            },
            'latest': {
                'value': latest_value,
                'timestamp': latest_timestamp
            },
            'stats_24h': {
                'avg': stats['avg'] if stats['avg'] is not None else 0,
                'max': stats['max'] if stats['max'] is not None else 0,
                'count': stats['count'] if stats['count'] is not None else 0,
            },
            'severity': {
                'level': sev_level,
                'name': sev_name,
            },
            'next_level': next_level_info
        })

    return Response({
        'filters': {
            'municipality_id': municipality_id,
            'barangay_id': barangay_id,
            'parameters': param_filter
        },
        'generated_at': timezone.now(),
        'data': parameters
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def historical_suggestion(request):
    """Suggest a decision (subject + level) based on Historical Comparison
    Query params:
      - type: rainfall | water_level (default: rainfall)
      - days: integer (default: 7)
      - municipality_id, barangay_id: optional filters
    Returns:
      - subject, level (text), level_numeric (0-5), reasons, metrics
    """
    data_type = request.GET.get('type', 'rainfall')
    try:
        days = int(request.GET.get('days', 7))
    except Exception:
        days = 7

    municipality_id = request.GET.get('municipality_id')
    barangay_id = request.GET.get('barangay_id')

    # Build filters
    sensor_filters = {'sensor__sensor_type': data_type}
    if municipality_id:
        sensor_filters['sensor__municipality_id'] = municipality_id
    if barangay_id:
        sensor_filters['sensor__barangay_id'] = barangay_id

    # Time windows
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    prev_start = start_date - timedelta(days=365)
    prev_end = end_date - timedelta(days=365)

    # Query current values
    current_qs = SensorData.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date,
        **sensor_filters
    )
    current_stats = current_qs.aggregate(avg=Avg('value'), max=Max('value'), count=Count('id'))

    # Query historical (same period last year)
    historical_qs = SensorData.objects.filter(
        timestamp__gte=prev_start,
        timestamp__lte=prev_end,
        **sensor_filters
    )
    historical_stats = historical_qs.aggregate(avg=Avg('value'), max=Max('value'), count=Count('id'))

    # Compute metrics
    current_avg = float(current_stats['avg']) if current_stats['avg'] is not None else 0.0
    current_max = float(current_stats['max']) if current_stats['max'] is not None else 0.0
    hist_avg = float(historical_stats['avg']) if historical_stats['avg'] is not None else (current_avg * 0.85)

    deviation_pct = 0.0
    if hist_avg > 0:
        deviation_pct = ((current_avg - hist_avg) / hist_avg) * 100.0

    reasons = []
    level_numeric = 0
    level_text = 'Normal'

    # Try to leverage configured thresholds when available for water_level
    threshold = None
    try:
        if data_type in ['water_level', 'rainfall']:
            threshold = ThresholdSetting.objects.filter(parameter=data_type).first()
    except Exception:
        threshold = None

    # Suggestion logic
    if data_type == 'rainfall':
        # Heuristics for rainfall
        if current_max >= 150 or deviation_pct >= 120:
            level_numeric = 4
            level_text = 'Emergency'
            reasons.append('Extreme rainfall spikes or far above historical norms')
        elif current_max >= 100 or deviation_pct >= 90:
            level_numeric = 3
            level_text = 'Warning'
            reasons.append('Very heavy rainfall and substantially above historical norms')
        elif current_avg >= 25 or deviation_pct >= 50:
            level_numeric = 2
            level_text = 'Watch'
            reasons.append('Sustained heavy rainfall relative to historical averages')
        elif current_avg >= 10 or deviation_pct >= 20:
            level_numeric = 1
            level_text = 'Advisory'
            reasons.append('Rainfall trending above normal levels')
        else:
            level_numeric = 0
            level_text = 'Normal'
            reasons.append('Rainfall near or below historical norms')

        if current_max > 0:
            reasons.append(f'Max 24h rainfall observed: {current_max:.1f} mm')
        reasons.append(f'Average vs historical: {current_avg:.1f} vs {hist_avg:.1f} mm ({deviation_pct:.0f}% change)')

    elif data_type == 'water_level':
        # Use configured thresholds if available
        if threshold:
            if current_max >= threshold.catastrophic_threshold:
                level_numeric = 5; level_text = 'Catastrophic'; reasons.append('Water level reached catastrophic threshold')
            elif current_max >= threshold.emergency_threshold:
                level_numeric = 4; level_text = 'Emergency'; reasons.append('Water level reached emergency threshold')
            elif current_max >= threshold.warning_threshold:
                level_numeric = 3; level_text = 'Warning'; reasons.append('Water level reached warning threshold')
            elif current_max >= threshold.watch_threshold:
                level_numeric = 2; level_text = 'Watch'; reasons.append('Water level reached watch threshold')
            elif current_max >= threshold.advisory_threshold:
                level_numeric = 1; level_text = 'Advisory'; reasons.append('Water level reached advisory threshold')
            else:
                level_numeric = 0; level_text = 'Normal'; reasons.append('Water level below advisory threshold')
        else:
            # Fallback heuristics if thresholds missing
            if current_max >= 1.8 or deviation_pct >= 80:
                level_numeric = 4; level_text = 'Emergency'; reasons.append('Water level far above typical levels')
            elif current_max >= 1.5 or deviation_pct >= 50:
                level_numeric = 3; level_text = 'Warning'; reasons.append('Water level significantly above typical levels')
            elif current_max >= 1.2 or deviation_pct >= 20:
                level_numeric = 2; level_text = 'Watch'; reasons.append('Water level trending higher than normal')
            elif current_max >= 1.0 or deviation_pct >= 10:
                level_numeric = 1; level_text = 'Advisory'; reasons.append('Water level slightly above normal')
            else:
                level_numeric = 0; level_text = 'Normal'; reasons.append('Water level within normal range')

        reasons.append(f'Max water level: {current_max:.2f} {threshold.unit if threshold else "m"}')
        reasons.append(f'Average vs historical: {current_avg:.2f} vs {hist_avg:.2f} ({deviation_pct:.0f}% change)')

    # Subject and action
    subject = f"Decision Support: {level_text} recommended for {data_type.replace('_',' ').title()}"
    suggested_action = {
        0: 'No action required. Continue monitoring.',
        1: 'Issue Advisory and inform monitoring teams.',
        2: 'Issue Watch and prepare response resources.',
        3: 'Issue Warning and activate response plans.',
        4: 'Issue Emergency alert and consider evacuations.',
        5: 'Issue Catastrophic alert. Immediate evacuation recommended.'
    }.get(level_numeric, 'Continue monitoring.')

    return Response({
        'type': data_type,
        'days': days,
        'subject': subject,
        'level': level_text,
        'level_numeric': level_numeric,
        'suggested_action': suggested_action,
        'reasons': reasons,
        'metrics': {
            'current_avg': round(current_avg, 2),
            'historical_avg': round(hist_avg, 2),
            'deviation_pct': round(deviation_pct, 1),
            'current_max': round(current_max, 2),
            'count': current_stats['count'] or 0
        },
        'time_window': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        }
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def threshold_visualization_parameter(request, parameter):
    """API endpoint providing threshold visualization for a single parameter
    Path param:
      - parameter: one of configured parameters (e.g., rainfall, water_level)
    Optional query params:
      - municipality_id
      - barangay_id
    """
    municipality_id = request.GET.get('municipality_id', None)
    barangay_id = request.GET.get('barangay_id', None)
    p = (parameter or '').strip().lower()

    try:
        t = ThresholdSetting.objects.get(parameter=p)
    except ThresholdSetting.DoesNotExist:
        available = list(ThresholdSetting.objects.values_list('parameter', flat=True))
        return Response({
            'error': f'Parameter "{parameter}" not found. Available parameters: {available}'
        }, status=status.HTTP_404_NOT_FOUND)

    # Build sensor filters based on location
    sensor_filters = {}
    if municipality_id:
        sensor_filters['sensor__municipality_id'] = municipality_id
    if barangay_id:
        sensor_filters['sensor__barangay_id'] = barangay_id

    end_date = timezone.now()
    start_date_24h = end_date - timedelta(hours=24)

    def compute_severity(val, t):
        if val is None:
            return 0
        if val >= t.catastrophic_threshold:
            return 5
        elif val >= t.emergency_threshold:
            return 4
        elif val >= t.warning_threshold:
            return 3
        elif val >= t.watch_threshold:
            return 2
        elif val >= t.advisory_threshold:
            return 1
        return 0

    # Query latest and 24h stats for this parameter
    base_filters = {
        'sensor__sensor_type': t.parameter,
    }
    base_filters.update(sensor_filters)

    latest = SensorData.objects.filter(**base_filters).order_by('-timestamp').first()

    stats_filters = base_filters.copy()
    stats_filters.update({
        'timestamp__gte': start_date_24h,
        'timestamp__lte': end_date
    })
    stats = SensorData.objects.filter(**stats_filters).aggregate(
        avg=Avg('value'), max=Max('value'), count=Count('id')
    )

    latest_value = latest.value if latest else None
    latest_timestamp = latest.timestamp if latest else None
    sev_level = compute_severity(latest_value, t)

    # Compute progress toward next threshold
    levels = [
        (1, 'Advisory', t.advisory_threshold),
        (2, 'Watch', t.watch_threshold),
        (3, 'Warning', t.warning_threshold),
        (4, 'Emergency', t.emergency_threshold),
        (5, 'Catastrophic', t.catastrophic_threshold),
    ]

    if latest_value is None:
        next_level_info = {
            'name': 'Advisory',
            'value': t.advisory_threshold,
            'delta': None,
            'progress_pct': None
        }
    elif sev_level == 0:
        cur_base = 0.0
        nxt_val = t.advisory_threshold
        denom = max(nxt_val - cur_base, 1e-9)
        progress = max(0.0, min(100.0, (latest_value - cur_base) / denom * 100.0))
        next_level_info = {
            'name': 'Advisory',
            'value': nxt_val,
            'delta': max(0.0, nxt_val - latest_value),
            'progress_pct': round(progress, 2)
        }
    elif sev_level < 5:
        cur_idx = sev_level - 1
        cur_val = levels[cur_idx][2]
        nxt_val = levels[cur_idx + 1][2]
        denom = max(nxt_val - cur_val, 1e-9)
        progress = max(0.0, min(100.0, (latest_value - cur_val) / denom * 100.0))
        next_level_info = {
            'name': levels[cur_idx + 1][1],
            'value': nxt_val,
            'delta': max(0.0, nxt_val - latest_value),
            'progress_pct': round(progress, 2)
        }
    else:
        next_level_info = {
            'name': None,
            'value': None,
            'delta': 0.0,
            'progress_pct': 100.0
        }

    data = {
        'parameter': t.parameter,
        'unit': t.unit,
        'thresholds': {
            'advisory': t.advisory_threshold,
            'watch': t.watch_threshold,
            'warning': t.warning_threshold,
            'emergency': t.emergency_threshold,
            'catastrophic': t.catastrophic_threshold,
        },
        'latest': {
            'value': latest_value,
            'timestamp': latest_timestamp
        },
        'stats_24h': {
            'avg': stats['avg'] if stats['avg'] is not None else 0,
            'max': stats['max'] if stats['max'] is not None else 0,
            'count': stats['count'] if stats['count'] is not None else 0,
        },
        'severity': {
            'level': sev_level,
            'name': 'Normal' if sev_level == 0 else get_severity_name(sev_level),
        },
        'next_level': next_level_info
    }

    return Response({
        'filters': {
            'municipality_id': municipality_id,
            'barangay_id': barangay_id
        },
        'generated_at': timezone.now(),
        'parameter': t.parameter,
        'data': data
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_all_barangays(request):
    """API endpoint for retrieving all barangays within a municipality without pagination"""
    municipality_id = request.GET.get('municipality_id', None)
    province = request.GET.get('province', None)
    region_1 = request.GET.get('region_1', None)

    try:
        barangays_queryset = Barangay.objects.all()
        sensors_queryset = Sensor.objects.all()
        municipalities = Municipality.objects.none()

        # Case 1: Specific municipality requested
        if municipality_id:
            municipalities = Municipality.objects.filter(id=municipality_id)
            if not municipalities.exists():
                return Response(
                    {'error': f'Municipality with ID {municipality_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            municipality_ids = [int(municipality_id)]
            barangays_queryset = barangays_queryset.filter(municipality_id=municipality_id)
            sensors_queryset = sensors_queryset.filter(municipality_id=municipality_id)

        # Case 2: Province filter without specific municipality
        elif province:
            municipalities = Municipality.objects.filter(province__iexact=province)
            if not municipalities.exists():
                return Response(
                    {'error': f'No municipalities found in province {province}'},
                    status=status.HTTP_404_NOT_FOUND
                )
            municipality_ids = [m.id for m in municipalities]
            barangays_queryset = barangays_queryset.filter(municipality_id__in=municipality_ids)
            sensors_queryset = sensors_queryset.filter(municipality_id__in=municipality_ids)

        # Case 3: Region 1 filter
        elif region_1 and region_1.lower() == 'true':
            municipalities = Municipality.objects.filter(province__in=REGION_1_PROVINCES)
            if not municipalities.exists():
                return Response(
                    {'error': 'No municipalities found in Region 1'},
                    status=status.HTTP_404_NOT_FOUND
                )
            municipality_ids = [m.id for m in municipalities]
            barangays_queryset = barangays_queryset.filter(municipality_id__in=municipality_ids)
            sensors_queryset = sensors_queryset.filter(municipality_id__in=municipality_ids)

        else:
            # If no filter is provided, return all barangays
            municipalities = Municipality.objects.all()
            municipality_ids = [m.id for m in municipalities]

        # Get all barangays for these municipalities
        barangays = barangays_queryset

        # Prepare the barangay data
        barangay_data = []
        for barangay in barangays:
            municipality = next((m for m in municipalities if m.id == barangay.municipality_id), None)
            if municipality:
                barangay_info = {
                    'id': barangay.id,
                    'name': barangay.name,
                    'municipality_id': barangay.municipality_id,
                    'municipality_name': municipality.name,
                    'province': municipality.province,
                    'population': barangay.population,
                    'contact_person': barangay.contact_person,
                    'contact_number': barangay.contact_number,
                    'latitude': barangay.latitude,
                    'longitude': barangay.longitude,
                }
                barangay_data.append(barangay_info)

        # Sort alphabetically by name for consistent display
        barangay_data.sort(key=lambda x: x['name'])

        # Return data with region context
        return Response({
            'region': 'Region 1 (Ilocos Region)',
            'provinces': REGION_1_PROVINCES,
            'municipalities': [{
                'id': m.id,
                'name': m.name,
                'province': m.province
            } for m in municipalities],
            'barangays': barangay_data,
            'count': len(barangay_data)
        })

    except Municipality.DoesNotExist:
        return Response(
            {'error': f'Municipality with ID {municipality_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error retrieving barangays: {str(e)}")
        return Response(
            {'error': 'An error occurred while retrieving barangay data'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

from rest_framework import viewsets
from .serializers import BarangaySerializer

class BarangayViewSet(viewsets.ModelViewSet):
    queryset = Barangay.objects.all()
    serializer_class = BarangaySerializer
