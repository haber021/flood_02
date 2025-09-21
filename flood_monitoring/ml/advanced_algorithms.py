"""Advanced Machine Learning Algorithms for Flood Prediction

This module contains implementations of various machine learning algorithms for enhancing
flood prediction accuracy, including ensemble methods, neural networks, time series analysis,
and spatial analysis techniques.
"""

import numpy as np
import pandas as pd
import joblib
import os
import logging
from datetime import datetime, timedelta

# Scikit-learn imports
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import mean_squared_error, classification_report
from sklearn.model_selection import train_test_split, GridSearchCV

# Time series imports
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Neural network imports (if tensorflow is installed)
try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Dense, LSTM, Dropout
    from tensorflow.keras.callbacks import EarlyStopping
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)

# Constants
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data/models')


class GradientBoostingFloodPredictor:
    """Gradient Boosting Machine for flood prediction
    
    This model uses gradient boosting to classify flood risk using multiple features
    including rainfall, water level, and soil saturation.
    """
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.param_grid = {
            'n_estimators': [100, 200, 300],
            'learning_rate': [0.01, 0.1, 0.2],
            'max_depth': [3, 4, 5],
            'min_samples_split': [2, 5, 10],
            'subsample': [0.8, 0.9, 1.0]
        }
        
    def train(self, X, y):
        """Train the gradient boosting model with hyperparameter tuning"""
        logger.info("Training gradient boosting model with grid search...")
        X_scaled = self.scaler.fit_transform(X)
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        
        # Use GridSearchCV for hyperparameter tuning
        grid_search = GridSearchCV(GradientBoostingClassifier(), 
                                  self.param_grid, 
                                  cv=5, 
                                  scoring='f1',
                                  n_jobs=-1)
        grid_search.fit(X_train, y_train)
        
        # Get the best model
        self.model = grid_search.best_estimator_
        logger.info(f"Best parameters found: {grid_search.best_params_}")
        
        # Evaluate the model
        y_pred = self.model.predict(X_test)
        
    def predict(self, X):
        """Predict flood risk using the trained model"""
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        
        # Scale input data
        X_scaled = self.scaler.transform(X)
        
        # Make predictions
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)[:, 1]  # Probability of positive class
        
        return predictions, probabilities
    
    def save(self, model_path=None):
        """Save the trained model and scaler to disk"""
        if self.model is None:
            raise ValueError("Model not trained yet. Cannot save.")
        
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, 'gbm_flood_model.joblib')
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Save model and scaler together
        joblib.dump({'model': self.model, 'scaler': self.scaler}, model_path)
        logger.info(f"Saved GBM model to {model_path}")
    
    def load(self, model_path=None):
        """Load the model and scaler from disk"""
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, 'gbm_flood_model.joblib')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Load model and scaler
        saved_data = joblib.load(model_path)
        self.model = saved_data['model']
        self.scaler = saved_data['scaler']
        logger.info(f"Loaded GBM model from {model_path}")


class SVMFloodPredictor:
    """Support Vector Machine for flood prediction
    
    Uses SVM with RBF kernel to classify flood risk based on environmental factors.
    """
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.param_grid = {
            'C': [0.1, 1, 10, 100],
            'gamma': ['scale', 'auto', 0.01, 0.1, 1],
            'kernel': ['rbf', 'poly'],
            'probability': [True]
        }
    
    def train(self, X, y):
        """Train the SVM model with hyperparameter tuning"""
        logger.info("Training SVM model with grid search...")
        X_scaled = self.scaler.fit_transform(X)
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        
        # Use GridSearchCV for hyperparameter tuning
        # Note: smaller subset for parameter search due to SVM training time
        grid_search = GridSearchCV(SVC(probability=True), 
                                  self.param_grid, 
                                  cv=3, 
                                  scoring='f1',
                                  n_jobs=-1)
        grid_search.fit(X_train, y_train)
        
        # Get the best model
        self.model = grid_search.best_estimator_
        logger.info(f"Best parameters found: {grid_search.best_params_}")
        
        # Evaluate the model
        y_pred = self.model.predict(X_test)
        logger.info(f"Classification report:\n{classification_report(y_test, y_pred)}")
    
    def predict(self, X):
        """Predict flood risk using the trained SVM model"""
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        
        # Scale input data
        X_scaled = self.scaler.transform(X)
        
        # Make predictions
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)[:, 1]  # Probability of positive class
        
        return predictions, probabilities
    
    def save(self, model_path=None):
        """Save the trained model and scaler to disk"""
        if self.model is None:
            raise ValueError("Model not trained yet. Cannot save.")
        
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, 'svm_flood_model.joblib')
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Save model and scaler together
        joblib.dump({'model': self.model, 'scaler': self.scaler}, model_path)
        logger.info(f"Saved SVM model to {model_path}")
    
    def load(self, model_path=None):
        """Load the model and scaler from disk"""
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, 'svm_flood_model.joblib')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Load model and scaler
        saved_data = joblib.load(model_path)
        self.model = saved_data['model']
        self.scaler = saved_data['scaler']
        logger.info(f"Loaded SVM model from {model_path}")


class TimeSeriesForecaster:
    """Time series forecasting for flood prediction
    
    This class implements ARIMA and Exponential Smoothing methods for time-series
    analysis of flood-related data such as rainfall and water levels.
    """
    
    def __init__(self, method='arima'):
        """Initialize with specified forecasting method
        
        Args:
            method (str): Either 'arima' or 'exponential_smoothing'
        """
        self.method = method
        self.model = None
        self.data_frequency = 'D'  # Default to daily data
        self.last_trained_date = None
        self.feature_name = None
    
    def train(self, time_series_data, feature_name, date_column='date'):
        """Train the time series model
        
        Args:
            time_series_data (pd.DataFrame): DataFrame with date and feature columns
            feature_name (str): Name of the feature column to forecast
            date_column (str): Name of the date column
        """
        logger.info(f"Training {self.method} model for {feature_name}")
        self.feature_name = feature_name
        
        # Ensure data is sorted by date
        df = time_series_data.sort_values(by=date_column).copy()
        
        # Convert date to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            df[date_column] = pd.to_datetime(df[date_column])
        
        # Set date as index
        df.set_index(date_column, inplace=True)
        
        # Determine data frequency
        if len(df) > 1:
            # Calculate the most common time delta
            deltas = df.index.to_series().diff().dropna()
            if len(deltas) > 0:
                most_common_delta = deltas.mode()[0]
                # Convert to frequency string
                if most_common_delta <= pd.Timedelta(hours=1):
                    self.data_frequency = 'H'
                elif most_common_delta <= pd.Timedelta(days=1):
                    self.data_frequency = 'D'
                elif most_common_delta <= pd.Timedelta(weeks=1):
                    self.data_frequency = 'W'
                else:
                    self.data_frequency = 'M'
        
        # Get the time series data
        series = df[feature_name]
        
        # Train the model based on method
        if self.method == 'arima':
            # Simple auto ARIMA - in production would use more sophisticated parameter selection
            self.model = ARIMA(series, order=(1, 1, 1))
            self.model = self.model.fit()
        elif self.method == 'exponential_smoothing':
            # Exponential smoothing with trend
            self.model = ExponentialSmoothing(series, trend='add', seasonal=None)
            self.model = self.model.fit()
        else:
            raise ValueError(f"Unknown forecasting method: {self.method}")
        
        self.last_trained_date = df.index.max()
        logger.info(f"Time series model trained on data up to {self.last_trained_date}")
    
    def forecast(self, steps=24):
        """Generate forecast for specified number of steps ahead
        
        Args:
            steps (int): Number of time periods to forecast
            
        Returns:
            pd.Series: Forecasted values with date index
        """
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        
        if self.method == 'arima':
            forecast_result = self.model.forecast(steps=steps)
        elif self.method == 'exponential_smoothing':
            forecast_result = self.model.forecast(steps=steps)
        
        # Generate date index for the forecast
        if self.data_frequency == 'H':
            forecast_dates = pd.date_range(start=self.last_trained_date, periods=steps+1, freq='H')[1:]
        elif self.data_frequency == 'D':
            forecast_dates = pd.date_range(start=self.last_trained_date, periods=steps+1, freq='D')[1:]
        elif self.data_frequency == 'W':
            forecast_dates = pd.date_range(start=self.last_trained_date, periods=steps+1, freq='W')[1:]
        else:  # Monthly
            forecast_dates = pd.date_range(start=self.last_trained_date, periods=steps+1, freq='M')[1:]
        
        # Return forecast as Series with date index
        return pd.Series(forecast_result, index=forecast_dates, name=self.feature_name)
    
    def save(self, model_path=None):
        """Save the trained model to disk"""
        if self.model is None:
            raise ValueError("Model not trained yet. Cannot save.")
        
        if model_path is None:
            filename = f"{self.method}_{self.feature_name}_model.joblib"
            model_path = os.path.join(MODEL_DIR, filename)
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Save model parameters
        model_data = {
            'model': self.model,
            'method': self.method,
            'data_frequency': self.data_frequency,
            'last_trained_date': self.last_trained_date,
            'feature_name': self.feature_name
        }
        
        joblib.dump(model_data, model_path)
        logger.info(f"Saved {self.method} model for {self.feature_name} to {model_path}")
    
    def load(self, model_path=None):
        """Load the model from disk"""
        if model_path is None and self.feature_name is not None:
            filename = f"{self.method}_{self.feature_name}_model.joblib"
            model_path = os.path.join(MODEL_DIR, filename)
        elif model_path is None:
            raise ValueError("Either model_path or feature_name must be provided")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Load model parameters
        model_data = joblib.load(model_path)
        self.model = model_data['model']
        self.method = model_data['method']
        self.data_frequency = model_data['data_frequency']
        self.last_trained_date = model_data['last_trained_date']
        self.feature_name = model_data['feature_name']
        
        logger.info(f"Loaded {self.method} model for {self.feature_name} from {model_path}")


class SpatialAnalyzer:
    """Spatial analysis for flood risk using Inverse Distance Weighting and other methods
    
    This class implements spatial analysis techniques for flood risk assessment based on
    location data and environmental factors.
    """
    
    def __init__(self, method='idw'):
        """Initialize with specified spatial analysis method
        
        Args:
            method (str): 'idw' for Inverse Distance Weighting or 'kriging' for Kriging
        """
        self.method = method
        self.locations = None
        self.values = None
        self.trained = False
    
    def train(self, locations, values):
        """Train the spatial model with known data points
        
        Args:
            locations (np.array): Array of (latitude, longitude) coordinates
            values (np.array): Array of corresponding values at those locations
        """
        logger.info(f"Training spatial model using {self.method} with {len(locations)} points")
        
        if len(locations) != len(values):
            raise ValueError("Locations and values must have the same length")
        
        self.locations = np.array(locations)
        self.values = np.array(values)
        self.trained = True
        
        logger.info("Spatial model training complete")
    
    def predict(self, query_locations, p=2):
        """Predict values at query locations using spatial interpolation
        
        Args:
            query_locations (np.array): Array of (latitude, longitude) coordinates to predict
            p (int): Power parameter for IDW (default: 2)
            
        Returns:
            np.array: Predicted values at query locations
        """
        if not self.trained:
            raise ValueError("Model not trained yet. Call train() first.")
        
        query_locations = np.array(query_locations)
        predictions = np.zeros(len(query_locations))
        
        # IDW implementation
        if self.method == 'idw':
            for i, query_point in enumerate(query_locations):
                # Calculate distances from query point to all known points
                distances = np.sqrt(np.sum((self.locations - query_point)**2, axis=1))
                
                # Handle the case where a query point exactly matches a known point
                if np.any(distances == 0):
                    exact_match_idx = np.where(distances == 0)[0][0]
                    predictions[i] = self.values[exact_match_idx]
                    continue
                
                # Calculate weights using inverse distance
                weights = 1.0 / (distances ** p)
                weights = weights / np.sum(weights)  # Normalize weights
                
                # Calculate weighted average
                predictions[i] = np.sum(self.values * weights)
        
        elif self.method == 'kriging':
            # Simplified kriging implementation (in a full implementation, you'd use a library like PyKrige)
            logger.warning("Using simplified kriging implementation")
            
            # Simple Kriging implementation (this is a very simplified version)
            for i, query_point in enumerate(query_locations):
                # Calculate distances
                distances = np.sqrt(np.sum((self.locations - query_point)**2, axis=1))
                
                # Use exponential variogram model
                range_param = np.mean(distances) / 3
                sill = np.var(self.values)
                nugget = 0.1 * sill
                
                # Calculate semi-variance using exponential model
                semi_variance = nugget + sill * (1 - np.exp(-distances / range_param))
                
                # Avoid division by zero
                semi_variance[semi_variance < 1e-10] = 1e-10
                
                # Calculate weights (inverting the semi-variance matrix is complex, simplified here)
                weights = 1.0 / semi_variance
                weights = weights / np.sum(weights)  # Normalize
                
                # Weighted prediction
                predictions[i] = np.sum(self.values * weights)
        
        else:
            raise ValueError(f"Unknown spatial analysis method: {self.method}")
        
        return predictions
    
    def save(self, model_path=None):
        """Save the trained spatial model to disk"""
        if not self.trained:
            raise ValueError("Model not trained yet. Cannot save.")
        
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, f"spatial_{self.method}_model.joblib")
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Save model data
        model_data = {
            'method': self.method,
            'locations': self.locations,
            'values': self.values,
            'trained': self.trained
        }
        
        joblib.dump(model_data, model_path)
        logger.info(f"Saved spatial model using {self.method} to {model_path}")
    
    def load(self, model_path=None):
        """Load the spatial model from disk"""
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, f"spatial_{self.method}_model.joblib")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Load model data
        model_data = joblib.load(model_path)
        self.method = model_data['method']
        self.locations = model_data['locations']
        self.values = model_data['values']
        self.trained = model_data['trained']
        
        logger.info(f"Loaded spatial model using {self.method} from {model_path}")


class LSTMFloodPredictor:
    """Long Short-Term Memory Neural Network for flood prediction
    
    This model uses LSTM layers to capture temporal patterns in flood-related data.
    It requires TensorFlow to be installed.
    """
    
    def __init__(self):
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTMFloodPredictor")
        
        from tensorflow.keras.models import Sequential, load_model
        from tensorflow.keras.layers import Dense, LSTM, Dropout
        
        self.model = None
        self.scaler = StandardScaler()
        self.sequence_length = None
        self.features = None
        self.trained = False
    
    def _create_sequences(self, df, target_col, sequence_length):
        """Create sequences for LSTM input
        
        Args:
            df (pd.DataFrame): DataFrame with features and target
            target_col (str): Name of target column
            sequence_length (int): Number of time steps to use
            
        Returns:
            tuple: (X, y) where X is sequence data and y is targets
        """
        X, y = [], []
        data = df.values
        
        for i in range(len(data) - sequence_length):
            X.append(data[i:(i + sequence_length), :-1])  # All columns except target
            y.append(data[i + sequence_length - 1, -1])   # Target column
        
        return np.array(X), np.array(y)
    
    def train(self, data, target_col, sequence_length=10, epochs=50, batch_size=32):
        """Train the LSTM model
        
        Args:
            data (pd.DataFrame): DataFrame with features and target column
            target_col (str): Name of target column
            sequence_length (int): Number of time steps to use as input
            epochs (int): Number of training epochs
            batch_size (int): Batch size for training
        """
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTMFloodPredictor")
        
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Dense, LSTM, Dropout
        from tensorflow.keras.callbacks import EarlyStopping
        
        logger.info(f"Training LSTM model with sequence length {sequence_length}")
        
        # Save for prediction
        self.sequence_length = sequence_length
        self.features = [col for col in data.columns if col != target_col]
        
        # Move target column to end if it's not already there
        if data.columns[-1] != target_col:
            cols = [col for col in data.columns if col != target_col] + [target_col]
            data = data[cols]
        
        # Scale the data
        data_values = data.values
        self.scaler.fit(data_values)
        scaled_data = self.scaler.transform(data_values)
        
        # Create DataFrame with scaled values
        scaled_df = pd.DataFrame(scaled_data, columns=data.columns)
        
        # Create sequences
        X, y = self._create_sequences(scaled_df, target_col, sequence_length)
        
        # Reshape for LSTM [samples, time steps, features]
        n_features = X.shape[2]
        
        # Split into train/test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Build LSTM model
        self.model = Sequential()
        self.model.add(LSTM(50, activation='relu', return_sequences=True, 
                           input_shape=(sequence_length, n_features)))
        self.model.add(Dropout(0.2))
        self.model.add(LSTM(50, activation='relu'))
        self.model.add(Dropout(0.2))
        self.model.add(Dense(1, activation='sigmoid'))
        
        # Compile
        self.model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        
        # Early stopping
        early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
        
        # Fit the model
        self.model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size,
                      validation_data=(X_test, y_test), callbacks=[early_stopping], verbose=1)
        
        # Evaluate
        loss, accuracy = self.model.evaluate(X_test, y_test)
        logger.info(f"LSTM Test accuracy: {accuracy:.4f}")
        
        self.trained = True
    
    def predict(self, X):
        """Predict flood probability using the trained LSTM model
        
        Args:
            X (pd.DataFrame or np.array): Input features
            
        Returns:
            tuple: (predictions, probabilities)
        """
        if not self.trained or self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        
        # If DataFrame, extract values and ensure features match
        if isinstance(X, pd.DataFrame):
            # Check features
            missing_features = set(self.features) - set(X.columns)
            if missing_features:
                raise ValueError(f"Missing features in input data: {missing_features}")
            
            # Extract values for required features
            X = X[self.features].values
        
        # Scale the data
        X_scaled = self.scaler.transform(X)
        
        # Create sequences (assumes X is already in time order)
        sequences = []
        for i in range(len(X_scaled) - self.sequence_length + 1):
            sequences.append(X_scaled[i:i+self.sequence_length])
        
        if not sequences:  # Not enough data for a sequence
            raise ValueError(f"Need at least {self.sequence_length} samples for prediction")
        
        # Convert to numpy array
        X_seq = np.array(sequences)
        
        # Predict
        probabilities = self.model.predict(X_seq)
        predictions = (probabilities > 0.5).astype(int)
        
        return predictions.flatten(), probabilities.flatten()
    
    def save(self, model_path=None):
        """Save the trained LSTM model to disk"""
        if not self.trained or self.model is None:
            raise ValueError("Model not trained yet. Cannot save.")
        
        if model_path is None:
            model_dir = os.path.join(MODEL_DIR, 'lstm_model')
            os.makedirs(model_dir, exist_ok=True)
            model_path = os.path.join(model_dir, 'lstm_model.h5')
            metadata_path = os.path.join(model_dir, 'lstm_metadata.joblib')
        else:
            model_dir = os.path.dirname(model_path)
            os.makedirs(model_dir, exist_ok=True)
            metadata_path = os.path.join(model_dir, 'lstm_metadata.joblib')
        
        # Save Keras model
        self.model.save(model_path)
        
        # Save metadata
        metadata = {
            'sequence_length': self.sequence_length,
            'features': self.features,
            'scaler': self.scaler
        }
        joblib.dump(metadata, metadata_path)
        
        logger.info(f"Saved LSTM model to {model_path} and metadata to {metadata_path}")
    
    def load(self, model_path=None):
        """Load the LSTM model from disk"""
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTMFloodPredictor")
        
        from tensorflow.keras.models import load_model
        
        if model_path is None:
            model_dir = os.path.join(MODEL_DIR, 'lstm_model')
            model_path = os.path.join(model_dir, 'lstm_model.h5')
            metadata_path = os.path.join(model_dir, 'lstm_metadata.joblib')
        else:
            model_dir = os.path.dirname(model_path)
            metadata_path = os.path.join(model_dir, 'lstm_metadata.joblib')
        
        if not os.path.exists(model_path) or not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Model files not found: {model_path} or {metadata_path}")
        
        # Load Keras model
        self.model = load_model(model_path)
        
        # Load metadata
        metadata = joblib.load(metadata_path)
        self.sequence_length = metadata['sequence_length']
        self.features = metadata['features']
        self.scaler = metadata['scaler']
        self.trained = True
        
        logger.info(f"Loaded LSTM model from {model_path} and metadata from {metadata_path}")


class MultiCriteriaDecisionAnalyzer:
    """Multi-criteria decision analysis for flood risk assessment
    
    This class implements Multi-Criteria Decision Analysis (MCDA) methods for
    combining multiple risk factors with different weights to produce a comprehensive
    flood risk assessment.
    """
    
    def __init__(self):
        # Default criteria and weights
        self.criteria = {
            'rainfall_intensity': 0.25,
            'water_level': 0.25,
            'soil_saturation': 0.15,
            'elevation': 0.15,
            'historical_floods': 0.10,
            'proximity_to_water': 0.10
        }
        
        # Thresholds for risk levels
        self.thresholds = {
            'high_risk': 0.7,
            'medium_risk': 0.4,
            'low_risk': 0.2
        }
    
    def set_criteria(self, criteria_weights):
        """Set custom criteria and weights
        
        Args:
            criteria_weights (dict): Dictionary of criteria names and weights
        """
        # Validate weights sum to 1
        total_weight = sum(criteria_weights.values())
        if abs(total_weight - 1.0) > 0.001:  # Allow small floating point error
            logger.warning(f"Criteria weights sum to {total_weight}, not 1.0. Normalizing.")
            # Normalize weights
            for key in criteria_weights:
                criteria_weights[key] /= total_weight
        
        self.criteria = criteria_weights
        logger.info(f"Set custom criteria weights: {self.criteria}")
    
    def set_thresholds(self, thresholds):
        """Set custom thresholds for risk levels
        
        Args:
            thresholds (dict): Dictionary with keys 'high_risk', 'medium_risk', 'low_risk'
        """
        # Validate thresholds are in descending order
        if not (thresholds['high_risk'] > thresholds['medium_risk'] > thresholds['low_risk']):
            raise ValueError("Thresholds must be in descending order: high_risk > medium_risk > low_risk")
        
        self.thresholds = thresholds
        logger.info(f"Set custom risk thresholds: {self.thresholds}")
    
    def normalize_factor(self, value, min_val, max_val, invert=False):
        """Normalize a factor to 0-1 scale
        
        Args:
            value (float): The value to normalize
            min_val (float): Minimum possible value
            max_val (float): Maximum possible value
            invert (bool): If True, invert the scale (1 = low risk, 0 = high risk)
            
        Returns:
            float: Normalized value (0-1)
        """
        if max_val == min_val:
            normalized = 0.5  # Default if range is zero
        else:
            normalized = (value - min_val) / (max_val - min_val)
        
        # Clamp to 0-1 range
        normalized = max(0, min(1, normalized))
        
        # Invert if needed (e.g., for elevation where higher is better)
        if invert:
            normalized = 1 - normalized
        
        return normalized
    
    def analyze(self, factors):
        """Perform multi-criteria analysis to assess flood risk
        
        Args:
            factors (dict): Dictionary of factor values keyed by criterion name
            
        Returns:
            dict: Risk assessment results including score and risk level
        """
        # Validate that all required criteria are present
        missing_criteria = set(self.criteria.keys()) - set(factors.keys())
        if missing_criteria:
            raise ValueError(f"Missing required criteria: {missing_criteria}")
        
        # Factor ranges for normalization (these would ideally be determined from historical data)
        factor_ranges = {
            'rainfall_intensity': {'min': 0, 'max': 100, 'invert': False},  # mm
            'water_level': {'min': 0, 'max': 5, 'invert': False},  # meters
            'soil_saturation': {'min': 0, 'max': 100, 'invert': False},  # percent
            'elevation': {'min': 0, 'max': 200, 'invert': True},  # meters
            'historical_floods': {'min': 0, 'max': 10, 'invert': False},  # count
            'proximity_to_water': {'min': 0, 'max': 1000, 'invert': True}  # meters
        }
        
        # Normalize factors
        normalized_factors = {}
        for criterion, value in factors.items():
            if criterion in factor_ranges:
                range_info = factor_ranges[criterion]
                normalized_factors[criterion] = self.normalize_factor(
                    value, range_info['min'], range_info['max'], range_info['invert']
                )
            else:
                # For criteria not in predefined ranges, assume 0-1 already normalized
                normalized_factors[criterion] = value
        
        # Calculate weighted score
        weighted_score = 0
        for criterion, weight in self.criteria.items():
            if criterion in normalized_factors:
                weighted_score += normalized_factors[criterion] * weight
        
        # Determine risk level
        if weighted_score >= self.thresholds['high_risk']:
            risk_level = 'high'
            numeric_risk = 3
        elif weighted_score >= self.thresholds['medium_risk']:
            risk_level = 'medium'
            numeric_risk = 2
        elif weighted_score >= self.thresholds['low_risk']:
            risk_level = 'low'
            numeric_risk = 1
        else:
            risk_level = 'minimal'
            numeric_risk = 0
        
        return {
            'score': weighted_score,
            'risk_level': risk_level,
            'numeric_risk': numeric_risk,
            'normalized_factors': normalized_factors,
            'thresholds': self.thresholds
        }
    
    def save(self, model_path=None):
        """Save the MCDA model configuration"""
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, 'mcda_model.joblib')
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Save configuration
        config = {
            'criteria': self.criteria,
            'thresholds': self.thresholds
        }
        
        joblib.dump(config, model_path)
        logger.info(f"Saved MCDA model configuration to {model_path}")
    
    def load(self, model_path=None):
        """Load MCDA model configuration"""
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, 'mcda_model.joblib')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Load configuration
        config = joblib.load(model_path)
        self.criteria = config['criteria']
        self.thresholds = config['thresholds']
        
        logger.info(f"Loaded MCDA model configuration from {model_path}")


class DynamicTimeWarpingAnalyzer:
    """Dynamic Time Warping for comparing flood event patterns
    
    This class uses Dynamic Time Warping (DTW) to compare current environmental
    patterns with historical flood events to identify similar situations.
    """
    
    def __init__(self):
        self.historical_patterns = []  # List of (pattern, metadata) tuples
    
    def add_pattern(self, time_series, metadata=None):
        """Add a historical pattern for comparison
        
        Args:
            time_series (array-like): Time series data representing a pattern
            metadata (dict): Associated metadata (e.g., 'resulted_in_flood', 'severity')
        """
        self.historical_patterns.append((np.array(time_series), metadata or {}))
    
    def dtw_distance(self, s1, s2, window=None):
        """Compute Dynamic Time Warping distance between two sequences
        
        Args:
            s1, s2 (array-like): Sequences to compare
            window (int): Sakoe-Chiba band width (None for no constraint)
            
        Returns:
            float: DTW distance
        """
        # Convert to numpy arrays
        s1 = np.array(s1)
        s2 = np.array(s2)
        
        # Get sequence lengths
        n, m = len(s1), len(s2)
        
        # If window is not set, use the larger sequence length
        if window is None:
            window = max(n, m)
        
        # Initialize cost matrix
        dtw_matrix = np.full((n+1, m+1), np.inf)
        dtw_matrix[0, 0] = 0
        
        # Fill the cost matrix
        for i in range(1, n+1):
            for j in range(max(1, i-window), min(m+1, i+window+1)):
                cost = (s1[i-1] - s2[j-1])**2
                dtw_matrix[i, j] = cost + min(
                    dtw_matrix[i-1, j],      # Insertion
                    dtw_matrix[i, j-1],      # Deletion
                    dtw_matrix[i-1, j-1]     # Match
                )
        
        return np.sqrt(dtw_matrix[n, m])
    
    def find_similar_patterns(self, current_pattern, top_k=3):
        """Find historical patterns most similar to current pattern
        
        Args:
            current_pattern (array-like): Current time series data
            top_k (int): Number of most similar patterns to return
            
        Returns:
            list: List of (distance, pattern, metadata) tuples sorted by similarity
        """
        if not self.historical_patterns:
            return []
        
        # Convert to numpy array if not already
        current_pattern = np.array(current_pattern)
        
        # Calculate distance to each historical pattern
        results = []
        for i, (pattern, metadata) in enumerate(self.historical_patterns):
            try:
                # Z-normalize patterns for better comparison
                pattern_norm = (pattern - np.mean(pattern)) / (np.std(pattern) + 1e-8)
                current_norm = (current_pattern - np.mean(current_pattern)) / (np.std(current_pattern) + 1e-8)
                
                distance = self.dtw_distance(current_norm, pattern_norm)
                results.append((distance, pattern, metadata))
            except Exception as e:
                logger.warning(f"Error computing DTW for pattern {i}: {str(e)}")
        
        # Sort by distance (smaller = more similar)
        results.sort(key=lambda x: x[0])
        
        # Return top k results
        return results[:top_k]
    
    def save(self, model_path=None):
        """Save the DTW analyzer with historical patterns"""
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, 'dtw_analyzer.joblib')
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Save historical patterns
        joblib.dump(self.historical_patterns, model_path)
        logger.info(f"Saved DTW analyzer with {len(self.historical_patterns)} patterns to {model_path}")
    
    def load(self, model_path=None):
        """Load DTW analyzer with historical patterns"""
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, 'dtw_analyzer.joblib')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Load historical patterns
        self.historical_patterns = joblib.load(model_path)
        logger.info(f"Loaded DTW analyzer with {len(self.historical_patterns)} patterns from {model_path}")
        logger.info("\nGradient Boosting model evaluation:")
        logger.info(classification_report(y_test, y_pred))
        
        return self
    
    def predict(self, features):
        """Make flood predictions using the trained model"""
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        
        # Scale features
        features_scaled = self.scaler.transform(features)
        
        # Make prediction
        prediction = self.model.predict(features_scaled)
        probability = self.model.predict_proba(features_scaled)[:, 1]  # Probability of positive class
        
        return prediction, probability
    
    def save(self, filename='gbm_flood_model.joblib'):
        """Save the model to disk"""
        if self.model is None:
            raise ValueError("No model to save. Train the model first.")
            
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
            
        model_path = os.path.join(MODEL_DIR, filename)
        scaler_path = os.path.join(MODEL_DIR, 'gbm_scaler.joblib')
        
        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"Model saved to {model_path}")
        
        return model_path
    
    def load(self, filename='gbm_flood_model.joblib'):
        """Load the model from disk"""
        model_path = os.path.join(MODEL_DIR, filename)
        scaler_path = os.path.join(MODEL_DIR, 'gbm_scaler.joblib')
        
        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            raise FileNotFoundError(f"Model or scaler file not found at {model_path}")
            
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        logger.info(f"Model loaded from {model_path}")
        
        return self


class SVMFloodPredictor:
    """Support Vector Machine for flood classification
    
    This model uses SVM for binary classification of flood events.
    """
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.param_grid = {
            'C': [0.1, 1, 10, 100],
            'gamma': ['scale', 'auto', 0.1, 0.01],
            'kernel': ['rbf', 'poly', 'sigmoid']
        }
        
    def train(self, X, y):
        """Train the SVM model with hyperparameter tuning"""
        logger.info("Training SVM model with grid search...")
        X_scaled = self.scaler.fit_transform(X)
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        
        # Use GridSearchCV for hyperparameter tuning
        grid_search = GridSearchCV(SVC(probability=True), 
                                  self.param_grid, 
                                  cv=5, 
                                  scoring='f1',
                                  n_jobs=-1)
        grid_search.fit(X_train, y_train)
        
        # Get the best model
        self.model = grid_search.best_estimator_
        logger.info(f"Best parameters found: {grid_search.best_params_}")
        
        # Evaluate the model
        y_pred = self.model.predict(X_test)
        logger.info("\nSVM model evaluation:")
        logger.info(classification_report(y_test, y_pred))
        
        return self
    
    def predict(self, features):
        """Make flood predictions using the trained model"""
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        
        # Scale features
        features_scaled = self.scaler.transform(features)
        
        # Make prediction
        prediction = self.model.predict(features_scaled)
        probability = self.model.predict_proba(features_scaled)[:, 1]  # Probability of positive class
        
        return prediction, probability
    
    def save(self, filename='svm_flood_model.joblib'):
        """Save the model to disk"""
        if self.model is None:
            raise ValueError("No model to save. Train the model first.")
            
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
            
        model_path = os.path.join(MODEL_DIR, filename)
        scaler_path = os.path.join(MODEL_DIR, 'svm_scaler.joblib')
        
        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"Model saved to {model_path}")
        
        return model_path
    
    def load(self, filename='svm_flood_model.joblib'):
        """Load the model from disk"""
        model_path = os.path.join(MODEL_DIR, filename)
        scaler_path = os.path.join(MODEL_DIR, 'svm_scaler.joblib')
        
        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            raise FileNotFoundError(f"Model or scaler file not found at {model_path}")
            
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        logger.info(f"Model loaded from {model_path}")
        
        return self


class TimeSeriesForecaster:
    """Time Series Forecasting for flood prediction
    
    This class implements ARIMA and Exponential Smoothing for forecasting 
    time-dependent variables like water level and rainfall.
    """
    
    def __init__(self, method='arima'):
        """Initialize the time series forecaster
        
        Args:
            method (str): The forecasting method to use ('arima' or 'ets')
        """
        self.method = method.lower()
        self.model = None
        self.history = None
        self.frequency = None
        
        if self.method not in ['arima', 'ets']:
            raise ValueError("Method must be either 'arima' or 'ets'")
    
    def train(self, time_series, date_column, value_column, frequency='D'):
        """Train the time series model
        
        Args:
            time_series (pd.DataFrame): DataFrame containing time series data
            date_column (str): Name of the date column
            value_column (str): Name of the value column
            frequency (str): Frequency of the time series ('D' for daily, 'H' for hourly, etc.)
        """
        logger.info(f"Training {self.method.upper()} time series model...")
        
        # Convert to time series format
        df = time_series.copy()
        df[date_column] = pd.to_datetime(df[date_column])
        df = df.sort_values(date_column)
        
        # Set the date as index
        df = df.set_index(date_column)
        self.frequency = frequency
        
        # Extract the time series
        ts = df[value_column]
        self.history = ts
        
        if self.method == 'arima':
            # Fit ARIMA model (p,d,q) = (5,1,0) as starting point
            # These parameters should be tuned based on ACF/PACF plots
            self.model = ARIMA(ts, order=(5, 1, 0))
            self.model = self.model.fit()
            logger.info("ARIMA model summary:")
            logger.info(self.model.summary())
            
        elif self.method == 'ets':
            # Fit Exponential Smoothing model
            # seasonal_periods should be adjusted based on the data
            seasonal_periods = 7 if frequency == 'D' else 24  # Weekly or daily pattern
            self.model = ExponentialSmoothing(ts, 
                                             seasonal='add', 
                                             seasonal_periods=seasonal_periods)
            self.model = self.model.fit()
            logger.info("Exponential Smoothing model fitted")
        
        return self
    
    def forecast(self, steps=24):
        """Generate a forecast for future periods
        
        Args:
            steps (int): Number of periods to forecast
            
        Returns:
            pd.Series: Forecasted values with date index
        """
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        
        if self.method == 'arima':
            forecast = self.model.forecast(steps=steps)
        elif self.method == 'ets':
            forecast = self.model.forecast(steps=steps)
        
        # Create a date range for the forecast
        last_date = self.history.index[-1]
        if self.frequency == 'D':
            forecast_dates = pd.date_range(start=last_date + timedelta(days=1), periods=steps, freq='D')
        elif self.frequency == 'H':
            forecast_dates = pd.date_range(start=last_date + timedelta(hours=1), periods=steps, freq='H')
        else:
            # Default to daily
            forecast_dates = pd.date_range(start=last_date + timedelta(days=1), periods=steps, freq=self.frequency)
        
        # Return forecast as a Series with date index
        forecast_series = pd.Series(forecast, index=forecast_dates)
        return forecast_series
    
    def save(self, filename=None):
        """Save the model to disk
        
        Note: For time series models, we save the model parameters and history
        """
        if self.model is None:
            raise ValueError("No model to save. Train the model first.")
            
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
        
        if filename is None:
            filename = f"{self.method}_model.joblib"
            
        model_path = os.path.join(MODEL_DIR, filename)
        history_path = os.path.join(MODEL_DIR, f"{self.method}_history.joblib")
        
        # Save the model and history
        joblib.dump(self.model, model_path)
        joblib.dump(self.history, history_path)
        logger.info(f"Time series model saved to {model_path}")
        
        return model_path
    
    def load(self, filename=None):
        """Load the model from disk"""
        if filename is None:
            filename = f"{self.method}_model.joblib"
            
        model_path = os.path.join(MODEL_DIR, filename)
        history_path = os.path.join(MODEL_DIR, f"{self.method}_history.joblib")
        
        if not os.path.exists(model_path) or not os.path.exists(history_path):
            raise FileNotFoundError(f"Model or history file not found at {model_path}")
            
        self.model = joblib.load(model_path)
        self.history = joblib.load(history_path)
        logger.info(f"Time series model loaded from {model_path}")
        
        return self


class SpatialAnalyzer:
    """Spatial analysis for flood risk zones
    
    This class implements K-means clustering and IDW interpolation for
    identifying flood risk zones and interpolating sensor readings.
    """
    
    def __init__(self, method='kmeans'):
        """Initialize the spatial analyzer
        
        Args:
            method (str): The spatial analysis method to use ('kmeans' or 'idw')
        """
        self.method = method.lower()
        self.model = None
        self.locations = None
        
        if self.method not in ['kmeans', 'idw']:
            raise ValueError("Method must be either 'kmeans' or 'idw'")
    
    def fit(self, locations, values=None, n_clusters=5):
        """Fit the spatial model
        
        Args:
            locations (pd.DataFrame): DataFrame with latitude and longitude columns
            values (pd.Series, optional): Series of values for each location (for IDW)
            n_clusters (int): Number of clusters for K-means
        """
        logger.info(f"Fitting {self.method.upper()} spatial model...")
        
        # Store locations
        self.locations = locations.copy()
        
        if self.method == 'kmeans':
            # Fit K-means clustering
            # We use lat/long as features for clustering
            coords = self.locations[['latitude', 'longitude']].values
            self.model = KMeans(n_clusters=n_clusters, random_state=42)
            self.model.fit(coords)
            
            # Add cluster labels to locations
            self.locations['cluster'] = self.model.labels_
            logger.info(f"K-means clustering completed with {n_clusters} clusters")
            
        elif self.method == 'idw':
            # For IDW, we just store the values with coordinates
            if values is None:
                raise ValueError("Values must be provided for IDW interpolation")
                
            self.locations['value'] = values
            logger.info("IDW interpolation prepared with locations and values")
        
        return self
    
    def predict(self, points):
        """Make predictions for new points
        
        Args:
            points (pd.DataFrame): DataFrame with latitude and longitude columns
            
        Returns:
            pd.Series: Predicted values or cluster assignments
        """
        if self.model is None and self.method == 'kmeans':
            raise ValueError("Model not fitted yet. Call fit() first.")
            
        if self.locations is None:
            raise ValueError("No location data available. Call fit() first.")
        
        if self.method == 'kmeans':
            # Predict cluster for new points
            coords = points[['latitude', 'longitude']].values
            clusters = self.model.predict(coords)
            return pd.Series(clusters, index=points.index)
            
        elif self.method == 'idw':
            # Implement Inverse Distance Weighting interpolation
            results = []
            
            for _, point in points.iterrows():
                # Calculate inverse squared distances to all known points
                distances = np.sqrt(((self.locations['latitude'] - point['latitude'])**2 + 
                                    (self.locations['longitude'] - point['longitude'])**2))
                
                # Avoid division by zero by setting a minimum distance
                min_dist = 1e-6
                distances = np.maximum(distances, min_dist)
                
                # Calculate weights as 1/d²
                weights = 1.0 / (distances**2)
                
                # Normalize weights
                weights /= np.sum(weights)
                
                # Calculate weighted average
                interpolated_value = np.sum(weights * self.locations['value'])
                results.append(interpolated_value)
            
            return pd.Series(results, index=points.index)
    
    def get_clusters(self):
        """Get the cluster assignments for all locations"""
        if self.method != 'kmeans' or self.model is None:
            raise ValueError("This method is only available for K-means clustering")
            
        return self.locations[['latitude', 'longitude', 'cluster']]
    
    def save(self, filename=None):
        """Save the model to disk"""
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
        
        if filename is None:
            filename = f"{self.method}_spatial_model.joblib"
            
        model_path = os.path.join(MODEL_DIR, filename)
        locations_path = os.path.join(MODEL_DIR, f"{self.method}_locations.joblib")
        
        # Save the model (if applicable) and locations
        if self.model is not None:
            joblib.dump(self.model, model_path)
        
        joblib.dump(self.locations, locations_path)
        logger.info(f"Spatial model saved to {model_path}")
        
        return model_path
    
    def load(self, filename=None):
        """Load the model from disk"""
        if filename is None:
            filename = f"{self.method}_spatial_model.joblib"
            
        model_path = os.path.join(MODEL_DIR, filename)
        locations_path = os.path.join(MODEL_DIR, f"{self.method}_locations.joblib")
        
        if self.method == 'kmeans' and not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
            
        if not os.path.exists(locations_path):
            raise FileNotFoundError(f"Locations file not found at {locations_path}")
        
        if self.method == 'kmeans':
            self.model = joblib.load(model_path)
        
        self.locations = joblib.load(locations_path)
        logger.info(f"Spatial model loaded from {model_path}")
        
        return self


class LSTMFloodPredictor:
    """LSTM Neural Network for time series flood prediction
    
    This model uses LSTM recurrent neural networks to predict flood events
    using time series data.
    """
    
    def __init__(self):
        """Initialize the LSTM flood predictor"""
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTM models but is not installed")
            
        self.model = None
        self.scaler = StandardScaler()
        self.sequence_length = 24  # Default to 24 hours of data
        self.input_features = None
        
    def _create_sequences(self, data, target_column):
        """Create sequences for LSTM training
        
        Args:
            data (pd.DataFrame): DataFrame with time series data
            target_column (str): Name of the target column
            
        Returns:
            tuple: (X, y) where X is sequence data and y is target values
        """
        sequences = []
        targets = []
        
        for i in range(len(data) - self.sequence_length):
            seq = data.iloc[i:i+self.sequence_length].drop(columns=[target_column])
            target = data.iloc[i+self.sequence_length][target_column]
            sequences.append(seq.values)
            targets.append(target)
            
        return np.array(sequences), np.array(targets)
        
    def train(self, data, target_column, sequence_length=24, epochs=50, batch_size=32):
        """Train the LSTM model for flood prediction
        
        Args:
            data (pd.DataFrame): DataFrame with features and target
            target_column (str): Name of the target column
            sequence_length (int): Number of time steps in each sequence
            epochs (int): Number of training epochs
            batch_size (int): Batch size for training
        """
        logger.info("Training LSTM neural network model...")
        
        self.sequence_length = sequence_length
        
        # Save feature names (excluding target)
        self.input_features = [col for col in data.columns if col != target_column]
        
        # Scale the data
        scaled_data = pd.DataFrame(
            self.scaler.fit_transform(data),
            columns=data.columns,
            index=data.index
        )
        
        # Create sequences for LSTM
        X, y = self._create_sequences(scaled_data, target_column)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Get the number of features (excluding target)
        n_features = X.shape[2]
        
        # Build LSTM model
        self.model = Sequential([
            LSTM(64, activation='relu', input_shape=(sequence_length, n_features), return_sequences=True),
            Dropout(0.2),
            LSTM(32, activation='relu'),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(1, activation='sigmoid' if len(np.unique(y)) <= 2 else None)
        ])
        
        # Compile the model
        if len(np.unique(y)) <= 2:
            # Binary classification
            self.model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        else:
            # Regression
            self.model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        
        # Early stopping to prevent overfitting
        early_stopping = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
        
        # Train the model
        history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(X_test, y_test),
            callbacks=[early_stopping],
            verbose=1
        )
        
        # Evaluate the model
        loss, metric = self.model.evaluate(X_test, y_test)
        
        if len(np.unique(y)) <= 2:
            logger.info(f"LSTM model trained - Test accuracy: {metric:.4f}")
            # Make predictions for classification report
            y_pred = (self.model.predict(X_test) > 0.5).astype(int)
            logger.info("\nLSTM model evaluation:")
            logger.info(classification_report(y_test, y_pred))
        else:
            logger.info(f"LSTM model trained - Test MAE: {metric:.4f}")
            # Calculate MSE for regression
            y_pred = self.model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            logger.info(f"Test MSE: {mse:.4f}")
        
        return self
    
    def predict(self, sequence_data):
        """Make predictions using the trained LSTM model
        
        Args:
            sequence_data (pd.DataFrame): DataFrame with sequence_length rows of features
            
        Returns:
            float: Prediction (probability for classification, value for regression)
        """
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
            
        if len(sequence_data) != self.sequence_length:
            raise ValueError(f"Input must have exactly {self.sequence_length} time steps")
            
        # Ensure we have the correct features in the correct order
        if not all(feature in sequence_data.columns for feature in self.input_features):
            raise ValueError(f"Input must contain all features: {self.input_features}")
            
        sequence_data = sequence_data[self.input_features].copy()
        
        # Scale the data
        scaled_sequence = self.scaler.transform(sequence_data)
        
        # Reshape for LSTM input [samples, time steps, features]
        X = scaled_sequence.reshape(1, self.sequence_length, len(self.input_features))
        
        # Make prediction
        prediction = self.model.predict(X)[0, 0]
        
        return prediction
    
    def save(self, filename='lstm_flood_model'):
        """Save the LSTM model"""
        if self.model is None:
            raise ValueError("No model to save. Train the model first.")
            
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
            
        model_path = os.path.join(MODEL_DIR, f"{filename}.h5")
        scaler_path = os.path.join(MODEL_DIR, f"{filename}_scaler.joblib")
        metadata_path = os.path.join(MODEL_DIR, f"{filename}_metadata.joblib")
        
        # Save the model in H5 format
        self.model.save(model_path)
        
        # Save the scaler
        joblib.dump(self.scaler, scaler_path)
        
        # Save metadata (sequence length and feature names)
        metadata = {
            'sequence_length': self.sequence_length,
            'input_features': self.input_features
        }
        joblib.dump(metadata, metadata_path)
        
        logger.info(f"LSTM model saved to {model_path}")
        
        return model_path
    
    def load(self, filename='lstm_flood_model'):
        """Load the LSTM model"""
        from tensorflow.keras.models import load_model
        
        model_path = os.path.join(MODEL_DIR, f"{filename}.h5")
        scaler_path = os.path.join(MODEL_DIR, f"{filename}_scaler.joblib")
        metadata_path = os.path.join(MODEL_DIR, f"{filename}_metadata.joblib")
        
        if not os.path.exists(model_path) or not os.path.exists(scaler_path) or not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Model, scaler, or metadata file not found at {model_path}")
            
        # Load the model
        self.model = load_model(model_path)
        
        # Load the scaler
        self.scaler = joblib.load(scaler_path)
        
        # Load metadata
        metadata = joblib.load(metadata_path)
        self.sequence_length = metadata['sequence_length']
        self.input_features = metadata['input_features']
        
        logger.info(f"LSTM model loaded from {model_path}")
        
        return self


class MultiCriteriaDecisionAnalyzer:
    """Multi-criteria Decision Analysis for evacuation routing and resource allocation
    
    This class implements Multi-criteria Decision Analysis (MCDA) techniques
    to optimize evacuation routes and resource allocation during flood events
    by considering multiple factors such as population density, road accessibility,
    elevation, distance to evacuation centers, and flood risk levels.
    """
    
    def __init__(self):
        """Initialize the MCDA analyzer"""
        self.criteria = {}
        self.alternatives = {}
        self.weights = {}
        self.normalized_matrix = None
        self.weighted_matrix = None
        self.rankings = None
        
    def add_criteria(self, criteria_dict):
        """Add decision criteria with their weights and optimization direction
        
        Args:
            criteria_dict (dict): Dictionary of criteria with their weights and direction
                e.g., {'population': {'weight': 0.3, 'direction': 'max'},
                       'flood_risk': {'weight': 0.4, 'direction': 'min'},
                       'distance': {'weight': 0.2, 'direction': 'min'},
                       'elevation': {'weight': 0.1, 'direction': 'max'}}
        """
        self.criteria = criteria_dict
        # Extract weights for convenience
        self.weights = {criterion: data['weight'] for criterion, data in criteria_dict.items()}
        return self
    
    def add_alternatives(self, alternatives_dict):
        """Add alternatives with their criteria values
        
        Args:
            alternatives_dict (dict): Dictionary of alternatives with their criteria values
                e.g., {'route_1': {'population': 5000, 'flood_risk': 0.8, 'distance': 2.5, 'elevation': 50},
                       'route_2': {'population': 3000, 'flood_risk': 0.4, 'distance': 3.2, 'elevation': 80}}
        """
        self.alternatives = alternatives_dict
        return self
    
    def normalize_criteria(self):
        """Normalize criteria values to ensure comparability across different scales"""
        if not self.criteria or not self.alternatives:
            raise ValueError("Criteria and alternatives must be added before normalization")
        
        # Initialize normalized matrix
        normalized = {}
        for alt_name in self.alternatives.keys():
            normalized[alt_name] = {}
        
        # Normalize each criterion
        for criterion, criterion_data in self.criteria.items():
            # Extract values for this criterion across all alternatives
            values = [alt_data[criterion] for alt_data in self.alternatives.values() if criterion in alt_data]
            
            if not values:
                continue
                
            # Determine normalization approach based on optimization direction
            max_val = max(values)
            min_val = min(values)
            
            # Skip if all values are identical (prevent division by zero)
            if max_val == min_val:
                for alt_name, alt_data in self.alternatives.items():
                    if criterion in alt_data:
                        normalized[alt_name][criterion] = 1.0
                continue
            
            # Normalize based on optimization direction
            for alt_name, alt_data in self.alternatives.items():
                if criterion not in alt_data:
                    continue
                
                value = alt_data[criterion]
                if criterion_data['direction'] == 'max':
                    # For criteria to maximize (higher is better)
                    normalized[alt_name][criterion] = (value - min_val) / (max_val - min_val)
                else:
                    # For criteria to minimize (lower is better)
                    normalized[alt_name][criterion] = (max_val - value) / (max_val - min_val)
        
        self.normalized_matrix = normalized
        return self
    
    def calculate_weighted_scores(self):
        """Calculate weighted scores for each alternative"""
        if self.normalized_matrix is None:
            self.normalize_criteria()
        
        weighted = {}
        for alt_name, norm_scores in self.normalized_matrix.items():
            weighted[alt_name] = {}
            for criterion, norm_value in norm_scores.items():
                if criterion in self.weights:
                    weighted[alt_name][criterion] = norm_value * self.weights[criterion]
        
        self.weighted_matrix = weighted
        return self
    
    def rank_alternatives(self):
        """Rank alternatives based on weighted scores"""
        if self.weighted_matrix is None:
            self.calculate_weighted_scores()
        
        # Calculate total score for each alternative
        total_scores = {}
        for alt_name, weighted_scores in self.weighted_matrix.items():
            total_scores[alt_name] = sum(weighted_scores.values())
        
        # Sort alternatives by total score (descending)
        ranked_alternatives = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
        
        self.rankings = ranked_alternatives
        return self.rankings
    
    def get_best_alternative(self):
        """Get the highest ranked alternative"""
        if self.rankings is None:
            self.rank_alternatives()
        
        if not self.rankings:
            return None
            
        return self.rankings[0]
    
    def save(self, filename='mcda_model.joblib'):
        """Save the MCDA model parameters"""
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
        
        model_path = os.path.join(MODEL_DIR, filename)
        model_data = {
            'criteria': self.criteria,
            'weights': self.weights,
            'normalized_matrix': self.normalized_matrix,
            'weighted_matrix': self.weighted_matrix,
            'rankings': self.rankings
        }
        
        joblib.dump(model_data, model_path)
        logger.info(f"MCDA model saved to {model_path}")
        
        return model_path
    
    def load(self, filename='mcda_model.joblib'):
        """Load the MCDA model parameters"""
        model_path = os.path.join(MODEL_DIR, filename)
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
        
        model_data = joblib.load(model_path)
        self.criteria = model_data['criteria']
        self.weights = model_data['weights']
        self.normalized_matrix = model_data['normalized_matrix']
        self.weighted_matrix = model_data['weighted_matrix']
        self.rankings = model_data['rankings']
        
        logger.info(f"MCDA model loaded from {model_path}")
        
        return self


class DynamicTimeWarpingAnalyzer:
    """Dynamic Time Warping for comparing temporal patterns in flood data
    
    This class implements Dynamic Time Warping (DTW) to compare time series patterns
    between historical flood events and current conditions, identifying similar
    patterns that may indicate increased flood risk.
    """
    
    def __init__(self):
        """Initialize the DTW analyzer"""
        self.reference_patterns = {}
        self.window_size = None
        self.distance_metric = 'euclidean'
    
    def add_reference_pattern(self, pattern_name, time_series_data, metadata=None):
        """Add a reference time series pattern
        
        Args:
            pattern_name (str): Unique identifier for this pattern
            time_series_data (array-like): The time series values
            metadata (dict, optional): Additional information about this pattern
        """
        self.reference_patterns[pattern_name] = {
            'data': np.array(time_series_data),
            'metadata': metadata or {}
        }
        return self
    
    def set_window_size(self, window_size):
        """Set the warping window size
        
        A smaller window size restricts the warping path, which can improve performance
        and prevent pathological alignments.
        
        Args:
            window_size (int): Maximum allowed deviation from the diagonal path
        """
        self.window_size = window_size
        return self
    
    def _dtw_distance(self, series1, series2, window=None):
        """Calculate DTW distance between two time series
        
        Args:
            series1 (array-like): First time series
            series2 (array-like): Second time series
            window (int, optional): Warping window size
            
        Returns:
            float: DTW distance between the series
        """
        # Convert to numpy arrays
        s1 = np.array(series1)
        s2 = np.array(series2)
        
        # Get sequence lengths
        n, m = len(s1), len(s2)
        
        # Set window size
        w = max(window if window else 0, abs(n-m))
        
        # Initialize cost matrix with infinity
        dtw_matrix = np.full((n+1, m+1), np.inf)
        dtw_matrix[0, 0] = 0
        
        # Fill the cost matrix
        for i in range(1, n+1):
            for j in range(max(1, i-w), min(m+1, i+w+1)):
                if self.distance_metric == 'euclidean':
                    cost = (s1[i-1] - s2[j-1])**2
                else:  # Default to Manhattan distance
                    cost = abs(s1[i-1] - s2[j-1])
                
                # Get minimum of three adjacent cells
                dtw_matrix[i, j] = cost + min(dtw_matrix[i-1, j],      # insertion
                                             dtw_matrix[i, j-1],      # deletion
                                             dtw_matrix[i-1, j-1])    # match
        
        # Return the final DTW distance
        return np.sqrt(dtw_matrix[n, m]) if self.distance_metric == 'euclidean' else dtw_matrix[n, m]
    
    def find_similar_patterns(self, query_series, top_n=3):
        """Find the most similar reference patterns to the query time series
        
        Args:
            query_series (array-like): The time series to compare against references
            top_n (int): Number of top matches to return
            
        Returns:
            list: Top N matching patterns with their distances and metadata
        """
        if not self.reference_patterns:
            raise ValueError("No reference patterns added. Use add_reference_pattern() first.")
        
        # Calculate DTW distance to each reference pattern
        results = []
        for pattern_name, pattern_data in self.reference_patterns.items():
            distance = self._dtw_distance(query_series, pattern_data['data'], self.window_size)
            results.append({
                'pattern_name': pattern_name,
                'distance': distance,
                'metadata': pattern_data['metadata']
            })
        
        # Sort by distance (ascending) and return top N
        results.sort(key=lambda x: x['distance'])
        return results[:top_n]
    
    def calculate_similarity_score(self, query_series, normalize=True):
        """Calculate a normalized similarity score based on DTW distance
        
        Args:
            query_series (array-like): The time series to compare against references
            normalize (bool): Whether to normalize the score to 0-100 range
            
        Returns:
            dict: Similarity scores for each reference pattern
        """
        if not self.reference_patterns:
            raise ValueError("No reference patterns added. Use add_reference_pattern() first.")
        
        # Calculate DTW distance to each reference pattern
        distances = {}
        for pattern_name, pattern_data in self.reference_patterns.items():
            distances[pattern_name] = self._dtw_distance(query_series, pattern_data['data'], self.window_size)
        
        # Calculate similarity scores (invert distances)
        if normalize and distances:
            # Find max and min distances for normalization
            max_dist = max(distances.values())
            min_dist = min(distances.values())
            
            # Normalize to 0-100 range (100 = most similar)
            if max_dist > min_dist:
                similarity_scores = {pattern: 100 * (1 - (dist - min_dist) / (max_dist - min_dist))
                                  for pattern, dist in distances.items()}
            else:
                similarity_scores = {pattern: 100 for pattern in distances.keys()}
        else:
            # Simple inversion (smaller distance = higher similarity)
            max_dist = max(distances.values()) if distances else 1
            similarity_scores = {pattern: 1 / (dist + 0.001) for pattern, dist in distances.items()}
        
        return similarity_scores
    
    def save(self, filename='dtw_model.joblib'):
        """Save the DTW model parameters"""
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
        
        model_path = os.path.join(MODEL_DIR, filename)
        model_data = {
            'reference_patterns': self.reference_patterns,
            'window_size': self.window_size,
            'distance_metric': self.distance_metric
        }
        
        joblib.dump(model_data, model_path)
        logger.info(f"DTW model saved to {model_path}")
        
        return model_path
    
    def load(self, filename='dtw_model.joblib'):
        """Load the DTW model parameters"""
        model_path = os.path.join(MODEL_DIR, filename)
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
        
        model_data = joblib.load(model_path)
        self.reference_patterns = model_data['reference_patterns']
        self.window_size = model_data['window_size']
        self.distance_metric = model_data['distance_metric']
        
        logger.info(f"DTW model loaded from {model_path}")
        
        return self
