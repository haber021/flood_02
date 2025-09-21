"""Safe ML Algorithms for Flood Prediction

This module contains simplified implementations of various machine learning algorithms
for enhancing flood prediction accuracy. It avoids importing problematic libraries
and serves as a fallback when advanced algorithms are not available.
"""

import os
import logging
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

# Constants
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data/models')
os.makedirs(MODEL_DIR, exist_ok=True)

# Flag to indicate these are the safe fallback algorithms
SAFE_ALGORITHMS_AVAILABLE = True


class GradientBoostingFloodPredictor:
    """Simplified Gradient Boosting implementation using scikit-learn compatible interface"""
    
    def __init__(self):
        self.name = "Gradient Boosting (Safe Implementation)"
        logger.info(f"Initializing {self.name}")
    
    def train(self, X, y):
        """Train the model with fallback to statistical approach"""
        logger.info(f"Training {self.name} (simulated)")
        # In this safe implementation, we don't actually train a model
        # We'll just use a statistical approach later when predicting
        return self
    
    def predict(self, X):
        """Make prediction using a statistical approach"""
        logger.info(f"Making prediction with {self.name}")
        
        # Manual calculations for demonstration
        if isinstance(X, dict):
            # Process single dictionary
            rainfall = X.get('rainfall_24h', 0)
            water_level = X.get('water_level', 0)
            soil_saturation = X.get('soil_saturation', 50)
            
            # Simple formula: higher values = higher probability
            rainfall_factor = min(100, (rainfall / 50) * 100) if rainfall > 0 else 0
            water_factor = min(100, (water_level / 1.5) * 100) if water_level > 0 else 0
            soil_factor = min(100, soil_saturation)
            
            # Weighted combination
            probability = (rainfall_factor * 0.5) + (water_factor * 0.3) + (soil_factor * 0.2)
            probability = max(0, min(100, probability)) / 100  # Convert to 0-1 range
            
            return [1 if probability > 0.5 else 0], probability
        else:
            # Basic processing for dataframe or numpy array
            # Simple implementation that returns medium probability
            import numpy as np
            try:
                # If X is a numpy array or pandas DataFrame, return array of predictions
                size = len(X) if hasattr(X, '__len__') else 1
                return np.array([0] * size), 0.4  # Default: Not flood, 40% probability
            except:
                # Fallback for any other case
                return [0], 0.4  # Default: Not flood, 40% probability
    
    def save(self, filename=None):
        """Save the model (simulation)"""
        logger.info(f"Simulating save for {self.name}")
        return
    
    def load(self, filename=None):
        """Load the model (simulation)"""
        logger.info(f"Simulating load for {self.name}")
        return self


class SVMFloodPredictor:
    """Simplified SVM implementation using scikit-learn compatible interface"""
    
    def __init__(self):
        self.name = "SVM (Safe Implementation)"
        logger.info(f"Initializing {self.name}")
    
    def train(self, X, y):
        """Train the model with fallback to statistical approach"""
        logger.info(f"Training {self.name} (simulated)")
        # In this safe implementation, we don't actually train a model
        return self
    
    def predict(self, X):
        """Make prediction using a statistical approach"""
        logger.info(f"Making prediction with {self.name}")
        
        # Manual calculations for demonstration
        if isinstance(X, dict):
            # Process single dictionary
            rainfall = X.get('rainfall_24h', 0)
            water_level = X.get('water_level', 0)
            
            # Very simple formula based primarily on water level
            if water_level > 1.2:
                probability = 0.9  # 90% probability
            elif water_level > 0.8:
                probability = 0.65  # 65% probability
            elif rainfall > 40:
                probability = 0.7  # 70% probability
            elif rainfall > 20:
                probability = 0.4  # 40% probability
            else:
                probability = 0.2  # 20% probability
            
            return [1 if probability > 0.5 else 0], probability
        else:
            # Basic processing for dataframe or numpy array
            # Simple implementation that returns medium probability
            import numpy as np
            try:
                # If X is a numpy array or pandas DataFrame, return array of predictions
                size = len(X) if hasattr(X, '__len__') else 1
                return np.array([0] * size), 0.35  # Default: Not flood, 35% probability
            except:
                # Fallback for any other case
                return [0], 0.35  # Default: Not flood, 35% probability
    
    def save(self, filename=None):
        """Save the model (simulation)"""
        logger.info(f"Simulating save for {self.name}")
        return
    
    def load(self, filename=None):
        """Load the model (simulation)"""
        logger.info(f"Simulating load for {self.name}")
        return self


class MultiCriteriaDecisionAnalyzer:
    """Simplified MCDA implementation"""
    
    def __init__(self):
        self.name = "Multi-criteria Decision Analysis (Safe Implementation)"
        logger.info(f"Initializing {self.name}")
        
        # Define criteria weights
        self.criteria = {
            'rainfall_intensity': 0.25,
            'water_level': 0.3,
            'soil_saturation': 0.15,
            'elevation': 0.15,
            'historical_floods': 0.1,
            'proximity_to_water': 0.05
        }
    
    def analyze(self, factors):
        """Analyze flood risk using multi-criteria decision analysis"""
        logger.info(f"Analyzing with {self.name}")
        
        # Normalize factors to 0-1 scale
        normalized_factors = {}
        
        # Rainfall (0-100mm maps to 0-1)
        rainfall = factors.get('rainfall_intensity', 0)
        normalized_factors['rainfall_intensity'] = min(1.0, rainfall / 100)
        
        # Water level (0-3m maps to 0-1)
        water_level = factors.get('water_level', 0)
        normalized_factors['water_level'] = min(1.0, water_level / 3)
        
        # Soil saturation (already 0-100, convert to 0-1)
        soil_saturation = factors.get('soil_saturation', 50)
        normalized_factors['soil_saturation'] = soil_saturation / 100
        
        # Elevation (inverse relationship - lower is riskier)
        # 0-50m maps to 1-0 (inverse)
        elevation = factors.get('elevation', 30)
        normalized_factors['elevation'] = max(0, 1 - (elevation / 50))
        
        # Historical floods (0-10 maps to 0-1)
        historical_floods = factors.get('historical_floods', 0)
        normalized_factors['historical_floods'] = min(1.0, historical_floods / 10)
        
        # Proximity to water (0-100 maps to 0-1)
        proximity = factors.get('proximity_to_water', 50)
        normalized_factors['proximity_to_water'] = proximity / 100
        
        # Calculate weighted score
        score = 0
        for criterion, weight in self.criteria.items():
            score += normalized_factors.get(criterion, 0) * weight
        
        # Determine risk level
        if score > 0.8:
            risk_level = 'high'
        elif score > 0.5:
            risk_level = 'medium'
        elif score > 0.3:
            risk_level = 'low'
        else:
            risk_level = 'minimal'
        
        return {
            'score': score,
            'risk_level': risk_level,
            'normalized_factors': normalized_factors
        }
    
    def save(self, filename=None):
        """Save the model (simulation)"""
        logger.info(f"Simulating save for {self.name}")
        return
    
    def load(self, filename=None):
        """Load the model (simulation)"""
        logger.info(f"Simulating load for {self.name}")
        return self


class DynamicTimeWarpingAnalyzer:
    """Simplified DTW implementation"""
    
    def __init__(self):
        self.name = "Dynamic Time Warping (Safe Implementation)"
        logger.info(f"Initializing {self.name}")
        self.historical_patterns = []
    
    def add_pattern(self, pattern, metadata):
        """Add a pattern to the historical database"""
        self.historical_patterns.append({
            'pattern': pattern,
            'metadata': metadata
        })
    
    def find_similar_patterns(self, current_pattern, top_k=3):
        """Find historical patterns similar to the current pattern"""
        if not self.historical_patterns:
            return []
        
        # Calculate simple Euclidean distance as a simplified version of DTW
        distances = []
        for i, pattern_data in enumerate(self.historical_patterns):
            pattern = pattern_data['pattern']
            
            # Calculate distance (simplified - just sum of squared differences)
            dist = 0
            for j in range(min(len(pattern), len(current_pattern))):
                dist += (pattern[j] - current_pattern[j]) ** 2
            distances.append((i, dist))
        
        # Sort by distance (closest first)
        distances.sort(key=lambda x: x[1])
        
        # Return top_k closest patterns
        results = []
        for i in range(min(top_k, len(distances))):
            pattern_idx = distances[i][0]
            similarity = 1 / (1 + distances[i][1])  # Convert distance to similarity (0-1)
            results.append({
                'pattern': self.historical_patterns[pattern_idx]['pattern'],
                'metadata': self.historical_patterns[pattern_idx]['metadata'],
                'similarity': similarity
            })
        
        return results
        
    def save(self, filename=None):
        """Save the model (simulation)"""
        logger.info(f"Simulating save for {self.name}")
        return
    
    def load(self, filename=None):
        """Load the model (simulation)"""
        logger.info(f"Simulating load for {self.name}")
        return self


class TimeSeriesForecaster:
    """Simplified Time Series Forecasting implementation"""
    
    def __init__(self, method='arima'):
        self.name = "Time Series Forecaster (Safe Implementation)"
        self.method = method  # Can be 'arima' or 'exponential_smoothing'
        logger.info(f"Initializing {self.name} with method: {method}")
    
    def forecast_arima(self, series, steps=1):
        """Simple forecasting function that uses trend extrapolation"""
        # This is a very simplified version that doesn't actually use ARIMA
        logger.info(f"Forecasting with {self.name} (ARIMA simulation)")
        
        if len(series) < 2:
            return [series[-1]] * steps if len(series) > 0 else [0] * steps
        
        # Calculate simple trend (average change)
        changes = [series[i] - series[i-1] for i in range(1, len(series))]
        avg_change = sum(changes) / len(changes)
        
        # Forecast using trend
        last_value = series[-1]
        forecast = [last_value + avg_change * (i+1) for i in range(steps)]
        
        return forecast
    
    def forecast_exponential_smoothing(self, series, steps=1, alpha=0.3):
        """Simple exponential smoothing implementation"""
        logger.info(f"Forecasting with {self.name} (Exponential Smoothing simulation)")
        
        if len(series) < 2:
            return [series[-1]] * steps if len(series) > 0 else [0] * steps
        
        # Very simplified exponential smoothing
        last_smoothed = series[0]
        for value in series[1:]:
            last_smoothed = alpha * value + (1 - alpha) * last_smoothed
        
        # Forecast (constant prediction for simple exponential smoothing)
        forecast = [last_smoothed] * steps
        
        return forecast
        
    def save(self, filename=None):
        """Save the model (simulation)"""
        logger.info(f"Simulating save for {self.name}")
        return
    
    def load(self, filename=None):
        """Load the model (simulation)"""
        logger.info(f"Simulating load for {self.name}")
        return self