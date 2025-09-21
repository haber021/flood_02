import re
import json
import requests
import traceback
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Sensor, SensorData
import statistics
from datetime import timedelta

class Command(BaseCommand):
    help = 'Fetch highly accurate real-time weather data from multiple reliable sources'
    
    # API configuration with fallback priority
    WEATHER_SOURCES = [
        {
            'name': 'Open-Meteo (Multi-Model)',
            'url': 'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,relative_humidity_2m,precipitation,rain,wind_speed_10m,wind_direction_10m&hourly=temperature_2m,relative_humidity_2m,precipitation,rain,wind_speed_10m&timeformat=unixtime&timezone=auto&models=best_match',
            'timeout': 10,
            'parser': lambda data: data.get('current', {})
        },
        {
            'name': 'WeatherAPI (Premium)',
            'url': 'http://api.weatherapi.com/v1/current.json?key=YOUR_WEATHERAPI_KEY&q={lat},{lng}',
            'timeout': 8,
            'parser': lambda data: data.get('current', {})
        },
        {
            'name': 'VisualCrossing (Historical)',
            'url': 'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timelinelocation/{lat},{lng}?unitGroup=metric&include=current&key=YOUR_VC_KEY&contentType=json',
            'timeout': 8,
            'parser': lambda data: data.get('currentConditions', {})
        },
        {
            'name': 'AccuWeather (LocationKey)',
            'url': 'http://dataservice.accuweather.com/currentconditions/v1/{location_key}?apikey=YOUR_ACCUWEATHER_KEY&details=true',
            'timeout': 8,
            'requires_location_key': True,
            'parser': lambda data: data[0] if data else {}
        }
    ]
    
    # Sensor-specific adjustments
    SENSOR_ADJUSTMENTS = {
        'temperature': {
            'range': (-20, 50),  # Reasonable temperature range in °C
            'precision': 1,
            'correction_factors': {
                'urban': 1.02,  # Urban heat island effect
                'coastal': 0.98,
                'mountain': 0.95
            }
        },
        'rainfall': {
            'range': (0, 100),  # Max 100mm/hr
            'precision': 2,
            'correction_factors': {
                'valley': 1.1,
                'hilltop': 0.9
            }
        },
        'water_level': {
            'range': (0, 10),  # Meters
            'precision': 2,
            'base_level': 0.5
        },
        'humidity': {
            'range': (0, 100),  # Percentage
            'precision': 1
        },
        'wind_speed': {
            'range': (0, 150),  # km/h
            'precision': 1,
            'height_adjustment': {
                '10m': 1.0,
                '5m': 0.8,
                '2m': 0.6
            }
        }
    }
    
    def handle(self, *args, **options):
        self.stdout.write("Fetching highly accurate real-time weather data...")
        
        # Get recent data for comparison and validation
        recent_data = self.get_recent_sensor_data()
        
        # Update all sensor types with enhanced accuracy
        self.update_temperature_data(recent_data)
        self.update_rainfall_data(recent_data)
        self.update_water_level_data(recent_data)
        self.update_humidity_data(recent_data)
        self.update_wind_data(recent_data)
        
        self.stdout.write(self.style.SUCCESS("Successfully updated all sensor data with high-accuracy values"))

    def get_recent_sensor_data(self):
        """Get recent sensor data for validation and comparison"""
        recent_data = {}
        time_threshold = timezone.now() - timedelta(hours=6)
        
        for sensor_type in self.SENSOR_ADJUSTMENTS.keys():
            sensors = Sensor.objects.filter(sensor_type=sensor_type, active=True)
            for sensor in sensors:
                recent_readings = SensorData.objects.filter(
                    sensor=sensor,
                    timestamp__gte=time_threshold
                ).order_by('-timestamp')[:10]
                
                if recent_readings:
                    values = [r.value for r in recent_readings]
                    recent_data[sensor.id] = {
                        'values': values,
                        'avg': statistics.mean(values),
                        'stdev': statistics.stdev(values) if len(values) > 1 else 0
                    }
        
        return recent_data

    def fetch_weather_for_location(self, location_name, lat, lng, sensor_type=None):
        """Fetch highly accurate weather data using multiple sources and consensus"""
        self.stdout.write(f"\nFetching high-accuracy data for {location_name} ({lat}, {lng})")
        
        results = []
        source_errors = []
        
        for source in self.WEATHER_SOURCES:
            try:
                # Skip sources that require location keys if we don't have them
                if source.get('requires_location_key'):
                    continue
                
                url = source['url'].format(lat=lat, lng=lng)
                headers = {
                    'User-Agent': 'FloodMonitoringSystem/3.0 (HighAccuracy)',
                    'Accept': 'application/json'
                }
                
                response = requests.get(url, headers=headers, timeout=source['timeout'])
                response.raise_for_status()
                
                data = response.json()
                parsed = source['parser'](data)
                
                if parsed:
                    standardized = self.standardize_weather_data(parsed, source['name'])
                    if standardized:
                        results.append(standardized)
                        self.stdout.write(f"  ✓ {source['name']}: {standardized}")
                    else:
                        source_errors.append(f"{source['name']}: Invalid data format")
                else:
                    source_errors.append(f"{source['name']}: No usable data")
            
            except Exception as e:
                source_errors.append(f"{source['name']}: {str(e)}")
        
        # If we have multiple results, use consensus
        if results:
            if len(results) > 1:
                # For numerical values, use median to reduce outlier impact
                consensus = {}
                for key in results[0].keys():
                    values = [r[key] for r in results if key in r]
                    if values:
                        try:
                            consensus[key] = round(statistics.median(values), 
                                                 self.SENSOR_ADJUSTMENTS.get(sensor_type, {}).get('precision', 1))
                        except statistics.StatisticsError:
                            consensus[key] = values[0]
                
                self.stdout.write(f"Consensus data from {len(results)} sources: {consensus}")
                return consensus
            else:
                return results[0]
        
        self.stdout.write(self.style.WARNING(f"All sources failed: {', '.join(source_errors)}"))
        return None
    
    def standardize_weather_data(self, raw_data, source_name):
        """Convert different API responses to standardized format"""
        standardized = {}
        
        # Temperature (convert to °C)
        if 'temperature_2m' in raw_data:  # Open-Meteo
            standardized['temperature'] = float(raw_data['temperature_2m'])
        elif 'temp_c' in raw_data:  # WeatherAPI
            standardized['temperature'] = float(raw_data['temp_c'])
        elif 'temp' in raw_data:  # VisualCrossing
            standardized['temperature'] = float(raw_data['temp'])
        elif 'Temperature' in raw_data:  # AccuWeather
            standardized['temperature'] = float(raw_data['Temperature']['Metric']['Value'])
        
        # Precipitation (convert to mm)
        if 'precipitation' in raw_data:  # Open-Meteo
            standardized['precipitation'] = float(raw_data['precipitation'] or 0)
        elif 'rain' in raw_data:  # Open-Meteo alternative
            standardized['precipitation'] = float(raw_data['rain'] or 0)
        elif 'precip_mm' in raw_data:  # WeatherAPI
            standardized['precipitation'] = float(raw_data['precip_mm'])
        elif 'precip' in raw_data:  # VisualCrossing
            standardized['precipitation'] = float(raw_data['precip'] or 0)
        elif 'PrecipitationSummary' in raw_data:  # AccuWeather
            standardized['precipitation'] = float(raw_data['PrecipitationSummary']['PastHour']['Metric']['Value'])
        
        # Humidity (convert to %)
        if 'relative_humidity_2m' in raw_data:  # Open-Meteo
            standardized['humidity'] = float(raw_data['relative_humidity_2m'])
        elif 'humidity' in raw_data:  # WeatherAPI, VisualCrossing
            standardized['humidity'] = float(raw_data['humidity'])
        elif 'RelativeHumidity' in raw_data:  # AccuWeather
            standardized['humidity'] = float(raw_data['RelativeHumidity'])
        
        # Wind Speed (convert to km/h)
        if 'wind_speed_10m' in raw_data:  # Open-Meteo
            standardized['wind_speed'] = float(raw_data['wind_speed_10m'])
        elif 'wind_kph' in raw_data:  # WeatherAPI
            standardized['wind_speed'] = float(raw_data['wind_kph'])
        elif 'windspeed' in raw_data:  # VisualCrossing
            standardized['wind_speed'] = float(raw_data['windspeed'])
        elif 'Wind' in raw_data and 'Speed' in raw_data['Wind']:  # AccuWeather
            standardized['wind_speed'] = float(raw_data['Wind']['Speed']['Metric']['Value'])
        
        return standardized
    
    def apply_sensor_corrections(self, value, sensor, sensor_type):
        """Apply location-specific corrections to sensor data"""
        adjustments = self.SENSOR_ADJUSTMENTS.get(sensor_type, {})
        
        # Apply general corrections
        if 'correction_factors' in adjustments:
            location_type = self.detect_location_type(sensor)
            correction = adjustments['correction_factors'].get(location_type, 1.0)
            value *= correction
        
        # Apply wind speed height adjustment
        if sensor_type == 'wind_speed' and 'height_adjustment' in adjustments:
            height = self.get_sensor_height(sensor)
            adjustment = adjustments['height_adjustment'].get(height, 1.0)
            value *= adjustment
        
        # Round to appropriate precision
        precision = adjustments.get('precision', 1)
        return round(value, precision)
    
    def detect_location_type(self, sensor):
        """Determine location type for sensor-specific adjustments"""
        name = sensor.name.lower()
        if 'urban' in name or 'city' in name:
            return 'urban'
        elif 'coastal' in name or 'beach' in name:
            return 'coastal'
        elif 'mountain' in name or 'hill' in name:
            return 'mountain'
        elif 'valley' in name:
            return 'valley'
        return 'default'
    
    def get_sensor_height(self, sensor):
        """Extract sensor height from description or name"""
        # Try to extract height from name/description
        match = re.search(r'(\d+)m', sensor.description or '')
        if match:
            height = match.group(1)
            if int(height) >= 10:
                return '10m'
            elif int(height) >= 5:
                return '5m'
            else:
                return '2m'
        return '10m'  # Default assumption
    
    def validate_sensor_data(self, value, sensor_type, sensor_id, recent_data):
        """Validate sensor data against expected ranges and recent trends"""
        adjustments = self.SENSOR_ADJUSTMENTS.get(sensor_type, {})
        min_val, max_val = adjustments.get('range', (None, None))
        
        # Basic range check
        if min_val is not None and value < min_val:
            return False, f"Value {value} below minimum {min_val}"
        if max_val is not None and value > max_val:
            return False, f"Value {value} above maximum {max_val}"
        
        # Compare with recent data if available
        if sensor_id in recent_data:
            recent = recent_data[sensor_id]
            avg = recent['avg']
            stdev = recent['stdev']
            
            # If value is more than 3 standard deviations from recent average
            if stdev > 0 and abs(value - avg) > 3 * stdev:
                return False, f"Value {value} is statistical outlier (avg: {avg}, stdev: {stdev})"
        
        return True, "Valid"
    
    def update_temperature_data(self, recent_data):
        """Update temperature data with high accuracy"""
        sensors = Sensor.objects.filter(sensor_type='temperature', active=True)
        
        if not sensors.exists():
            self.stdout.write(self.style.WARNING("No active temperature sensors found."))
            return
        
        self.stdout.write("\nFetching high-accuracy temperature data...")
        
        for sensor in sensors:
            weather_data = self.fetch_weather_for_location(
                sensor.name, sensor.latitude, sensor.longitude, 'temperature'
            )
            
            if weather_data and 'temperature' in weather_data:
                temp = weather_data['temperature']
                
                # Apply sensor-specific corrections
                corrected_temp = self.apply_sensor_corrections(temp, sensor, 'temperature')
                
                # Validate
                is_valid, validation_msg = self.validate_sensor_data(
                    corrected_temp, 'temperature', sensor.id, recent_data
                )
                
                if is_valid:
                    SensorData.objects.create(
                        sensor=sensor,
                        value=corrected_temp,
                        timestamp=timezone.now(),
                        accuracy_rating=0.9  # High confidence
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"Saved high-accuracy temperature: {corrected_temp}°C for {sensor.name}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Invalid temperature for {sensor.name}: {validation_msg}"
                    ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"No reliable temperature data for {sensor.name}"
                ))
    
    def update_rainfall_data(self, recent_data):
        """Update rainfall data with high accuracy"""
        sensors = Sensor.objects.filter(sensor_type='rainfall', active=True)
        
        if not sensors.exists():
            self.stdout.write(self.style.WARNING("No active rainfall sensors found."))
            return
            
        self.stdout.write("\nFetching high-accuracy precipitation data...")
        
        for sensor in sensors:
            weather_data = self.fetch_weather_for_location(
                sensor.name, sensor.latitude, sensor.longitude, 'rainfall'
            )
            
            if weather_data and 'precipitation' in weather_data:
                rainfall = max(0, weather_data['precipitation'])  # Ensure non-negative
                
                # Apply sensor-specific corrections
                corrected_rainfall = self.apply_sensor_corrections(rainfall, sensor, 'rainfall')
                
                # Validate
                is_valid, validation_msg = self.validate_sensor_data(
                    corrected_rainfall, 'rainfall', sensor.id, recent_data
                )
                
                if is_valid:
                    SensorData.objects.create(
                        sensor=sensor,
                        value=corrected_rainfall,
                        timestamp=timezone.now(),
                        accuracy_rating=0.85  # Slightly lower confidence than temp
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"Saved high-accuracy rainfall: {corrected_rainfall}mm for {sensor.name}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Invalid rainfall for {sensor.name}: {validation_msg}"
                    ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"No reliable rainfall data for {sensor.name}"
                ))
    
    def update_water_level_data(self, recent_data):
        """Update water level with advanced hydrological modeling"""
        sensors = Sensor.objects.filter(sensor_type='water_level', active=True)
        
        if not sensors.exists():
            self.stdout.write(self.style.WARNING("No active water level sensors found."))
            return
            
        self.stdout.write("\nCalculating water levels with advanced modeling...")
        
        # Get regional data for comprehensive modeling
        regional_rainfall = self.get_regional_rainfall_data()
        weather_forecast = self.get_weather_forecast()
        
        for sensor in sensors:
            try:
                # Base water level
                base_level = self.SENSOR_ADJUSTMENTS['water_level']['base_level']
                
                # Factor 1: Recent rainfall (weighted average)
                rainfall_factor = 0
                if regional_rainfall:
                    # Weight more recent rainfall heavier
                    weights = [0.5 ** i for i in range(len(regional_rainfall))]
                    weighted_avg = sum(w*r for w,r in zip(weights, reversed(regional_rainfall))) / sum(weights)
                    rainfall_factor = min(3.0, weighted_avg / 8)  # More conservative scaling
                
                # Factor 2: Current precipitation with sensor correction
                weather_data = self.fetch_weather_for_location(
                    sensor.name, sensor.latitude, sensor.longitude, 'water_level'
                )
                current_precip_factor = 0
                if weather_data and 'precipitation' in weather_data:
                    current_precip = max(0, weather_data['precipitation'])
                    corrected_precip = self.apply_sensor_corrections(current_precip, sensor, 'rainfall')
                    current_precip_factor = min(1.5, corrected_precip / 15)  # Adjusted scaling
                
                # Factor 3: Forecasted precipitation
                forecast_factor = 0
                if weather_forecast:
                    forecast_precip = weather_forecast.get('precipitation', 0)
                    forecast_factor = min(1.0, forecast_precip / 20)  # Potential future increase
                
                # Factor 4: Location-specific adjustments
                location_factor = self.get_water_level_location_factor(sensor)
                
                # Calculate final water level with all factors
                water_level = round(
                    base_level + 
                    (rainfall_factor * 0.7) +  # Recent rain has 70% impact
                    (current_precip_factor * 1.2) +  # Current rain has 120% impact
                    (forecast_factor * 0.3) *  # Forecast has 30% impact
                    location_factor,
                    2
                )
                
                # Validate
                is_valid, validation_msg = self.validate_sensor_data(
                    water_level, 'water_level', sensor.id, recent_data
                )
                
                if is_valid:
                    SensorData.objects.create(
                        sensor=sensor,
                        value=water_level,
                        timestamp=timezone.now(),
                        accuracy_rating=0.8  # Moderate confidence due to modeling
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"Saved modeled water level: {water_level}m for {sensor.name}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Invalid water level for {sensor.name}: {validation_msg}"
                    ))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Error processing water level for {sensor.name}: {str(e)}"
                ))
                traceback.print_exc()
    
    def get_water_level_location_factor(self, sensor):
        """Get location-specific factor for water level calculation"""
        name = sensor.name.lower()
        if "river" in name:
            return 1.2
        elif "bridge" in name:
            return 0.9
        elif "reservoir" in name or "dam" in name:
            return 1.5
        elif "coastal" in name or "beach" in name:
            return 1.1
        return 1.0
    
    def get_regional_rainfall_data(self):
        """Get comprehensive regional rainfall data for hydrological modeling"""
        try:
            # Get rainfall from all nearby sensors
            rainfall_sensors = Sensor.objects.filter(sensor_type='rainfall', active=True)
            
            # Get readings from last 24 hours
            recent_readings = SensorData.objects.filter(
                sensor__in=rainfall_sensors,
                timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
            ).order_by('-timestamp')
            
            # Return all values for weighted analysis
            return [r.value for r in recent_readings] if recent_readings else []
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error getting regional rainfall: {str(e)}"))
            return []
    
    def get_weather_forecast(self):
        """Get short-term weather forecast for water level prediction"""
        try:
            # Use the first active sensor as reference point
            ref_sensor = Sensor.objects.filter(active=True).first()
            if not ref_sensor:
                return {}
            
            # Get forecast from Open-Meteo
            url = f"https://api.open-meteo.com/v1/forecast?latitude={ref_sensor.latitude}&longitude={ref_sensor.longitude}&hourly=precipitation&timeformat=unixtime&timezone=auto&forecast_days=1"
            response = requests.get(url, timeout=8)
            data = response.json()
            
            if 'hourly' in data:
                # Get precipitation for next 3 hours
                now = timezone.now().timestamp()
                forecast_precip = 0
                count = 0
                
                for i, time in enumerate(data['hourly']['time']):
                    if now <= time <= now + 3*3600:  # Next 3 hours
                        forecast_precip += data['hourly']['precipitation'][i]
                        count += 1
                
                if count > 0:
                    return {
                        'precipitation': forecast_precip / count
                    }
            
            return {}
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error getting weather forecast: {str(e)}"))
            return {}
    
    def update_humidity_data(self, recent_data):
        """Update humidity data with high accuracy"""
        sensors = Sensor.objects.filter(sensor_type='humidity', active=True)
        
        if not sensors.exists():
            self.stdout.write(self.style.WARNING("No active humidity sensors found."))
            return
            
        self.stdout.write("\nFetching high-accuracy humidity data...")
        
        for sensor in sensors:
            weather_data = self.fetch_weather_for_location(
                sensor.name, sensor.latitude, sensor.longitude, 'humidity'
            )
            
            if weather_data and 'humidity' in weather_data:
                humidity = weather_data['humidity']
                
                # No corrections typically needed for humidity
                corrected_humidity = round(humidity, self.SENSOR_ADJUSTMENTS['humidity']['precision'])
                
                # Validate
                is_valid, validation_msg = self.validate_sensor_data(
                    corrected_humidity, 'humidity', sensor.id, recent_data
                )
                
                if is_valid:
                    SensorData.objects.create(
                        sensor=sensor,
                        value=corrected_humidity,
                        timestamp=timezone.now(),
                        accuracy_rating=0.88  # High confidence
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"Saved high-accuracy humidity: {corrected_humidity}% for {sensor.name}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Invalid humidity for {sensor.name}: {validation_msg}"
                    ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"No reliable humidity data for {sensor.name}"
                ))
    
    def update_wind_data(self, recent_data):
        """Update wind speed data with high accuracy"""
        sensors = Sensor.objects.filter(sensor_type='wind_speed', active=True)
        
        if not sensors.exists():
            self.stdout.write(self.style.WARNING("No active wind sensors found."))
            return
            
        self.stdout.write("\nFetching high-accuracy wind data...")
        
        for sensor in sensors:
            weather_data = self.fetch_weather_for_location(
                sensor.name, sensor.latitude, sensor.longitude, 'wind_speed'
            )
            
            if weather_data and 'wind_speed' in weather_data:
                wind_speed = weather_data['wind_speed']
                
                # Apply sensor-specific corrections (especially height adjustment)
                corrected_wind = self.apply_sensor_corrections(wind_speed, sensor, 'wind_speed')
                
                # Validate
                is_valid, validation_msg = self.validate_sensor_data(
                    corrected_wind, 'wind_speed', sensor.id, recent_data
                )
                
                if is_valid:
                    SensorData.objects.create(
                        sensor=sensor,
                        value=corrected_wind,
                        timestamp=timezone.now(),
                        accuracy_rating=0.82  # Moderate confidence (wind is variable)
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"Saved high-accuracy wind speed: {corrected_wind}km/h for {sensor.name}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Invalid wind speed for {sensor.name}: {validation_msg}"
                    ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"No reliable wind speed data for {sensor.name}"
                ))