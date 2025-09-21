#!/usr/bin/env python
"""Generate historical data and train the flood prediction model.

This script creates a synthetic historical dataset for training the flood prediction
model and then trains the model using this data.
"""

import os
import sys
import django
import numpy as np
import pandas as pd
import datetime
import random
from sklearn.model_selection import train_test_split

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flood_monitoring.settings')
django.setup()

# Import the ML model module
from flood_monitoring.ml.flood_prediction_model import train_flood_prediction_model


def generate_synthetic_data(num_samples=1000):
    """Generate synthetic historical data for model training.
    
    Args:
        num_samples (int): Number of data points to generate
        
    Returns:
        pandas.DataFrame: Synthetic dataset
    """
    print(f"Generating {num_samples} synthetic data points...")
    
    # Seed for reproducibility
    np.random.seed(42)
    random.seed(42)
    
    # Time range - 3 years of data
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365*3)
    date_range = pd.date_range(start=start_date, end=end_date, periods=num_samples)
    
    # Create dataframe
    df = pd.DataFrame(index=date_range)
    df['timestamp'] = df.index
    
    # Generate feature data
    df['rainfall_24h'] = np.random.exponential(scale=10, size=num_samples)  # mm, exponential distribution
    df['rainfall_48h'] = df['rainfall_24h'] * np.random.uniform(0.8, 1.2, size=num_samples) + np.random.exponential(scale=5, size=num_samples)
    df['rainfall_7d'] = df['rainfall_48h'] * np.random.uniform(1.5, 2.5, size=num_samples) + np.random.exponential(scale=10, size=num_samples)
    
    # Higher values during rainy season (assume rainy season is months 6-10)
    df['month'] = df['timestamp'].dt.month
    rainy_season_mask = df['month'].between(6, 10)
    df.loc[rainy_season_mask, 'rainfall_24h'] = df.loc[rainy_season_mask, 'rainfall_24h'] * 1.5
    df.loc[rainy_season_mask, 'rainfall_48h'] = df.loc[rainy_season_mask, 'rainfall_48h'] * 1.5
    df.loc[rainy_season_mask, 'rainfall_7d'] = df.loc[rainy_season_mask, 'rainfall_7d'] * 1.5
    
    # Water level is affected by rainfall
    df['water_level'] = 0.5 + (df['rainfall_24h'] * 0.02) + (df['rainfall_48h'] * 0.01) + np.random.normal(0, 0.2, size=num_samples)
    df['water_level'] = np.clip(df['water_level'], 0, 5)  # Clip to realistic range
    
    # Water level change is the difference from yesterday
    df['water_level_change_24h'] = np.zeros(num_samples)
    df['water_level_change_24h'][1:] = np.diff(df['water_level'])
    
    # Other environmental factors
    df['temperature'] = 25 + 5 * np.sin(np.linspace(0, 4*np.pi, num_samples)) + np.random.normal(0, 2, size=num_samples)  # Seasonal pattern
    df['humidity'] = 70 + 10 * np.sin(np.linspace(0, 4*np.pi, num_samples)) + np.random.normal(0, 5, size=num_samples)
    df['humidity'] = np.clip(df['humidity'], 0, 100)  # Clip to valid percentage
    
    # Geographic and soil factors
    # Assuming we have multiple locations with different characteristics
    locations = [
        {'name': 'Lowland Area', 'elevation': 10, 'base_saturation': 70},
        {'name': 'Riverside', 'elevation': 20, 'base_saturation': 60},
        {'name': 'Midland Area', 'elevation': 40, 'base_saturation': 50},
        {'name': 'Highland Area', 'elevation': 80, 'base_saturation': 40},
    ]
    
    # Assign random locations
    location_indices = np.random.choice(len(locations), size=num_samples)
    df['location'] = [locations[i]['name'] for i in location_indices]
    df['elevation'] = [locations[i]['elevation'] for i in location_indices]
    
    # Soil saturation depends on rainfall and base saturation of the location
    df['soil_saturation'] = np.zeros(num_samples)
    for i, idx in enumerate(location_indices):
        base_saturation = locations[idx]['base_saturation']
        rainfall_effect = df['rainfall_7d'].iloc[i] * 0.5
        df['soil_saturation'].iloc[i] = min(100, base_saturation + rainfall_effect + np.random.normal(0, 5))
    
    # Historical floods in the area (more for flood-prone areas)
    df['historical_floods_count'] = np.zeros(num_samples, dtype=int)
    for location in locations:
        mask = df['location'] == location['name']
        if location['name'] == 'Lowland Area' or location['name'] == 'Riverside':
            df.loc[mask, 'historical_floods_count'] = np.random.choice([2, 3, 4, 5], size=mask.sum())
        else:
            df.loc[mask, 'historical_floods_count'] = np.random.choice([0, 1, 2], size=mask.sum())
    
    # Add day of year for seasonality
    df['day_of_year'] = df['timestamp'].dt.dayofyear
    
    # Now, generate the target variables based on the features
    # 1. Did a flood occur?
    # Higher probability of flood when: high rainfall, high water level, low elevation, high soil saturation
    
    # Calculate a base flood probability
    flood_score = (
        (df['rainfall_24h'] / 50) * 0.3 +      # Heavy rain within 24h
        (df['rainfall_48h'] / 80) * 0.2 +      # Sustained rain
        (df['water_level'] / 2) * 0.3 +        # High water level
        (df['soil_saturation'] / 100) * 0.2 +  # Saturated soil
        (50 / df['elevation']) * 0.2          # Low elevation areas flood easier
    )
    
    # Higher probability during rainy season
    flood_score[rainy_season_mask] *= 1.2
    
    # Convert to probability and then determine flood occurrence
    flood_prob = 1 / (1 + np.exp(-5 * (flood_score - 0.6)))  # Sigmoid to convert to probability
    df['flood_occurred'] = np.random.binomial(1, flood_prob)  # 1 = flood, 0 = no flood
    
    # 2. Hours until flood (only relevant for flood events)
    df['hours_to_flood'] = np.nan
    flood_mask = df['flood_occurred'] == 1
    
    # For flood events, calculate hours until flood based on conditions
    # Severe conditions lead to faster flooding
    severity = (
        (df.loc[flood_mask, 'rainfall_24h'] / 50) * 0.4 +
        (df.loc[flood_mask, 'water_level'] / 2) * 0.3 +
        (df.loc[flood_mask, 'soil_saturation'] / 100) * 0.3
    )
    
    # Inverse relationship: higher severity -> fewer hours until flood
    df.loc[flood_mask, 'hours_to_flood'] = 48 - (severity * 40) + np.random.normal(0, 5, size=flood_mask.sum())
    df.loc[flood_mask, 'hours_to_flood'] = np.clip(df.loc[flood_mask, 'hours_to_flood'], 1, 48)  # Between 1 and 48 hours
    
    # Drop some features that we don't want to use in training (but kept for data generation)
    df = df.drop(columns=['location'])
    
    print(f"Generated dataset with {num_samples} samples, containing {flood_mask.sum()} flood events")
    
    return df


def main():
    """Main function to generate data and train the model."""
    # Generate synthetic historical data
    historical_data = generate_synthetic_data(num_samples=3000)
    
    # Save the historical data (can be useful for analysis)
    output_dir = os.path.join('flood_monitoring', 'data')
    os.makedirs(output_dir, exist_ok=True)
    historical_data.to_csv(os.path.join(output_dir, 'synthetic_historical_data.csv'), index=False)
    print(f"Saved synthetic historical data to {output_dir}/synthetic_historical_data.csv")
    
    # Train the model
    print("\nTraining flood prediction models...")
    classification_model, regression_model, scaler = train_flood_prediction_model(historical_data)
    
    print("\nModel training complete!")
    print("The models have been saved and are ready to use for flood prediction.")
    
    # Test the model with a sample input
    print("\nTesting the model with sample input:")
    from flood_monitoring.ml.flood_prediction_model import predict_flood_probability
    
    # Sample input data for a high-risk scenario
    test_data = {
        'rainfall_24h': 45.0,  # mm - heavy rainfall
        'rainfall_48h': 70.0,  # mm - sustained heavy rain
        'rainfall_7d': 120.0,  # mm - wet week
        'water_level': 1.8,    # m - high water level
        'water_level_change_24h': 0.3,  # m - rising water
        'temperature': 28.0,   # deg C
        'humidity': 90.0,      # %
        'elevation': 15.0,     # m - low-lying area
        'soil_saturation': 85.0,  # % - very wet soil
        'month': 7,            # July (rainy season)
        'day_of_year': 200,    # Mid-July
        'historical_floods_count': 3  # Area prone to flooding
    }
    
    prediction = predict_flood_probability(test_data)
    print(f"Prediction for high-risk scenario:")
    print(f"  Flood probability: {prediction['probability']}%")
    print(f"  Severity: {prediction['severity_text']} (Level {prediction['severity_level']})")
    if prediction['hours_to_flood'] is not None:
        print(f"  Estimated time to flood: {prediction['hours_to_flood']:.1f} hours")
    print(f"  Impact assessment: {prediction['impact']}")
    print(f"  Contributing factors:")
    for factor in prediction['contributing_factors']:
        print(f"    - {factor}")
    
    # Sample input data for a low-risk scenario
    test_data_low = {
        'rainfall_24h': 5.0,   # mm - light rainfall
        'rainfall_48h': 10.0,  # mm - moderate total rain
        'rainfall_7d': 30.0,   # mm - relatively dry week
        'water_level': 0.5,    # m - low water level
        'water_level_change_24h': 0.0,  # m - stable water
        'temperature': 28.0,   # deg C
        'humidity': 65.0,      # %
        'elevation': 75.0,     # m - higher ground
        'soil_saturation': 40.0,  # % - relatively dry soil
        'month': 2,            # February (dry season)
        'day_of_year': 50,     # Mid-February
        'historical_floods_count': 1  # Area with few floods
    }
    
    prediction_low = predict_flood_probability(test_data_low)
    print(f"\nPrediction for low-risk scenario:")
    print(f"  Flood probability: {prediction_low['probability']}%")
    print(f"  Severity: {prediction_low['severity_text']} (Level {prediction_low['severity_level']})")
    print(f"  Impact assessment: {prediction_low['impact']}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
