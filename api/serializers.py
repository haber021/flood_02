from rest_framework import serializers
from core.models import (
    Sensor, SensorData, Municipality, Barangay, FloodRiskZone, 
    FloodAlert, ThresholdSetting, NotificationLog, EmergencyContact,
    ResilienceScore
)

class SensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = '__all__'

class SensorDataSerializer(serializers.ModelSerializer):
    sensor_name = serializers.ReadOnlyField(source='sensor.name')
    sensor_type = serializers.ReadOnlyField(source='sensor.sensor_type')
    
    class Meta:
        model = SensorData
        fields = ['id', 'sensor', 'sensor_name', 'sensor_type', 'value', 'timestamp']

class MunicipalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipality
        fields = '__all__'

class BarangaySerializer(serializers.ModelSerializer):
    municipality_name = serializers.ReadOnlyField(source='municipality.name')
    
    class Meta:
        model = Barangay
        fields = '__all__'

class FloodRiskZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = FloodRiskZone
        fields = '__all__'

class FloodAlertSerializer(serializers.ModelSerializer):
    issued_by_username = serializers.ReadOnlyField(source='issued_by.username')
    
    class Meta:
        model = FloodAlert
        fields = ['id', 'title', 'description', 'severity_level', 'active', 
                  'predicted_flood_time', 'issued_at', 'updated_at', 
                  'affected_barangays', 'issued_by', 'issued_by_username']
        read_only_fields = ['issued_at', 'updated_at', 'issued_by']

class ThresholdSettingSerializer(serializers.ModelSerializer):
    last_updated_by_username = serializers.ReadOnlyField(source='last_updated_by.username')
    
    class Meta:
        model = ThresholdSetting
        fields = ['id', 'parameter', 'advisory_threshold', 'watch_threshold', 
                  'warning_threshold', 'emergency_threshold', 'catastrophic_threshold', 
                  'unit', 'created_at', 'updated_at', 'last_updated_by', 
                  'last_updated_by_username']
        read_only_fields = ['created_at', 'updated_at', 'last_updated_by']    
    def validate(self, data):
        # Use incoming data first, fall back to instance values for partial updates
        a = data.get('advisory_threshold', getattr(self.instance, 'advisory_threshold', None))
        w = data.get('watch_threshold', getattr(self.instance, 'watch_threshold', None))
        wn = data.get('warning_threshold', getattr(self.instance, 'warning_threshold', None))
        e = data.get('emergency_threshold', getattr(self.instance, 'emergency_threshold', None))
        c = data.get('catastrophic_threshold', getattr(self.instance, 'catastrophic_threshold', None))
        msg = 'Thresholds must be strictly increasing: Advisory < Watch < Warning < Emergency < Catastrophic.'
        if None not in (a, w, wn, e, c):
            if not (a < w < wn < e < c):
                raise serializers.ValidationError({
                    'advisory_threshold': msg,
                    'watch_threshold': msg,
                    'warning_threshold': msg,
                    'emergency_threshold': msg,
                    'catastrophic_threshold': msg,
                })
        return data

class NotificationLogSerializer(serializers.ModelSerializer):
    alert_title = serializers.ReadOnlyField(source='alert.title')
    
    class Meta:
        model = NotificationLog
        fields = ['id', 'alert', 'alert_title', 'notification_type', 
                  'recipient', 'sent_at', 'status']

class EmergencyContactSerializer(serializers.ModelSerializer):
    barangay_name = serializers.ReadOnlyField(source='barangay.name')
    
    class Meta:
        model = EmergencyContact
        fields = ['id', 'name', 'role', 'phone', 'email', 'barangay', 'barangay_name']

class ResilienceScoreSerializer(serializers.ModelSerializer):
    municipality_name = serializers.ReadOnlyField(source='municipality.name', default=None)
    barangay_name = serializers.ReadOnlyField(source='barangay.name', default=None)
    assessed_by_username = serializers.ReadOnlyField(source='assessed_by.username', default=None)
    resilience_category_display = serializers.CharField(source='get_resilience_category_display', read_only=True)
    
    class Meta:
        model = ResilienceScore
        fields = [
            'id', 'municipality', 'municipality_name', 'barangay', 'barangay_name',
            'infrastructure_score', 'social_capital_score', 'institutional_score',
            'economic_score', 'environmental_score', 'overall_score',
            'resilience_category', 'resilience_category_display', 'recommendations',
            'assessed_by', 'assessed_by_username', 'assessment_date', 'valid_until',
            'methodology', 'notes', 'is_current', 'created_at', 'updated_at'
        ]
        read_only_fields = ['overall_score', 'resilience_category', 'created_at', 'updated_at']
