import os
import django
import random
import json
from datetime import datetime, timedelta

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flood_monitoring.settings')
django.setup()

# Import models
from django.contrib.auth.models import User
from core.models import (
    Sensor, SensorData, Barangay, FloodRiskZone, 
    FloodAlert, ThresholdSetting, NotificationLog, EmergencyContact
)
from django.utils import timezone

# Function to create test data
def create_test_data():
    print("Creating test data for Flood Monitoring System...")
    
    # Create threshold settings
    print("Creating threshold settings...")
    thresholds = {
        'rainfall': {
            'advisory': 5.0,
            'watch': 10.0,
            'warning': 15.0,
            'emergency': 20.0,
            'catastrophic': 30.0,
            'unit': 'mm/hr'
        },
        'water_level': {
            'advisory': 1.0,
            'watch': 2.0,
            'warning': 3.0,
            'emergency': 4.0,
            'catastrophic': 5.0,
            'unit': 'm'
        },
        'temperature': {
            'advisory': 30.0,
            'watch': 32.0,
            'warning': 35.0,
            'emergency': 38.0,
            'catastrophic': 40.0,
            'unit': '°C'
        },
        'humidity': {
            'advisory': 70.0,
            'watch': 80.0,
            'warning': 85.0,
            'emergency': 90.0,
            'catastrophic': 95.0,
            'unit': '%'
        },
        'wind_speed': {
            'advisory': 30.0,
            'watch': 45.0,
            'warning': 60.0,
            'emergency': 90.0,
            'catastrophic': 120.0,
            'unit': 'km/h'
        }
    }
    
    # Get first admin user
    admin_user = User.objects.filter(is_superuser=True).first()
    
    for parameter, values in thresholds.items():
        ThresholdSetting.objects.get_or_create(
            parameter=parameter,
            defaults={
                'advisory_threshold': values['advisory'],
                'watch_threshold': values['watch'],
                'warning_threshold': values['warning'],
                'emergency_threshold': values['emergency'],
                'catastrophic_threshold': values['catastrophic'],
                'unit': values['unit'],
                'last_updated_by': admin_user
            }
        )
    
    # Create barangays in Vical, Santa Lucia, Ilocos Sur area
    print("Creating barangays...")
    barangays_data = [
        {
            'name': 'Vical',
            'population': 4520,
            'area_sqkm': 3.2,
            'latitude': 17.135678,
            'longitude': 120.437203,
            'contact_person': 'Maria Santos',
            'contact_number': '+63 918 123 4567'
        },
        {
            'name': 'Barangay Santa Lucia',
            'population': 6250,
            'area_sqkm': 2.8,
            'latitude': 17.138520,
            'longitude': 120.435678,
            'contact_person': 'Juan Reyes',
            'contact_number': '+63 917 234 5678'
        },
        {
            'name': 'Barangay Nagsayaoan',
            'population': 3800,
            'area_sqkm': 2.1,
            'latitude': 17.132456,
            'longitude': 120.432987,
            'contact_person': 'Roberto Lim',
            'contact_number': '+63 919 345 6789'
        },
        {
            'name': 'Cabaroan',
            'population': 5100,
            'area_sqkm': 2.5,
            'latitude': 17.141032,
            'longitude': 120.440215,
            'contact_person': 'Elena Gonzales',
            'contact_number': '+63 920 456 7890'
        },
        {
            'name': 'San Juan',
            'population': 4300,
            'area_sqkm': 2.2,
            'latitude': 17.129876,
            'longitude': 120.428765,
            'contact_person': 'Carlos Tan',
            'contact_number': '+63 921 567 8901'
        }
    ]
    
    created_barangays = []
    for data in barangays_data:
        barangay, created = Barangay.objects.get_or_create(
            name=data['name'],
            defaults={
                'population': data['population'],
                'area_sqkm': data['area_sqkm'],
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'contact_person': data['contact_person'],
                'contact_number': data['contact_number']
            }
        )
        created_barangays.append(barangay)
    
    # Create flood risk zones in Vical, Santa Lucia, Ilocos Sur area
    print("Creating flood risk zones...")
    zone_data = [
        {
            'name': 'Vical River Basin',
            'severity_level': 4,
            'description': 'Low-lying area near the river, prone to severe flooding during monsoon season',
            'geojson': json.dumps({
                'type': 'Polygon',
                'coordinates': [
                    [
                        [120.435, 17.134],
                        [120.438, 17.136],
                        [120.439, 17.138],
                        [120.436, 17.139],
                        [120.435, 17.134]
                    ]
                ]
            })
        },
        {
            'name': 'Santa Lucia Central',
            'severity_level': 3,
            'description': 'Urban area with poor drainage system, vulnerable to flash floods',
            'geojson': json.dumps({
                'type': 'Polygon',
                'coordinates': [
                    [
                        [120.433, 17.137],
                        [120.436, 17.139],
                        [120.438, 17.137],
                        [120.435, 17.135],
                        [120.433, 17.137]
                    ]
                ]
            })
        },
        {
            'name': 'Eastern Hillside',
            'severity_level': 2,
            'description': 'Sloped area prone to landslides during heavy rainfall periods',
            'geojson': json.dumps({
                'type': 'Polygon',
                'coordinates': [
                    [
                        [120.441, 17.137],
                        [120.444, 17.139],
                        [120.443, 17.142],
                        [120.440, 17.140],
                        [120.441, 17.137]
                    ]
                ]
            })
        }
    ]
    
    for data in zone_data:
        FloodRiskZone.objects.get_or_create(
            name=data['name'],
            defaults={
                'severity_level': data['severity_level'],
                'description': data['description'],
                'geojson': data['geojson']
            }
        )
    
    # Create sensors in Vical, Santa Lucia, Ilocos Sur area
    print("Creating sensors...")
    sensors_data = [
        {
            'name': 'Vical Rain Gauge',
            'sensor_type': 'rainfall',
            'latitude': 17.135678,
            'longitude': 120.437203,
        },
        {
            'name': 'Santa Lucia Rain Monitor',
            'sensor_type': 'rainfall',
            'latitude': 17.138520,
            'longitude': 120.435678,
        },
        {
            'name': 'Vical River Level Monitor',
            'sensor_type': 'water_level',
            'latitude': 17.136789,
            'longitude': 120.438901,
        },
        {
            'name': 'Bridge Water Level Sensor',
            'sensor_type': 'water_level',
            'latitude': 17.134562,
            'longitude': 120.436789,
        },
        {
            'name': 'Santa Lucia Weather Station',
            'sensor_type': 'temperature',
            'latitude': 17.137895,
            'longitude': 120.434567,
        },
        {
            'name': 'Vical Environmental Monitor',
            'sensor_type': 'humidity',
            'latitude': 17.135789,
            'longitude': 120.436543,
        },
        {
            'name': 'Municipal Weather Station',
            'sensor_type': 'wind_speed',
            'latitude': 17.139012,
            'longitude': 120.439876,
        }
    ]
    
    created_sensors = []
    for data in sensors_data:
        sensor, created = Sensor.objects.get_or_create(
            name=data['name'],
            defaults={
                'sensor_type': data['sensor_type'],
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'active': True
            }
        )
        created_sensors.append(sensor)
    
    # Generate sensor data for the past week
    print("Generating historical sensor data...")
    sensor_value_ranges = {
        'rainfall': (0, 35),       # 0-35 mm/hr
        'water_level': (0.5, 6),   # 0.5-6 meters
        'temperature': (25, 42),    # 25-42 °C
        'humidity': (50, 98),       # 50-98 %
        'wind_speed': (0, 130)      # 0-130 km/h
    }
    
    # Define a realistic data pattern (e.g., more rain at night)
    def get_realistic_value(sensor_type, hour, day_index):
        base_range = sensor_value_ranges[sensor_type]
        value_range = (base_range[1] - base_range[0])
        
        # Pattern factors (0-1 scale)
        if sensor_type == 'rainfall':
            # More rain in the afternoon and evenings, some days are rainier
            time_factor = 0.2 + (0.8 * (1 if 14 <= hour <= 22 else 0.3))
            day_factor = 0.3 + (0.7 * (day_index % 3 == 0))  # Every 3rd day is rainier
            randomness = random.random() * 0.5  # Lower randomness for more pattern
            
            # Rain often comes in bursts
            if random.random() > 0.7:  # 30% chance of heavy rain
                heavy_rain_factor = random.uniform(0.6, 1.0)
            else:
                heavy_rain_factor = random.uniform(0, 0.3)
                
            factor = time_factor * day_factor * (randomness + heavy_rain_factor) * 0.5
            
        elif sensor_type == 'water_level':
            # Water level rises after rainfall with some delay
            # Higher at night when more rain has accumulated
            time_factor = 0.3 + (0.7 * (1 if 16 <= hour <= 23 else 0.2))
            day_factor = 0.4 + (0.6 * (day_index % 3 == 1))  # Peak day after rain
            randomness = random.random() * 0.3
            factor = time_factor * day_factor * (0.7 + randomness)
            
        elif sensor_type == 'temperature':
            # Higher during midday, lower at night
            time_factor = 0.3 + (0.7 * (1 if 10 <= hour <= 16 else 0.5 if 8 <= hour <= 18 else 0.2))
            randomness = random.random() * 0.2
            factor = time_factor * (0.8 + randomness)
            
        elif sensor_type == 'humidity':
            # Higher at night and early morning, lower midday
            time_factor = 0.5 + (0.5 * (1 if (hour < 8 or hour > 18) else 0.3))
            # Higher on rainy days
            day_factor = 0.7 + (0.3 * (day_index % 3 == 0))  # Matches rainy days
            randomness = random.random() * 0.2
            factor = time_factor * day_factor * (0.8 + randomness)
            
        elif sensor_type == 'wind_speed':
            # Can be stronger in afternoons and during storms
            time_factor = 0.2 + (0.8 * (1 if 12 <= hour <= 18 else 0.4))
            # Stronger on rainy days
            day_factor = 0.4 + (0.6 * (day_index % 3 == 0))  # Matches rainy days
            # Wind comes in gusts
            gust_factor = 1.0 if random.random() > 0.8 else 0.6
            randomness = random.random() * 0.3
            factor = time_factor * day_factor * gust_factor * (0.7 + randomness)
            
        # Calculate value based on range and factor
        value = base_range[0] + (value_range * factor)
        return round(value, 2)
    
    # Generate data for the past 2 days in 3-hour intervals
    end_time = timezone.now()
    start_time = end_time - timedelta(days=2)
    current_time = start_time
    
    # Track which days to create alerts for
    alert_days = [3, 6]  # Day indexes (0-based) to create alerts for
    
    # Track peak values for alert creation
    peak_rainfall = 0
    peak_water_level = 0
    peak_day_index = -1
    
    day_index = 0
    day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    
    sensor_data_batch = []
    batch_size = 100
    
    while current_time <= end_time:
        # Check if we're on a new day
        if current_time.date() != day_start.date():
            day_index += 1
            day_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            # Reset peak values for new day
            peak_rainfall = 0
            peak_water_level = 0
        
        for sensor in created_sensors:
            hour = current_time.hour
            value = get_realistic_value(sensor.sensor_type, hour, day_index)
            
            # Track peak values for alerts
            if sensor.sensor_type == 'rainfall' and value > peak_rainfall:
                peak_rainfall = value
                peak_day_index = day_index
            elif sensor.sensor_type == 'water_level' and value > peak_water_level:
                peak_water_level = value
            
            # Add to batch
            sensor_data_batch.append(SensorData(
                sensor=sensor,
                value=value,
                timestamp=current_time
            ))
            
            # Insert batch if it reaches the batch size
            if len(sensor_data_batch) >= batch_size:
                SensorData.objects.bulk_create(sensor_data_batch)
                sensor_data_batch = []
        
        current_time += timedelta(hours=3)
    
    # Insert any remaining sensor data
    if sensor_data_batch:
        SensorData.objects.bulk_create(sensor_data_batch)
    
    # Create emergency contacts
    print("Creating emergency contacts...")
    contact_data = [
        {
            'name': 'Emergency Response Team',
            'role': 'First Responders',
            'phone': '+63 919 111 2222',
            'email': 'response@floodmonitor.example.com',
            'barangay': None  # Central team, not barangay-specific
        },
        {
            'name': 'Municipal Disaster Office',
            'role': 'Coordination Center',
            'phone': '+63 919 333 4444',
            'email': 'disaster@municipality.example.com',
            'barangay': None
        }
    ]
    
    # Add barangay-specific contacts
    for barangay in created_barangays:
        contact_data.append({
            'name': f'{barangay.contact_person}',
            'role': 'Barangay Captain',
            'phone': barangay.contact_number,
            'email': f'captain@{barangay.name.lower().replace(" ", "")}.example.com',
            'barangay': barangay
        })
    
    for data in contact_data:
        EmergencyContact.objects.get_or_create(
            name=data['name'],
            role=data['role'],
            defaults={
                'phone': data['phone'],
                'email': data['email'],
                'barangay': data['barangay']
            }
        )
    
    # Create flood alerts
    print("Creating flood alerts...")
    # Create one active alert and one historical alert
    alert_data = [
        {
            'title': 'Emergency Flood Warning: Rising Water Levels in Vical River',
            'description': 'Water levels in the Vical River are approaching critical thresholds due to continuous rainfall. Evacuation may be necessary in low-lying areas of Vical and Nagsayaoan.',
            'severity_level': 4,  # Emergency
            'active': True,
            'predicted_flood_time': timezone.now() + timedelta(hours=3),
            'affected_barangays': [created_barangays[0], created_barangays[2]],  # Vical, Barangay Nagsayaoan
        },
        {
            'title': 'Flood Advisory: Heavy Rainfall Expected in Santa Lucia',
            'description': 'Continuous heavy rainfall expected over the next 12 hours in Santa Lucia and surrounding areas. Please monitor water levels and prepare for possible evacuation.',
            'severity_level': 2,  # Watch
            'active': True,
            'predicted_flood_time': timezone.now() + timedelta(hours=12),
            'affected_barangays': [created_barangays[1], created_barangays[3], created_barangays[4]],  # Barangay Santa Lucia, Cabaroan, San Juan
        },
        {
            'title': 'Previous Flood Event in Vical Area (Archived)',
            'description': 'Previous flash flood event in Vical and San Juan areas has now receded. Cleanup operations ongoing.',
            'severity_level': 3,  # Warning
            'active': False,
            'predicted_flood_time': timezone.now() - timedelta(days=3),
            'affected_barangays': [created_barangays[0], created_barangays[4]],  # Vical, San Juan
        }
    ]
    
    for data in alert_data:
        alert = FloodAlert.objects.create(
            title=data['title'],
            description=data['description'],
            severity_level=data['severity_level'],
            active=data['active'],
            predicted_flood_time=data['predicted_flood_time'],
            issued_by=admin_user
        )
        alert.affected_barangays.set(data['affected_barangays'])
        
        # Create notification logs for this alert
        if data['active']:
            for i, barangay in enumerate(data['affected_barangays']):
                # Create SMS notification
                NotificationLog.objects.create(
                    alert=alert,
                    notification_type='sms',
                    recipient=f"+63 9{17+i} {barangay.name.replace(' ', '')}1234",
                    status='delivered' if i % 2 == 0 else 'sent',
                )
                
                # Create Email notification
                NotificationLog.objects.create(
                    alert=alert,
                    notification_type='email',
                    recipient=f"residents@{barangay.name.lower().replace(' ', '')}.example.com",
                    status='sent',
                )
                
                # Create App notification
                NotificationLog.objects.create(
                    alert=alert,
                    notification_type='app',
                    recipient='All Users',
                    status='delivered',
                )
    
    print("Test data creation complete!")

if __name__ == "__main__":
    create_test_data()
