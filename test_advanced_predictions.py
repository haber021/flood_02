#!/usr/bin/env python

"""
Test script for advanced flood prediction algorithms

This script tests the various flood prediction algorithms implemented in the system,
including ensemble methods, multi-criteria decision analysis, time series forecasting,
and dynamic time warping.
"""

import os
import sys
import logging
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('flood_prediction_test')

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import prediction modules
try:
    # Set up Django environment
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flood_monitoring.settings')
    django.setup()
    
    # Import prediction modules
    from flood_monitoring.ml.flood_prediction_model import (
        predict_flood_probability,
        predict_with_ensemble,
        predict_with_mcda,
        predict_with_dtw,
        predict_with_time_series
    )
    
    # Check if advanced algorithms are available
    try:
        # Check if the variables are already set in the flood_prediction_model module
        from flood_monitoring.ml.flood_prediction_model import ADVANCED_ALGORITHMS_AVAILABLE
        logger.info(f"Advanced algorithms available: {ADVANCED_ALGORITHMS_AVAILABLE}")
    except ImportError:
        logger.warning("Cannot determine if advanced algorithms are available. Will use basic prediction.")
        ADVANCED_ALGORITHMS_AVAILABLE = False
    
    # Flag to indicate successful imports
    IMPORT_SUCCESS = True
except ImportError as e:
    logger.error(f"Failed to import required modules: {str(e)}")
    IMPORT_SUCCESS = False


def create_test_scenario(scenario_type):
    """Create test data for various flood scenarios
    
    Args:
        scenario_type (str): Type of scenario - 'high_risk', 'medium_risk', 'low_risk'
        
    Returns:
        dict: Dictionary containing sensor data and environmental conditions
    """
    scenarios = {
        'high_risk': {
            'rainfall_24h': 45.0,  # mm
            'rainfall_48h': 75.0,  # mm
            'water_level': 1.8,    # meters
            'water_level_change_24h': 0.4,  # meters
            'soil_saturation': 90,  # percent
            'temperature': 28.5,   # celsius
            'humidity': 85,        # percent
            'elevation': 15,       # meters
            'historical_floods_count': 4,
            'timestamp': datetime.now().isoformat()
        },
        'medium_risk': {
            'rainfall_24h': 30.0,
            'rainfall_48h': 45.0,
            'water_level': 1.4,
            'water_level_change_24h': 0.2,
            'soil_saturation': 75,
            'temperature': 29.0,
            'humidity': 75,
            'elevation': 25,
            'historical_floods_count': 2,
            'timestamp': datetime.now().isoformat()
        },
        'low_risk': {
            'rainfall_24h': 10.0,
            'rainfall_48h': 15.0,
            'water_level': 0.6,
            'water_level_change_24h': 0.1,
            'soil_saturation': 40,
            'temperature': 30.0,
            'humidity': 60,
            'elevation': 45,
            'historical_floods_count': 1,
            'timestamp': datetime.now().isoformat()
        }
    }
    
    return scenarios.get(scenario_type, scenarios['medium_risk'])


def test_prediction_algorithms():
    """Test various flood prediction algorithms and compare results"""
    if not IMPORT_SUCCESS:
        logger.error("Skipping tests due to import failures")
        return
    
    logger.info("Testing flood prediction algorithms...")
    
    # Create test scenarios
    scenarios = {
        'high_risk': create_test_scenario('high_risk'),
        'medium_risk': create_test_scenario('medium_risk'),
        'low_risk': create_test_scenario('low_risk')
    }
    
    # Algorithms to test
    algorithms = ['random_forest']
    
    if ADVANCED_ALGORITHMS_AVAILABLE:
        algorithms.extend(['gradient_boosting', 'svm', 'ensemble', 'mcda', 'dtw', 'time_series'])
    
    # Test each algorithm on each scenario
    results = {}
    
    for scenario_name, scenario_data in scenarios.items():
        results[scenario_name] = {}
        
        logger.info(f"\n===== Testing {scenario_name} scenario =====")
        
        for algorithm in algorithms:
            logger.info(f"\nPredicting with {algorithm} algorithm:")
            try:
                prediction = predict_flood_probability(scenario_data, classification_algorithm=algorithm)
                
                # Log key results
                logger.info(f"Probability: {prediction['probability']}%")
                logger.info(f"Severity: {prediction['severity_text']} (Level {prediction['severity_level']})")
                if prediction.get('hours_to_flood') is not None:
                    logger.info(f"Estimated time to flood: {prediction['hours_to_flood']:.1f} hours")
                logger.info(f"Impact: {prediction['impact']}")
                logger.info(f"Contributing factors: {prediction['contributing_factors']}")
                
                # Store results
                results[scenario_name][algorithm] = {
                    'probability': prediction['probability'],
                    'severity_level': prediction['severity_level'],
                    'severity_text': prediction['severity_text'],
                    'hours_to_flood': prediction.get('hours_to_flood'),
                    'contributing_factors_count': len(prediction['contributing_factors'])
                }
                
            except Exception as e:
                logger.error(f"Error predicting with {algorithm} algorithm: {str(e)}")
                results[scenario_name][algorithm] = {'error': str(e)}
    
    # Compare algorithm results
    logger.info("\n\n===== Algorithm Comparison =====")
    for scenario_name, scenario_results in results.items():
        logger.info(f"\n{scenario_name.upper()} SCENARIO:")
        for algorithm, result in scenario_results.items():
            if 'error' in result:
                logger.info(f"  {algorithm}: ERROR - {result['error']}")
            else:
                logger.info(f"  {algorithm}: {result['probability']}% ({result['severity_text']})")
    
    return results


if __name__ == "__main__":
    logger.info("Starting flood prediction algorithm tests")
    results = test_prediction_algorithms()
    
    # Output detailed results to a file
    try:
        with open('prediction_test_results.json', 'w') as f:
            # Convert to a serializable format
            serializable_results = {}
            for scenario, scenario_data in results.items():
                serializable_results[scenario] = {}
                for algo, algo_data in scenario_data.items():
                    if 'hours_to_flood' in algo_data and algo_data['hours_to_flood'] is not None:
                        algo_data['hours_to_flood'] = float(algo_data['hours_to_flood'])
                    serializable_results[scenario][algo] = algo_data
            
            json.dump(serializable_results, f, indent=2)
        logger.info("Test results saved to prediction_test_results.json")
    except Exception as e:
        logger.error(f"Error saving results to file: {str(e)}")
    
    logger.info("Flood prediction algorithm tests completed")
