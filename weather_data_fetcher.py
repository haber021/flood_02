import trafilatura
import json
import re
import requests
from datetime import datetime
from core.models import Sensor, SensorData
from django.utils import timezone

def fetch_weather_for_location(location_name, lat, lng):
    """Fetch weather data for a specific location"""
    try:
        # Format the search query for weather data
        search_query = f"weather {location_name} philippines current temperature"
        search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        
        # Fetch the content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(search_url, headers=headers)
        
        if response.status_code != 200:
            print(f"Error fetching data: {response.status_code}")
            return None
        
        # Extract the temperature using regex
        temperature_pattern = r'(\d+)°C'
        matches = re.search(temperature_pattern, response.text)
        
        if matches:
            temperature = float(matches.group(1))
            print(f"Found temperature for {location_name}: {temperature}°C")
            return temperature
        else:
            # Alternative method using trafilatura
            downloaded = trafilatura.fetch_url(search_url)
            text = trafilatura.extract(downloaded)
            
            # Try to extract temperature from the text
            if text:
                matches = re.search(temperature_pattern, text)
                if matches:
                    temperature = float(matches.group(1))
                    print(f"Found temperature for {location_name}: {temperature}°C")
                    return temperature
            
            print(f"Could not extract temperature for {location_name}")
            return None
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None

def update_weather_data():
    """Update weather data for all temperature sensors"""
    # Get all temperature sensors
    temperature_sensors = Sensor.objects.filter(sensor_type='temperature', active=True)
    
    if not temperature_sensors.exists():
        print("No active temperature sensors found.")
        return
    
    for sensor in temperature_sensors:
        # Get location name from sensor name or default to Vical, Santa Lucia
        location_name = sensor.name.replace('Weather Station', '').strip()
        if not location_name:
            location_name = "Vical, Santa Lucia, Ilocos Sur"
        
        # Fetch temperature data
        temperature = fetch_weather_for_location(location_name, sensor.latitude, sensor.longitude)
        
        if temperature is not None:
            # Save the new sensor reading
            SensorData.objects.create(
                sensor=sensor,
                value=temperature,
                timestamp=timezone.now()
            )
            print(f"Saved new temperature reading for {sensor.name}: {temperature}°C")
        else:
            print(f"Failed to get temperature for {sensor.name}")

def update_rainfall_data():
    """Update rainfall data for all rainfall sensors"""
    # This would connect to a rainfall data API
    # For now, we'll use a simple simulation
    pass

if __name__ == "__main__":
    # This allows the script to be run as a standalone script
    # For Django integration, we need to set up the environment
    import os
    import django
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flood_monitoring.settings')
    django.setup()
    
    print("Updating weather data...")
    update_weather_data()
    print("Done!")
