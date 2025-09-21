#!/usr/bin/env python
import os
import sys
import time
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flood_monitoring.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def train_models():
    """Run the model training script"""
    try:
        print(f"\n{datetime.now()} - Starting flood prediction model training...")
        os.system('python generate_and_train_model.py')
        print(f"{datetime.now()} - Flood prediction model training completed\n")
    except Exception as e:
        print(f"{datetime.now()} - Error training models: {e}")

def main():
    # Train models immediately on start
    train_models()
    
    # Then train every 24 hours (once a day)
    while True:
        # Sleep for 24 hours (86400 seconds)
        time.sleep(86400)
        train_models()

if __name__ == "__main__":
    main()
