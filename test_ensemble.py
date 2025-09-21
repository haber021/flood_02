#!/usr/bin/env python

"""
Simple test script for ensemble flood prediction algorithm
"""

import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ensemble_test')

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
        generate_impact_assessment,
        identify_contributing_factors
    )
    
    # Flag to indicate successful imports
    IMPORT_SUCCESS = True
except ImportError as e:
    logger.error(f"Failed to import required modules: {str(e)}")
    IMPORT_SUCCESS = False


def create_test_data():
    """Create test data for flood scenarios"""
    return {
        'rainfall_24h': 45.0,      # mm
        'rainfall_48h': 75.0,      # mm
        'water_level': 1.8,        # meters
        'water_level_change_24h': 0.4,  # meters
        'soil_saturation': 90,     # percent
        'temperature': 28.5,       # celsius
        'humidity': 85,            # percent
        'elevation': 15,           # meters
        'historical_floods_count': 4
    }


def test_ensemble_approach():
    """Test ensemble approach by directly using helper functions"""
    if not IMPORT_SUCCESS:
        logger.error("Skipping test due to import failures")
        return
    
    logger.info("Testing ensemble approach with custom implementation")
    
    test_data = create_test_data()
    
    # First, make a standard prediction
    logger.info("Making standard prediction with Random Forest")
    standard_result = predict_flood_probability(test_data, classification_algorithm='random_forest')
    
    logger.info(f"Standard prediction result: {standard_result['probability']}% probability")
    
    # Create a simple ensemble implementation
    logger.info("\nImplementing custom ensemble approach")
    
    # Factors that contribute to flooding
    rainfall_factor = min(100, (test_data['rainfall_24h'] / 50) * 100)
    water_level_factor = min(100, (test_data['water_level'] / 1.5) * 100)
    soil_factor = min(100, test_data['soil_saturation'])
    historical_factor = min(100, (test_data['historical_floods_count'] / 5) * 100)
    
    # Weighted ensemble
    ensemble_probability = (
        (rainfall_factor * 0.4) + 
        (water_level_factor * 0.4) + 
        (soil_factor * 0.15) + 
        (historical_factor * 0.05)
    )
    
    logger.info(f"Weighted factors:\n" +
               f"- Rainfall: {rainfall_factor:.1f}% (weight: 40%)\n" +
               f"- Water level: {water_level_factor:.1f}% (weight: 40%)\n" +
               f"- Soil saturation: {soil_factor:.1f}% (weight: 15%)\n" +
               f"- Historical floods: {historical_factor:.1f}% (weight: 5%)")
    
    logger.info(f"Combined ensemble probability: {ensemble_probability:.1f}%")
    
    # Create ensemble result dictionary
    ensemble_result = {
        'probability': int(ensemble_probability),
        'hours_to_flood': None,
        'severity_level': 1,
        'severity_text': 'Advisory'
    }
    
    # Determine severity level based on probability
    if ensemble_result['probability'] >= 85:
        ensemble_result['severity_level'] = 5
        ensemble_result['severity_text'] = 'Catastrophic'
    elif ensemble_result['probability'] >= 70:
        ensemble_result['severity_level'] = 4
        ensemble_result['severity_text'] = 'Emergency'
    elif ensemble_result['probability'] >= 55:
        ensemble_result['severity_level'] = 3
        ensemble_result['severity_text'] = 'Warning'
    elif ensemble_result['probability'] >= 40:
        ensemble_result['severity_level'] = 2
        ensemble_result['severity_text'] = 'Watch'
    else:
        ensemble_result['severity_level'] = 1
        ensemble_result['severity_text'] = 'Advisory'
    
    # Add impact assessment and contributing factors
    ensemble_result['impact'] = generate_impact_assessment(
        ensemble_result['probability'], ensemble_result['hours_to_flood']
    )
    
    ensemble_result['contributing_factors'] = identify_contributing_factors(
        test_data, ensemble_result['probability']
    )
    
    logger.info(f"Final ensemble prediction:\n" +
               f"Probability: {ensemble_result['probability']}%\n" +
               f"Severity: {ensemble_result['severity_text']} (Level {ensemble_result['severity_level']})\n" +
               f"Impact: {ensemble_result['impact']}\n" +
               f"Contributing factors: {ensemble_result['contributing_factors']}")
    
    logger.info("\nComparison with standard Random Forest prediction:\n" +
              f"Ensemble: {ensemble_result['probability']}% ({ensemble_result['severity_text']})\n" +
              f"Random Forest: {standard_result['probability']}% ({standard_result['severity_text']})")
    


if __name__ == "__main__":
    logger.info("Starting ensemble prediction test")
    test_ensemble_approach()
    logger.info("Ensemble prediction test completed")
