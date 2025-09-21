#!/usr/bin/env python
import os
import sys
import time
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flood_monitoring.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def update_weather_data():
    """Run the Django management command to update weather data"""
    try:
        print(f"\n{datetime.now()} - Running weather data update...")
        os.system('python manage.py fetch_real_weather')
        print(f"{datetime.now()} - Weather data update completed\n")
    except Exception as e:
        print(f"{datetime.now()} - Error updating weather data: {e}")

def main():
    # Update immediately on start
    update_weather_data()
    
    # Then update every 30 minutes
    while True:
        # Sleep for 30 minutes (1800 seconds)
        time.sleep(1800)
        update_weather_data()

if __name__ == "__main__":
    main()
