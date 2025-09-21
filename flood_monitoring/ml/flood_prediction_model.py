"""Flood Prediction Machine Learning Model

This module provides functions for training and using machine learning models to predict flood
events based on environmental sensor data, historical patterns, and geographic information.

The model primarily uses rainfall, water level, soil saturation, and elevation data to predict
flood probabilities, timing, and potential impact.

Example usage:
    - Train the model: train_flood_prediction_model(historical_data)
    - Make predictions: predict_flood_probability(current_data)
"""

import os
import datetime
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, mean_squared_error, mean_absolute_error, accuracy_score, f1_score
from sklearn.pipeline import Pipeline
import joblib

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File paths for saving/loading models
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'models')
CLASSIFICATION_MODEL_PATH = os.path.join(MODEL_DIR, 'flood_classification_model.joblib')
REGRESSION_MODEL_PATH = os.path.join(MODEL_DIR, 'flood_timing_model.joblib')
SCALER_PATH = os.path.join(MODEL_DIR, 'feature_scaler.joblib')

# Try to import advanced algorithms (optional)
# Import placeholder classes for graceful fallback when libraries aren't available
class DummyPredictor:
    """Placeholder class when advanced algorithms are not available"""
    def __init__(self, *args, **kwargs):
        self.name = "Dummy Predictor"
        
    def train(self, *args, **kwargs):
        logger.warning("Advanced algorithms not available. Using standard models instead.")
        return self
        
    def predict(self, *args, **kwargs):
        logger.warning("Advanced algorithms not available. Using standard models instead.")
        return 0, 0.15  # Default: No flood, 15% probability
    
    def save(self, filename=None):
        """Dummy save method"""
        logger.warning("Cannot save model: advanced algorithms not available")
        return
        
    def load(self, filename=None):
        """Dummy load method"""
        logger.warning("Cannot load model: advanced algorithms not available")
        return self

# Set defaults assuming libraries aren't available
GradientBoostingFloodPredictor = DummyPredictor
SVMFloodPredictor = DummyPredictor
TimeSeriesForecaster = DummyPredictor
SpatialAnalyzer = DummyPredictor
LSTMFloodPredictor = DummyPredictor
MultiCriteriaDecisionAnalyzer = DummyPredictor
DynamicTimeWarpingAnalyzer = DummyPredictor
ADVANCED_ALGORITHMS_AVAILABLE = False
TENSORFLOW_AVAILABLE = False

# Now try to import the real implementations
try:
    # First check basic dependencies
    import numpy as np
    import pandas as pd
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    BASIC_DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Basic ML dependencies not available: {str(e)}")
    BASIC_DEPENDENCIES_AVAILABLE = False

# First try to import safe algorithms which have no problematic dependencies
try:
    from flood_monitoring.ml.safe_algorithms import (
        GradientBoostingFloodPredictor,
        SVMFloodPredictor,
        MultiCriteriaDecisionAnalyzer,
        DynamicTimeWarpingAnalyzer,
        TimeSeriesForecaster
    )
    SAFE_ALGORITHMS_AVAILABLE = True
    ADVANCED_ALGORITHMS_AVAILABLE = True  # Safe algorithms can be used as advanced ones
    logger.info("Safe prediction algorithms successfully loaded")
except ImportError as e:
    logger.warning(f"Safe algorithms not imported: {str(e)}")
    SAFE_ALGORITHMS_AVAILABLE = False
    ADVANCED_ALGORITHMS_AVAILABLE = False

# Dummy LSTMFloodPredictor and SpatialAnalyzer since they're not in safe_algorithms
class DummyLSTMPredictor(DummyPredictor):
    pass

class DummySpatialAnalyzer(DummyPredictor):
    pass

LSTMFloodPredictor = DummyLSTMPredictor
SpatialAnalyzer = DummySpatialAnalyzer
TENSORFLOW_AVAILABLE = False

# Then try to import real advanced algorithms (may fail due to TensorFlow)
if BASIC_DEPENDENCIES_AVAILABLE and not ADVANCED_ALGORITHMS_AVAILABLE:
    try:
        # Try to import advanced algorithms with potential TensorFlow dependency
        from flood_monitoring.ml.advanced_algorithms import (
            GradientBoostingFloodPredictor as AdvGradientBoostingFloodPredictor,
            SVMFloodPredictor as AdvSVMFloodPredictor,
            TimeSeriesForecaster as AdvTimeSeriesForecaster,
            SpatialAnalyzer as AdvSpatialAnalyzer,
            MultiCriteriaDecisionAnalyzer as AdvMultiCriteriaDecisionAnalyzer,
            DynamicTimeWarpingAnalyzer as AdvDynamicTimeWarpingAnalyzer
        )
        
        # If we got here, we can use the advanced versions
        GradientBoostingFloodPredictor = AdvGradientBoostingFloodPredictor
        SVMFloodPredictor = AdvSVMFloodPredictor
        TimeSeriesForecaster = AdvTimeSeriesForecaster
        SpatialAnalyzer = AdvSpatialAnalyzer
        MultiCriteriaDecisionAnalyzer = AdvMultiCriteriaDecisionAnalyzer
        DynamicTimeWarpingAnalyzer = AdvDynamicTimeWarpingAnalyzer
        
        ADVANCED_ALGORITHMS_AVAILABLE = True
        logger.info("Advanced prediction algorithms successfully loaded")
        
        # Try to import LSTM which requires TensorFlow
        try:
            import tensorflow as tf
            from flood_monitoring.ml.advanced_algorithms import LSTMFloodPredictor as AdvLSTMFloodPredictor
            LSTMFloodPredictor = AdvLSTMFloodPredictor
            TENSORFLOW_AVAILABLE = True
            logger.info("TensorFlow successfully loaded for neural network models")
        except (ImportError, Exception) as e:
            logger.warning(f"TensorFlow not available: {str(e)}")
            TENSORFLOW_AVAILABLE = False
            
    except ImportError as e:
        logger.warning(f"Advanced algorithms not imported: {str(e)}")
        # We keep using the safe algorithms if they were loaded

# Default algorithm to use
DEFAULT_CLASSIFICATION_ALGORITHM = 'random_forest'  # Options: 'random_forest', 'gradient_boosting', 'svm', 'lstm', 'ensemble', 'mcda', 'dtw', 'time_series'
DEFAULT_REGRESSION_ALGORITHM = 'random_forest'      # Options: 'random_forest', 'gradient_boosting'
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

CLASSIFICATION_MODEL_PATH = os.path.join(MODEL_DIR, 'flood_classification_model.joblib')
REGRESSION_MODEL_PATH = os.path.join(MODEL_DIR, 'flood_time_prediction_model.joblib')
FEATURE_SCALER_PATH = os.path.join(MODEL_DIR, 'feature_scaler.joblib')

# Features used for prediction
FEATURES = [
    'rainfall_24h', 'rainfall_48h', 'rainfall_7d',
    'water_level', 'water_level_change_24h',
    'temperature', 'humidity',
    'elevation', 'soil_saturation',
    'month', 'day_of_year', 'historical_floods_count'
]

# Thresholds for flood severity classification
FLOOD_THRESHOLDS = {
    'advisory': 30,     # 30% probability
    'watch': 50,       # 50% probability
    'warning': 70,     # 70% probability
    'emergency': 85,   # 85% probability
    'catastrophic': 95 # 95% probability
}


def preprocess_data(data):
    """Preprocess input data for the flood prediction model.
    
    Args:
        data (dict or pandas.DataFrame): Raw input data with sensor readings and geographical info
        
    Returns:
        pandas.DataFrame: Preprocessed data ready for the model
    """
    # Convert to DataFrame if it's a dictionary
    if isinstance(data, dict):
        df = pd.DataFrame([data])
    else:
        df = data.copy()
    
    # Extract temporal features if timestamp is available
    if 'timestamp' in df.columns:
        # Convert to datetime if not already
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Extract date features
        df['month'] = df['timestamp'].dt.month
        df['day_of_year'] = df['timestamp'].dt.dayofyear
    else:
        # Use current date if no timestamp provided
        now = datetime.datetime.now()
        df['month'] = now.month
        df['day_of_year'] = now.timetuple().tm_yday
    
    # Fill missing values with appropriate defaults
    for feature in FEATURES:
        if feature not in df.columns:
            if feature == 'soil_saturation':
                # Estimate soil saturation from rainfall data if available
                if 'rainfall_24h' in df.columns and 'rainfall_48h' in df.columns:
                    df[feature] = (df['rainfall_24h'] * 2 + df['rainfall_48h']) / 3 * 10  # Simple estimation
                else:
                    df[feature] = 50  # Default mid-range value
            elif feature == 'historical_floods_count':
                df[feature] = 0  # Default to zero historical floods
            elif 'rainfall' in feature and 'rainfall_24h' in df.columns:
                df[feature] = df['rainfall_24h']  # Use 24h rainfall as a fallback
            elif feature == 'water_level_change_24h' and 'water_level' in df.columns:
                df[feature] = 0  # Default to no change
            else:
                df[feature] = 0  # Default for other missing features
    
    # Ensure all required features are in the DataFrame
    for feature in FEATURES:
        if feature not in df.columns:
            logger.warning(f"Missing feature: {feature}. Using default value.")
            df[feature] = 0
    
    return df[FEATURES]


def train_flood_prediction_model(historical_data, classification_algorithm=DEFAULT_CLASSIFICATION_ALGORITHM, 
                            regression_algorithm=DEFAULT_REGRESSION_ALGORITHM, evaluate_only=False):
    """Train machine learning models for flood prediction.
    
    This function trains two models:
    1. A classification model to predict flood probability
    2. A regression model to predict time until flooding
    
    Args:
        historical_data (pandas.DataFrame): Historical data with sensor readings and flood outcomes
        classification_algorithm (str): Algorithm to use for flood classification
        regression_algorithm (str): Algorithm to use for flood timing regression
        evaluate_only (bool): If True, only evaluate existing models, don't train or save
        
    Returns:
        tuple: (classification_model, regression_model, feature_scaler) or metrics dict if evaluate_only=True
    """
    logger.info(f"Starting flood prediction model training using {classification_algorithm} for classification")
    
    # Preprocess data
    X = preprocess_data(historical_data)
    y_flood = historical_data['flood_occurred']  # Binary: Did flooding occur?
    y_time = historical_data['hours_to_flood']   # Regression: Hours until flooding
    
    # Split data into training and testing sets
    X_train, X_test, y_flood_train, y_flood_test = train_test_split(
        X, y_flood, test_size=0.2, random_state=42
    )
    
    # Create feature scaler for standard models
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train classification model (flood probability)
    logger.info(f"Training classification model using {classification_algorithm}...")
    classification_model = None
    metrics = {}
    
    # Select algorithm for classification
    if classification_algorithm == 'random_forest':
        classification_model = Pipeline([
            ('scaler', scaler),
            ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
        ])
        classification_model.fit(X_train, y_flood_train)
    
    elif classification_algorithm == 'gradient_boosting' and ADVANCED_ALGORITHMS_AVAILABLE:
        # Use our GradientBoostingFloodPredictor
        classification_model = GradientBoostingFloodPredictor()
        classification_model.train(X_train, y_flood_train)
    
    elif classification_algorithm == 'svm' and ADVANCED_ALGORITHMS_AVAILABLE:
        # Use our SVMFloodPredictor
        classification_model = SVMFloodPredictor()
        classification_model.train(X_train, y_flood_train)
    
    elif classification_algorithm == 'lstm' and ADVANCED_ALGORITHMS_AVAILABLE:
        try:
            # Use our LSTMFloodPredictor
            # For LSTM, we need to prepare sequential data
            all_data = pd.concat([pd.DataFrame(X_train_scaled, columns=X.columns), 
                                 pd.Series(y_flood_train, name='flood_occurred')], axis=1)
            classification_model = LSTMFloodPredictor()
            classification_model.train(all_data, 'flood_occurred', sequence_length=10, epochs=20, batch_size=32)
        except Exception as e:
            logger.error(f"LSTM training failed: {str(e)}")
            # Fall back to Random Forest
            logger.info("Falling back to Random Forest classifier")
            classification_model = Pipeline([
                ('scaler', scaler),
                ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
            ])
            classification_model.fit(X_train, y_flood_train)
    else:
        # Default to Random Forest if algorithm not recognized
        logger.info("Using default Random Forest classifier")
        classification_model = Pipeline([
            ('scaler', scaler),
            ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
        ])
        classification_model.fit(X_train, y_flood_train)
    
    # Evaluate classification model
    if classification_algorithm in ['gradient_boosting', 'svm'] and ADVANCED_ALGORITHMS_AVAILABLE:
        y_flood_pred, _ = classification_model.predict(X_test)
    elif classification_algorithm == 'lstm' and ADVANCED_ALGORITHMS_AVAILABLE:
        # Special evaluation for LSTM (simplified)
        try:
            test_data = pd.concat([pd.DataFrame(X_test_scaled, columns=X.columns), 
                                  pd.Series(y_flood_test, name='flood_occurred')], axis=1)
            y_flood_pred = []
            sequence_len = 10  # Should match training sequence length
            
            # Use a subset for demonstration if data is large
            test_subset = min(50, len(test_data) - sequence_len)
            for i in range(test_subset):
                seq = test_data.iloc[i:i+sequence_len].drop(columns=['flood_occurred'])
                y_flood_pred.append(int(classification_model.predict(seq) > 0.5))
                
            y_flood_test = y_flood_test[:test_subset]  # Match prediction length
        except Exception as e:
            logger.error(f"LSTM evaluation failed: {str(e)}")
            y_flood_pred = [0] * len(y_flood_test)  # Default predictions
    else:
        y_flood_pred = classification_model.predict(X_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_flood_test, y_flood_pred)
    f1 = f1_score(y_flood_test, y_flood_pred)
    logger.info("Classification model evaluation:")
    logger.info(f"Accuracy: {accuracy:.4f}, F1 Score: {f1:.4f}")
    logger.info(classification_report(y_flood_test, y_flood_pred))
    
    metrics['accuracy'] = accuracy
    metrics['f1_score'] = f1
    
    # Train regression model (time until flooding) - only on data where flooding occurred
    regression_model = None
    logger.info(f"Training regression model using {regression_algorithm}...")
    flood_mask = historical_data['flood_occurred'] == 1
    if flood_mask.sum() > 0:
        X_flood = X[flood_mask]
        y_time_flood = y_time[flood_mask]
        
        X_time_train, X_time_test, y_time_train, y_time_test = train_test_split(
            X_flood, y_time_flood, test_size=0.2, random_state=42
        )
        
        # Select algorithm for regression
        if regression_algorithm == 'random_forest':
            regression_model = Pipeline([
                ('scaler', StandardScaler()),
                ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
            ])
        elif regression_algorithm == 'gradient_boosting':
            regression_model = Pipeline([
                ('scaler', StandardScaler()),
                ('regressor', GradientBoostingRegressor(n_estimators=100, random_state=42))
            ])
        else:
            # Default to Gradient Boosting if not recognized
            regression_model = Pipeline([
                ('scaler', StandardScaler()),
                ('regressor', GradientBoostingRegressor(n_estimators=100, random_state=42))
            ])
        
        regression_model.fit(X_time_train, y_time_train)
        
        # Evaluate regression model
        y_time_pred = regression_model.predict(X_time_test)
        mse = mean_squared_error(y_time_test, y_time_pred)
        mae = mean_absolute_error(y_time_test, y_time_pred)
        logger.info(f"Regression model - MSE: {mse:.2f}, MAE: {mae:.2f}")
        
        metrics['regression_mse'] = mse
        metrics['regression_mae'] = mae
    else:
        logger.warning("No flood events in training data. Regression model not trained.")
    
    # Save models if not in evaluate_only mode
    if not evaluate_only:
        logger.info("Saving models...")
        # For advanced algorithm models that have their own save methods
        if classification_algorithm in ['gradient_boosting', 'svm', 'lstm'] and ADVANCED_ALGORITHMS_AVAILABLE:
            try:
                classification_model.save()
            except Exception as e:
                logger.error(f"Error saving advanced classification model: {str(e)}")
                # Consider saving model in another format if needed
        else:
            # Standard sklearn Pipeline models
            joblib.dump(classification_model, CLASSIFICATION_MODEL_PATH)
        
        if regression_model is not None:
            joblib.dump(regression_model, REGRESSION_MODEL_PATH)
    
    if evaluate_only:
        return metrics
    else:
        return classification_model, regression_model, scaler


def load_models(classification_algorithm=DEFAULT_CLASSIFICATION_ALGORITHM, regression_algorithm=DEFAULT_REGRESSION_ALGORITHM):
    """Load trained models from disk.
    
    Args:
        classification_algorithm (str): The algorithm used for classification
        regression_algorithm (str): The algorithm used for regression
    
    Returns:
        tuple: (classification_model, regression_model)
    """
    classification_model = None
    regression_model = None
    
    try:
        # Try to load the appropriate model based on the algorithm
        if classification_algorithm in ['gradient_boosting', 'svm', 'lstm'] and ADVANCED_ALGORITHMS_AVAILABLE:
            # Load the advanced model
            if classification_algorithm == 'gradient_boosting':
                logger.info("Loading Gradient Boosting classification model...")
                classification_model = GradientBoostingFloodPredictor()
                classification_model.load()
            elif classification_algorithm == 'svm':
                logger.info("Loading SVM classification model...")
                classification_model = SVMFloodPredictor()
                classification_model.load()
            elif classification_algorithm == 'lstm':
                logger.info("Loading LSTM classification model...")
                classification_model = LSTMFloodPredictor()
                classification_model.load()
        else:
            # Default to standard models
            if os.path.exists(CLASSIFICATION_MODEL_PATH):
                logger.info("Loading Random Forest classification model...")
                classification_model = joblib.load(CLASSIFICATION_MODEL_PATH)
        
        # Load regression model
        if os.path.exists(REGRESSION_MODEL_PATH):
            logger.info("Loading flood timing regression model...")
            regression_model = joblib.load(REGRESSION_MODEL_PATH)
    except Exception as e:
        logger.error(f"Error loading models: {e}")
        # If advanced algorithm loading fails, try to fall back to standard model
        if classification_algorithm in ['gradient_boosting', 'svm', 'lstm'] and ADVANCED_ALGORITHMS_AVAILABLE:
            try:
                if os.path.exists(CLASSIFICATION_MODEL_PATH):
                    logger.info("Falling back to standard classification model...")
                    classification_model = joblib.load(CLASSIFICATION_MODEL_PATH)
            except Exception:
                pass
    
    return classification_model, regression_model


def predict_flood_probability(data=None, classification_algorithm=DEFAULT_CLASSIFICATION_ALGORITHM, 
                            regression_algorithm=DEFAULT_REGRESSION_ALGORITHM):
    """Predict flood probability based on current sensor data."""

    # Import fetch_real_weather if not already imported
    from flood_monitoring.ml.fetch_real_weather import fetch_real_weather

    # If no data is provided, or data is missing key fields, fetch real weather data
    if data is None or not isinstance(data, dict) or not all(
        k in data for k in ['rainfall_24h', 'water_level', 'soil_saturation', 'elevation']
    ):
        logger.info("No or incomplete data provided. Fetching real weather data using fetch_real_weather().")
        data = fetch_real_weather()

    # Check if we're using an advanced ensemble approach
    if classification_algorithm == 'ensemble' and ADVANCED_ALGORITHMS_AVAILABLE:
        return predict_with_ensemble(data)
    
    # If we're using Multi-criteria Decision Analysis
    if classification_algorithm == 'mcda' and ADVANCED_ALGORITHMS_AVAILABLE:
        return predict_with_mcda(data)
    
    # If we're using Dynamic Time Warping
    if classification_algorithm == 'dtw' and ADVANCED_ALGORITHMS_AVAILABLE:
        return predict_with_dtw(data)
    
    # If we're using time series forecasting
    if classification_algorithm == 'time_series' and ADVANCED_ALGORITHMS_AVAILABLE:
        return predict_with_time_series(data)
        
    # Load models with specified algorithms for standard approaches
    classification_model, regression_model = load_models(classification_algorithm, regression_algorithm)
    
    # Initialize result dictionary
    result = {
        'probability': 0,
        'severity_level': 0,
        'severity_text': 'Normal',
        'hours_to_flood': None,
        'contributing_factors': [],
        'model_used': classification_algorithm,
        'last_updated': datetime.datetime.now().isoformat(),
        'prediction_details': {}
    }
    
    if classification_model is None:
        logger.warning("Classification model not found. Using default prediction.")
        # Generate prediction based on rainfall and water level manually
        if isinstance(data, dict):
            rainfall_24h = data.get('rainfall_24h', 0)
            water_level = data.get('water_level', 0)
            water_level_threshold = 1.5  # Example threshold
            rainfall_threshold = 50      # Example threshold (mm in 24h)
            
            rainfall_factor = min(100, (rainfall_24h / rainfall_threshold) * 100) if rainfall_threshold > 0 else 0
            water_level_factor = min(100, (water_level / water_level_threshold) * 100) if water_level_threshold > 0 else 0
            
            # Weighted average of factors
            probability = (rainfall_factor * 0.6) + (water_level_factor * 0.4)  # 60% rainfall, 40% water level
            result['probability'] = int(probability)
            result['model_used'] = 'statistical_formula'  # Indicate we used a simple formula
        else:
            result['probability'] = 15  # Default low probability
            result['model_used'] = 'default_value'  # Indicate we used a default value
    else:
        # Preprocess input data
        X = preprocess_data(data)
        
        # Predict flood probability based on the model type
        if classification_algorithm in ['gradient_boosting', 'svm'] and ADVANCED_ALGORITHMS_AVAILABLE:
            # These advanced models return prediction and probability
            try:
                prediction_result = classification_model.predict(X)
                
                # Handle different return formats from different implementations
                if isinstance(prediction_result, tuple) and len(prediction_result) == 2:
                    # Standard format: (predictions, probabilities)
                    predictions, probability_value = prediction_result
                    probability = float(probability_value) * 100 if isinstance(probability_value, (float, int)) else 15
                elif isinstance(prediction_result, list) and len(prediction_result) == 2:
                    # Alternative format: [predictions, probability]
                    probability = float(prediction_result[1]) * 100 if isinstance(prediction_result[1], (float, int)) else 15
                else:
                    # Fallback for any other return format
                    probability = 15
            except Exception as e:
                logger.error(f"Error making prediction with advanced model: {str(e)}")
                probability = 15  # Default if prediction fails
        elif classification_algorithm == 'lstm' and ADVANCED_ALGORITHMS_AVAILABLE:
            # LSTM models may require sequential data
            try:
                # For real-time prediction, we need to handle sequences differently
                # For simplicity, we'll make a single prediction using the current data point
                # In a production system, you would maintain a queue of recent readings
                value = classification_model.predict(X)
                probability = float(value) * 100 if value is not None else 15
            except Exception as e:
                logger.error(f"Error making prediction with LSTM model: {str(e)}")
                probability = 15  # Default if prediction fails
        else:
            # Standard scikit-learn pipeline models
            try:
                probability = classification_model.predict_proba(X)[0, 1] * 100  # Convert to percentage
            except Exception as e:
                logger.error(f"Error making prediction with standard model: {str(e)}")
                probability = 15  # Default if prediction fails
        
        result['probability'] = int(probability)
        
        # If flooding is likely, predict time until flood
        if probability > 50 and regression_model is not None:
            try:
                hours_to_flood = regression_model.predict(X)[0]
                result['hours_to_flood'] = max(0, float(hours_to_flood))  # Ensure non-negative
                
                # Calculate predicted flood time
                now = datetime.datetime.now()
                flood_time = now + datetime.timedelta(hours=result['hours_to_flood'])
                result['flood_time'] = flood_time.isoformat()
            except Exception as e:
                logger.error(f"Error predicting flood timing: {str(e)}")
                # Don't set hours_to_flood if prediction fails
    
    # Determine severity level based on probability
    for level, threshold in sorted(FLOOD_THRESHOLDS.items(), key=lambda x: x[1]):
        if result['probability'] >= threshold:
            result['severity_text'] = level.capitalize()
            if level == 'advisory':
                result['severity_level'] = 1
            elif level == 'watch':
                result['severity_level'] = 2
            elif level == 'warning':
                result['severity_level'] = 3
            elif level == 'emergency':
                result['severity_level'] = 4
            elif level == 'catastrophic':
                result['severity_level'] = 5
    
    # Generate impact assessment based on severity
    if result['severity_level'] <= 1:
        result['impact'] = "No significant flooding expected."
    elif result['severity_level'] == 2:
        result['impact'] = "Possible minor flooding in low-lying areas."
    elif result['severity_level'] == 3:
        result['impact'] = "Moderate flooding likely. Some roads may be impassable."
    elif result['severity_level'] == 4:
        result['impact'] = "Severe flooding expected with significant infrastructure impact."
    else:
        result['impact'] = "Catastrophic flooding expected. Immediate evacuation recommended."
    
    # Identify contributing factors (for example purposes)
    if isinstance(data, dict):
        # Check rainfall
        if data.get('rainfall_24h', 0) > 30:
            result['contributing_factors'].append(f"Heavy rainfall in the last 24 hours ({data.get('rainfall_24h', 0):.1f}mm)")
        
        # Check water level
        if data.get('water_level', 0) > 1.0:
            result['contributing_factors'].append(f"Elevated water level ({data.get('water_level', 0):.2f}m)")
        
        # Check soil saturation if available
        if data.get('soil_saturation', 0) > 80:
            result['contributing_factors'].append("High soil saturation limiting water absorption")
        
        # Check historical context
        if data.get('historical_floods_count', 0) > 3:
            result['contributing_factors'].append("Area has history of frequent flooding")
        
        # If no factors but high probability
        if not result['contributing_factors'] and result['probability'] > 30:
            result['contributing_factors'].append("Multiple minor factors contributing to flood risk")
    
    return result


def predict_with_ensemble(data):
    """Make flood prediction using an ensemble of multiple models
    
    This function combines predictions from multiple models to improve accuracy and robustness.
    
    Args:
        data (dict): Dictionary containing environmental conditions
        
    Returns:
        dict: Prediction results including probability, impact assessment,
              estimated time to flood, and contributing factors
    """
    logger.info("Making flood prediction using ensemble of multiple models")
    
    # Initialize result
    result = {
        'probability': 0,
        'hours_to_flood': None,
        'severity_level': 1,
        'severity_text': 'Advisory',
        'impact': 'No significant flooding expected.',
        'contributing_factors': [],
        'model_used': 'ensemble',
        'prediction_details': {
            'algorithm': 'Ensemble (Multiple Models)',
            'individual_models': {}
        }
    }
    
    # Preprocess input data
    X = preprocess_data(data)
    
    # List of models to try (in order of preference)
    # If advanced algorithms aren't available, just use the basic model
    if not ADVANCED_ALGORITHMS_AVAILABLE:
        models_to_try = [
            {'name': 'random_forest', 'weight': 1.0}
        ]
        logger.warning("Advanced algorithms not available. Using only Random Forest model in ensemble.")
    else:
        models_to_try = [
            {'name': 'random_forest', 'weight': 0.3},
            {'name': 'gradient_boosting', 'weight': 0.3},
            {'name': 'svm', 'weight': 0.2}
        ]
        # Only add LSTM if TensorFlow is available
        if TENSORFLOW_AVAILABLE:
            models_to_try.append({'name': 'lstm', 'weight': 0.2})
            logger.info("Using all models including neural networks in ensemble")
        else:
            # Redistribute weights
            models_to_try = [
                {'name': 'random_forest', 'weight': 0.4},
                {'name': 'gradient_boosting', 'weight': 0.4},
                {'name': 'svm', 'weight': 0.2}
            ]
            logger.info("Using ensemble without neural networks (TensorFlow not available)")
    
    # Track total weight of successful predictions
    total_weight = 0
    weighted_probability = 0
    hours_predictions = []
    
    # Try each model and aggregate results
    for model_info in models_to_try:
        model_name = model_info['name']
        model_weight = model_info['weight']
        
        try:
            # Get prediction from this model
            model_result = predict_flood_probability(data, classification_algorithm=model_name)
            
            # Store individual model result
            result['prediction_details']['individual_models'][model_name] = {
                'probability': model_result['probability'],
                'hours_to_flood': model_result.get('hours_to_flood'),
                'weight': model_weight
            }
            
            # Add to weighted average
            weighted_probability += model_result['probability'] * model_weight
            total_weight += model_weight
            
            # Track time predictions
            if model_result.get('hours_to_flood') is not None:
                hours_predictions.append(model_result['hours_to_flood'])
            
            logger.info(f"Ensemble model {model_name} predicted {model_result['probability']}% probability")
        except Exception as e:
            logger.error(f"Error using {model_name} model in ensemble: {str(e)}")
    
    # If no models succeeded, fall back to default
    if total_weight == 0:
        logger.warning("All ensemble models failed. Falling back to default model.")
        return predict_flood_probability(data, classification_algorithm='random_forest')
    
    # Calculate final weighted average probability
    final_probability = int(round(weighted_probability / total_weight))
    result['probability'] = final_probability
    
    # Calculate average hours to flood (if any predictions)
    if hours_predictions:
        result['hours_to_flood'] = round(sum(hours_predictions) / len(hours_predictions), 1)
    
    # Determine severity level based on probability
    if result['probability'] >= 85:
        result['severity_level'] = 5
        result['severity_text'] = 'Catastrophic'
    elif result['probability'] >= 70:
        result['severity_level'] = 4
        result['severity_text'] = 'Emergency'
    elif result['probability'] >= 55:
        result['severity_level'] = 3
        result['severity_text'] = 'Warning'
    elif result['probability'] >= 40:
        result['severity_level'] = 2
        result['severity_text'] = 'Watch'
    else:
        result['severity_level'] = 1
        result['severity_text'] = 'Advisory'
    
    # Generate impact assessment
    result['impact'] = generate_impact_assessment(result['probability'], result['hours_to_flood'])
    
    # Identify contributing factors
    result['contributing_factors'] = identify_contributing_factors(data, result['probability'])
    
    return result


def predict_with_mcda(data):
    """Make flood prediction using Multi-criteria Decision Analysis
    
    This function uses MCDA to evaluate flood risk based on multiple criteria.
    
    Args:
        data (dict): Dictionary containing environmental conditions
        
    Returns:
        dict: Prediction results including probability, impact assessment,
              and contributing factors
    """
    logger.info("Making flood prediction using Multi-criteria Decision Analysis")
    
    if not ADVANCED_ALGORITHMS_AVAILABLE:
        logger.warning("Advanced algorithms not available. Falling back to default model.")
        return predict_flood_probability(data, classification_algorithm='random_forest')
    
    # Initialize result
    result = {
        'probability': 0,
        'hours_to_flood': None,
        'severity_level': 1,
        'severity_text': 'Advisory',
        'impact': 'No significant flooding expected.',
        'contributing_factors': [],
        'model_used': 'mcda',
        'prediction_details': {
            'algorithm': 'Multi-criteria Decision Analysis',
            'criteria_weights': {},
            'normalized_factors': {}
        }
    }
    
    try:
        # Create and configure MCDA analyzer
        mcda = MultiCriteriaDecisionAnalyzer()
        
        # Map our data to MCDA input factors
        rainfall_24h = data.get('rainfall_24h', 0)
        if isinstance(rainfall_24h, dict) and 'total' in rainfall_24h:
            rainfall_24h = rainfall_24h.get('total', 0)
        
        water_level = data.get('water_level', 0)
        soil_saturation = data.get('soil_saturation', 50)
        elevation = data.get('elevation', 30)
        historical_floods = data.get('historical_floods_count', 0)
        
        # Create input factors for MCDA
        mcda_factors = {
            'rainfall_intensity': rainfall_24h,
            'water_level': water_level,
            'soil_saturation': soil_saturation,
            'elevation': elevation,
            'historical_floods': historical_floods,
            'proximity_to_water': 50  # Default value (assuming medium proximity)
        }
        
        # Perform MCDA analysis
        mcda_result = mcda.analyze(mcda_factors)
        
        # Convert MCDA score to probability
        result['probability'] = int(mcda_result['score'] * 100)
        result['prediction_details']['criteria_weights'] = mcda.criteria
        result['prediction_details']['normalized_factors'] = mcda_result['normalized_factors']
        
        # Map MCDA risk level to our severity scale
        risk_level_map = {
            'minimal': 1,
            'low': 2,
            'medium': 3,
            'high': 4
        }
        result['severity_level'] = risk_level_map.get(mcda_result['risk_level'], 1)
        
        # Set severity text based on severity level
        severity_text_map = {
            1: 'Advisory',
            2: 'Watch',
            3: 'Warning',
            4: 'Emergency',
            5: 'Catastrophic'
        }
        result['severity_text'] = severity_text_map.get(result['severity_level'], 'Advisory')
        
        # Get weather to add hours to flood (if high risk)
        if result['severity_level'] >= 3:
            # Simplified formula using rainfall and water level
            rain_factor = min(1, rainfall_24h / 50)
            water_factor = min(1, water_level / 1.5)
            soil_factor = min(1, soil_saturation / 100)
            
            # More intense rainfall, higher water level, more saturated soil = less time to flood
            weighted_factor = (rain_factor * 0.5) + (water_factor * 0.3) + (soil_factor * 0.2)
            hours_to_flood = max(0, 24 * (1 - weighted_factor))
            result['hours_to_flood'] = round(hours_to_flood, 1)
        
        # Generate impact assessment
        result['impact'] = generate_impact_assessment(result['probability'], result['hours_to_flood'])
        
        # Identify contributing factors
        result['contributing_factors'] = identify_contributing_factors(data, result['probability'])
        
    except Exception as e:
        logger.error(f"Error using MCDA for prediction: {str(e)}")
        # Fall back to default model
        return predict_flood_probability(data, classification_algorithm='random_forest')
    
    return result


def predict_with_dtw(data):
    """Make flood prediction using Dynamic Time Warping pattern matching
    
    This function uses DTW to compare current patterns with historical flood events.
    
    Args:
        data (dict): Dictionary containing environmental conditions
        
    Returns:
        dict: Prediction results
    """
    logger.info("Making flood prediction using Dynamic Time Warping")
    
    if not ADVANCED_ALGORITHMS_AVAILABLE:
        logger.warning("Advanced algorithms not available. Falling back to default model.")
        return predict_flood_probability(data, classification_algorithm='random_forest')
    
    # Initialize result
    result = {
        'probability': 0,
        'hours_to_flood': None,
        'severity_level': 1,
        'severity_text': 'Advisory',
        'impact': 'No significant flooding expected.',
        'contributing_factors': [],
        'model_used': 'dtw',
        'prediction_details': {
            'algorithm': 'Dynamic Time Warping',
            'similar_patterns': []
        }
    }
    
    try:
        # Try to load an existing DTW analyzer with historical patterns
        dtw = DynamicTimeWarpingAnalyzer()
        
        # Create a pattern from current data
        # For DTW we'd typically use time series data, but here we'll use a simplified approach
        # Convert current data to a pattern representation
        current_pattern = [
            data.get('rainfall_24h', 0) if not isinstance(data.get('rainfall_24h', 0), dict) 
            else data.get('rainfall_24h', {}).get('total', 0),
            data.get('water_level', 0),
            data.get('soil_saturation', 50),
            data.get('temperature', 25),
            data.get('humidity', 60)
        ]
        
        # Generate some historical patterns for demonstration
        # In a real system, these would come from a database of past events
        if not hasattr(dtw, 'historical_patterns') or not dtw.historical_patterns:
            # Generate some sample historical patterns
            # High flooding patterns
            dtw.add_pattern([40, 1.8, 90, 28, 85], {'flood_occurred': True, 'severity': 4, 'hours_to_flood': 5})
            dtw.add_pattern([55, 2.0, 85, 27, 80], {'flood_occurred': True, 'severity': 5, 'hours_to_flood': 3})
            dtw.add_pattern([35, 1.6, 95, 29, 90], {'flood_occurred': True, 'severity': 3, 'hours_to_flood': 8})
            
            # Medium flooding patterns
            dtw.add_pattern([25, 1.2, 75, 26, 70], {'flood_occurred': True, 'severity': 2, 'hours_to_flood': 12})
            dtw.add_pattern([30, 1.3, 70, 28, 65], {'flood_occurred': True, 'severity': 2, 'hours_to_flood': 15})
            
            # No flooding patterns
            dtw.add_pattern([10, 0.6, 50, 30, 50], {'flood_occurred': False, 'severity': 0})
            dtw.add_pattern([5, 0.5, 40, 32, 45], {'flood_occurred': False, 'severity': 0})
            dtw.add_pattern([15, 0.8, 55, 29, 60], {'flood_occurred': False, 'severity': 1})
        
        # Find similar historical patterns
        similar_patterns = dtw.find_similar_patterns(current_pattern, top_k=3)
        
        if similar_patterns:
            # Extract information from similar patterns
            flood_probabilities = []
            severity_levels = []
            flood_times = []
            
            # Calculate similarity-weighted values
            total_similarity_weight = 0
            
            for i, (distance, pattern, metadata) in enumerate(similar_patterns):
                # Convert distance to similarity (lower distance = higher similarity)
                similarity = 1 / (1 + distance)  # Scale to 0-1 range
                total_similarity_weight += similarity
                
                # Store pattern info for result details
                result['prediction_details']['similar_patterns'].append({
                    'similarity': round(similarity, 2),
                    'flood_occurred': metadata.get('flood_occurred', False),
                    'severity': metadata.get('severity', 0)
                })
                
                # Add to our calculations with similarity weighting
                if metadata.get('flood_occurred', False):
                    flood_probabilities.append(similarity * 100)  # Scale to 0-100
                else:
                    flood_probabilities.append(similarity * 20)  # Lower base value for non-floods
                
                severity_levels.append(metadata.get('severity', 0) * similarity)
                
                if metadata.get('hours_to_flood') is not None:
                    flood_times.append(metadata.get('hours_to_flood') * similarity)
            
            # Calculate weighted averages
            if total_similarity_weight > 0:
                result['probability'] = int(sum(flood_probabilities) / total_similarity_weight)
                avg_severity = sum(severity_levels) / total_similarity_weight
                result['severity_level'] = max(1, min(5, round(avg_severity)))
                
                if flood_times:
                    result['hours_to_flood'] = round(sum(flood_times) / sum(similarity for _, _, m in similar_patterns 
                                                                if m.get('hours_to_flood') is not None), 1)
        else:
            # No similar patterns found, use default values
            result['probability'] = 15
            logger.warning("No similar historical patterns found for DTW comparison")
            
        # Set severity text based on severity level
        severity_text_map = {
            1: 'Advisory',
            2: 'Watch',
            3: 'Warning',
            4: 'Emergency',
            5: 'Catastrophic'
        }
        result['severity_text'] = severity_text_map.get(result['severity_level'], 'Advisory')
        
        # Generate impact assessment
        result['impact'] = generate_impact_assessment(result['probability'], result['hours_to_flood'])
        
        # Identify contributing factors
        result['contributing_factors'] = identify_contributing_factors(data, result['probability'])
        
    except Exception as e:
        logger.error(f"Error using DTW for prediction: {str(e)}")
        # Fall back to default model
        return predict_flood_probability(data, classification_algorithm='random_forest')
    
    return result


def predict_with_time_series(data):
    """Make flood prediction using time series forecasting
    
    This function uses time series models like ARIMA to forecast flood-related variables.
    
    Args:
        data (dict): Dictionary containing environmental conditions
        
    Returns:
        dict: Prediction results
    """
    logger.info("Making flood prediction using time series forecasting")
    
    if not ADVANCED_ALGORITHMS_AVAILABLE:
        logger.warning("Advanced algorithms not available. Falling back to default model.")
        return predict_flood_probability(data, classification_algorithm='random_forest')
    
    # Initialize result
    result = {
        'probability': 0,
        'hours_to_flood': None,
        'severity_level': 1,
        'severity_text': 'Advisory',
        'impact': 'No significant flooding expected.',
        'contributing_factors': [],
        'model_used': 'time_series',
        'prediction_details': {
            'algorithm': 'Time Series Forecasting',
            'forecasts': {}
        }
    }
    
    try:
        # Try to load existing time series models
        rainfall_forecaster = TimeSeriesForecaster(method='arima')
        water_level_forecaster = TimeSeriesForecaster(method='arima')
        
        # Attempt to make forecasts from current data
        # In a real system, we'd have historical time series data available
        # Here we'll use a simplified approach based on current values
        
        # Use current values to determine flood probability
        rainfall_24h = data.get('rainfall_24h', 0)
        if isinstance(rainfall_24h, dict) and 'total' in rainfall_24h:
            rainfall_24h = rainfall_24h.get('total', 0)
            
        water_level = data.get('water_level', 0)
        water_level_change = data.get('water_level_change_24h', 0)
        soil_saturation = data.get('soil_saturation', 50)
        
        # Check for trends - are values increasing?
        rainfall_trend = data.get('rainfall_trend', 0)  # Positive = increasing
        water_level_trend = water_level_change if water_level_change is not None else 0
        
        # Simple forecast based on current values and trends
        result['prediction_details']['forecasts']['rainfall_24h'] = rainfall_24h
        result['prediction_details']['forecasts']['rainfall_trend'] = rainfall_trend
        result['prediction_details']['forecasts']['water_level'] = water_level
        result['prediction_details']['forecasts']['water_level_trend'] = water_level_trend
        
        # Project values forward
        rainfall_24h_forecast = max(0, rainfall_24h + (rainfall_trend * 24))
        water_level_forecast = max(0, water_level + (water_level_trend * 24))
        
        # Calculate flood probability from projected values
        rainfall_factor = min(100, (rainfall_24h_forecast / 50) * 100)
        water_level_factor = min(100, (water_level_forecast / 1.5) * 100)
        soil_factor = min(100, soil_saturation)
        
        # Combine factors with weights
        result['probability'] = int(
            (rainfall_factor * 0.4) + 
            (water_level_factor * 0.4) + 
            (soil_factor * 0.2)
        )
        
        # Determine time to flood based on trends
        if result['probability'] >= 50 and water_level_trend > 0 and water_level < 1.5:
            # Time to reach critical level (1.5m)
            hours_to_critical = (1.5 - water_level) / water_level_trend
            result['hours_to_flood'] = max(0, round(hours_to_critical, 1))
        
        # Determine severity level based on probability
        if result['probability'] >= 85:
            result['severity_level'] = 5
            result['severity_text'] = 'Catastrophic'
        elif result['probability'] >= 70:
            result['severity_level'] = 4
            result['severity_text'] = 'Emergency'
        elif result['probability'] >= 55:
            result['severity_level'] = 3
            result['severity_text'] = 'Warning'
        elif result['probability'] >= 40:
            result['severity_level'] = 2
            result['severity_text'] = 'Watch'
        else:
            result['severity_level'] = 1
            result['severity_text'] = 'Advisory'
        
        # Generate impact assessment
        result['impact'] = generate_impact_assessment(result['probability'], result['hours_to_flood'])
        
        # Identify contributing factors
        result['contributing_factors'] = identify_contributing_factors(data, result['probability'])
        
    except Exception as e:
        logger.error(f"Error using time series forecasting for prediction: {str(e)}")
        # Fall back to default model
        return predict_flood_probability(data, classification_algorithm='random_forest')
    
    return result


def generate_impact_assessment(probability, hours_to_flood=None):
    """Generate a descriptive impact assessment based on probability and time to flood
    
    Args:
        probability (float): Flood probability percentage (0-100)
        hours_to_flood (float, optional): Estimated hours until flooding occurs
        
    Returns:
        str: Descriptive impact assessment
    """
    # Determine base impact statement based on probability
    if probability >= 85:
        impact = "Catastrophic flooding expected with severe infrastructure damage and potential loss of life. "
        impact += "Immediate evacuation recommended for all residents in flood-prone areas."
    elif probability >= 70:
        impact = "Severe flooding expected with significant infrastructure impact. "
        impact += "Evacuation recommended for vulnerable areas."
    elif probability >= 55:
        impact = "Moderate flooding likely. Some roads may be impassable and low-lying areas flooded. "
        impact += "Prepare for possible evacuation if conditions worsen."
    elif probability >= 40:
        impact = "Possible minor flooding in low-lying areas. "
        impact += "Monitor updates and prepare emergency supplies."
    else:
        impact = "No significant flooding expected. "
        impact += "Continue to monitor weather conditions."
    
    # Add time-specific information if available
    if hours_to_flood is not None:
        if hours_to_flood < 1:
            impact += f" Flooding is imminent or already occurring."
        elif hours_to_flood < 3:
            impact += f" Flooding expected within the next {hours_to_flood:.1f} hours."
        elif hours_to_flood < 12:
            impact += f" Potential flooding within {hours_to_flood:.1f} hours if conditions persist."
        else:
            impact += f" Be prepared for possible flooding in the next {hours_to_flood:.1f} hours to days."
    
    return impact


def identify_contributing_factors(data, probability):
    """Identify key environmental factors contributing to flood risk
    
    Args:
        data (dict): Dictionary containing environmental conditions
        probability (float): Calculated flood probability percentage
        
    Returns:
        list: Descriptive list of contributing factors
    """
    factors = []
    
    # Only identify factors if data is a dictionary and probability is significant
    if isinstance(data, dict) and probability > 15:
        # Check rainfall - major contributor
        rainfall_24h = data.get('rainfall_24h', 0)
        if isinstance(rainfall_24h, dict) and 'total' in rainfall_24h:
            rainfall_24h = rainfall_24h.get('total', 0)
        
        if rainfall_24h > 50:
            factors.append(f"Extreme rainfall in the last 24 hours ({rainfall_24h:.1f}mm)")
        elif rainfall_24h > 30:
            factors.append(f"Heavy rainfall in the last 24 hours ({rainfall_24h:.1f}mm)")
        elif rainfall_24h > 15 and probability > 30:
            factors.append(f"Moderate rainfall in the last 24 hours ({rainfall_24h:.1f}mm)")
        
        # Check water level - major contributor
        water_level = data.get('water_level', 0)
        if water_level > 1.8:
            factors.append(f"Critically high water level ({water_level:.2f}m)")
        elif water_level > 1.2:
            factors.append(f"Elevated water level ({water_level:.2f}m)")
        elif water_level > 0.8 and probability > 30:
            factors.append(f"Rising water level ({water_level:.2f}m)")
        
        # Check water level change - important trend indicator
        water_level_change = data.get('water_level_change_24h', 0)
        if water_level_change > 0.5:
            factors.append(f"Rapidly rising water level (+{water_level_change:.2f}m in 24h)")
        elif water_level_change > 0.2:
            factors.append(f"Steadily rising water level (+{water_level_change:.2f}m in 24h)")
        
        # Check soil saturation - affects water absorption
        soil_saturation = data.get('soil_saturation', 0)
        if soil_saturation > 90:
            factors.append("Extremely saturated soil severely limiting water absorption")
        elif soil_saturation > 75:
            factors.append("Highly saturated soil limiting water absorption")
        elif soil_saturation > 60 and probability > 40:
            factors.append("Moderately saturated soil reducing water absorption")
        
        # Check historical context - indicates geographical vulnerability
        historical_floods = data.get('historical_floods_count', 0)
        if historical_floods > 5:
            factors.append("Area has history of frequent severe flooding")
        elif historical_floods > 2:
            factors.append("Area has experienced multiple floods in the past")
        
        # Check elevation - low elevation is vulnerable
        elevation = data.get('elevation', None)
        if elevation is not None and elevation < 10 and probability > 30:
            factors.append(f"Low-lying area at {elevation}m elevation")
    
    # If no specific factors identified but probability is significant
    if not factors and probability > 30:
        factors.append("Multiple minor factors contributing to flood risk")
    
    return factors


def get_affected_barangays(municipality_id=None, probability_threshold=50, 
                        classification_algorithm=DEFAULT_CLASSIFICATION_ALGORITHM,
                        compare_algorithms=False):
    """Get list of barangays likely to be affected by flooding.
    
    Args:
        municipality_id (int, optional): Filter by municipality ID
        probability_threshold (int, optional): Minimum flood probability threshold
        classification_algorithm (str): Algorithm to use for classification
        compare_algorithms (bool): If True, run predictions with multiple algorithms for comparison
        
    Returns:
        list: Barangays with flood risk above threshold
    """
    # This would typically query the database for barangays and their risk factors
    # For now, we'll return a simulated list based on the parameters
    
    # In a real implementation, you would:
    # 1. Query the database for barangays (filtered by municipality_id if provided)
    # 2. For each barangay, collect its relevant sensor data
    # 3. Run the prediction model for each barangay
    # 4. Filter the results by probability_threshold
    # 5. Return the list of affected barangays with their risk assessment
    
    from core.models import Barangay
    from django.db.models import Q
    
    # Start with a base query for barangays
    barangay_query = Barangay.objects.all()
    
    # Filter by municipality if provided
    if municipality_id is not None:
        barangay_query = barangay_query.filter(municipality_id=municipality_id)
    
    # Get all barangays
    barangays = list(barangay_query)
    affected_barangays = []
    
    # Algorithms to use for prediction
    algorithms = ['random_forest']
    if compare_algorithms and ADVANCED_ALGORITHMS_AVAILABLE:
        algorithms = ['random_forest', 'gradient_boosting', 'svm']
        if TENSORFLOW_AVAILABLE:
            algorithms.append('lstm')
    elif classification_algorithm != 'random_forest':
        algorithms = [classification_algorithm]
    
    # For each barangay, make a prediction
    for barangay in barangays:
        # Get the latest sensor data for this barangay
        # (In a real implementation, you would query the sensor data related to this barangay)
        
        # For now, generate some test data based on barangay ID
        # This ensures deterministic but varied results per barangay
        barangay_data = {
            'rainfall_24h': (barangay.id * 3.5) % 50,  # 0-50mm
            'water_level': ((barangay.id * 2.7) % 20) / 10,  # 0-2.0m
            'elevation': ((barangay.id * 4.1) % 100) + 10,  # 10-110m
            'soil_saturation': (barangay.id * 1.8) % 100,  # 0-100%
            'historical_floods_count': (barangay.id * 1.3) % 5  # 0-4 past floods
        }
        
        # Make predictions with the specified algorithm(s)
        predictions = {}
        best_prediction = None
        
        for algo in algorithms:
            try:
                pred = predict_flood_probability(barangay_data, classification_algorithm=algo)
                predictions[algo] = pred
                
                # For single algorithm mode, this is the only prediction
                # For comparison mode, we'll use the highest probability prediction
                if best_prediction is None or pred['probability'] > best_prediction['probability']:
                    best_prediction = pred
            except Exception as e:
                logger.error(f"Error making prediction with {algo} algorithm: {str(e)}")
        
        # Use the best prediction (highest probability)
        prediction = best_prediction
        
        # Skip if we couldn't make any predictions
        if prediction is None:
            logger.warning(f"Could not make predictions for barangay {barangay.name} with any algorithm")
            continue
        
        # Include barangay if probability exceeds threshold
        if prediction['probability'] >= probability_threshold:
            barangay_info = {
                'id': barangay.id,
                'name': barangay.name,
                'population': barangay.population,
                'risk_level': "High" if prediction['probability'] >= 70 else 
                             "Moderate" if prediction['probability'] >= 50 else "Low",
                'probability': prediction['probability'],
                'model_used': prediction['model_used'],
                'evacuation_centers': (barangay.id % 3) + 1  # 1-3 evacuation centers
            }
            
            # If comparing algorithms, include all predictions
            if compare_algorithms and len(predictions) > 1:
                barangay_info['algorithm_comparison'] = {
                    algo: {'probability': pred['probability'], 'severity_level': pred['severity_level']}
                    for algo, pred in predictions.items()
                }
            
            affected_barangays.append(barangay_info)
    
    # Sort by risk (highest first)
    affected_barangays.sort(key=lambda x: x['probability'], reverse=True)
    
    return affected_barangays

