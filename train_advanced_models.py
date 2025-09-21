#!/usr/bin/env python
"""Train advanced machine learning models for flood prediction.

This script trains and evaluates multiple machine learning algorithms
for flood prediction using historical data, and compares their performance.
"""

import os
import sys
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, mean_absolute_error, accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import advanced algorithms
from flood_monitoring.ml.advanced_algorithms import (
    GradientBoostingFloodPredictor,
    SVMFloodPredictor,
    TimeSeriesForecaster,
    SpatialAnalyzer,
    LSTMFloodPredictor,
    MultiCriteriaDecisionAnalyzer,
    DynamicTimeWarpingAnalyzer
)

# Import original model for comparison
from flood_monitoring.ml.flood_prediction_model import train_models as train_original_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flood_monitoring/data')
HISTORICAL_DATA_FILE = os.path.join(DATA_DIR, 'synthetic_historical_data.csv')
OUTPUT_DIR = os.path.join(DATA_DIR, 'model_comparison')


def load_historical_data():
    """Load historical flood data for model training"""
    if not os.path.exists(HISTORICAL_DATA_FILE):
        raise FileNotFoundError(f"Historical data file not found at {HISTORICAL_DATA_FILE}. Run generate_and_train_model.py first.")
    
    logger.info(f"Loading historical data from {HISTORICAL_DATA_FILE}")
    df = pd.read_csv(HISTORICAL_DATA_FILE)
    
    # Convert date columns to datetime
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    
    return df


def prepare_data(df):
    """Prepare data for model training"""
    # Make a copy to avoid modifying the original dataframe
    data = df.copy()
    
    # Assuming 'flood_event' is the target variable for classification
    if 'flood_event' not in data.columns:
        raise ValueError("'flood_event' column not found in historical data")
    
    # Select features and target
    feature_columns = [
        'rainfall_24h', 'rainfall_48h', 'rainfall_72h',
        'water_level', 'temperature', 'humidity', 'soil_saturation'
    ]
    
    # Check if all features are present
    missing_features = [col for col in feature_columns if col not in data.columns]
    if missing_features:
        raise ValueError(f"Missing features in historical data: {missing_features}")
    
    # Prepare classification data
    X = data[feature_columns]
    y = data['flood_event']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Return classification data
    classification_data = {
        'X_train': X_train, 'X_test': X_test,
        'y_train': y_train, 'y_test': y_test,
        'feature_columns': feature_columns
    }
    
    # Prepare time series data
    if 'date' in data.columns:
        time_series_data = data.sort_values('date')
    else:
        # If date is not available, use index as time
        time_series_data = data.copy()
        time_series_data['date'] = pd.date_range(start='2024-01-01', periods=len(data), freq='D')
    
    return classification_data, time_series_data


def train_and_evaluate_classification_models(data):
    """Train and evaluate classification models"""
    X_train, X_test = data['X_train'], data['X_test']
    y_train, y_test = data['y_train'], data['y_test']
    
    # Dictionary to store model evaluation results
    results = {}
    
    # 1. Gradient Boosting
    logger.info("\n====== Gradient Boosting Model ======")
    gbm = GradientBoostingFloodPredictor()
    gbm.train(X_train, y_train)
    gbm_pred, gbm_prob = gbm.predict(X_test)
    gbm_accuracy = accuracy_score(y_test, gbm_pred)
    gbm_f1 = f1_score(y_test, gbm_pred)
    logger.info(f"GBM Accuracy: {gbm_accuracy:.4f}, F1 Score: {gbm_f1:.4f}")
    gbm.save()
    results['Gradient Boosting'] = {'accuracy': gbm_accuracy, 'f1': gbm_f1}
    
    # 2. Support Vector Machine
    logger.info("\n====== Support Vector Machine ======")
    svm = SVMFloodPredictor()
    svm.train(X_train, y_train)
    svm_pred, svm_prob = svm.predict(X_test)
    svm_accuracy = accuracy_score(y_test, svm_pred)
    svm_f1 = f1_score(y_test, svm_pred)
    logger.info(f"SVM Accuracy: {svm_accuracy:.4f}, F1 Score: {svm_f1:.4f}")
    svm.save()
    results['SVM'] = {'accuracy': svm_accuracy, 'f1': svm_f1}
    
    # 3. LSTM Neural Network (if TensorFlow is available)
    try:
        logger.info("\n====== LSTM Neural Network ======")
        # For LSTM, we need to prepare sequential data
        # Here we'll use a simple approach of recent historical data
        lstm = LSTMFloodPredictor()
        
        # We need to create a DataFrame with all data
        all_data = pd.DataFrame(
            np.vstack([X_train, X_test]), 
            columns=[f'feature_{i}' for i in range(X_train.shape[1])]
        )
        all_data['target'] = np.hstack([y_train, y_test])
        
        # Train the LSTM model
        lstm.train(all_data, 'target', sequence_length=10, epochs=20, batch_size=32)
        
        # Since LSTM uses sequential data, evaluation is a bit different
        # We'll use a simplified approach here
        try:
            # Create test sequences
            test_data = pd.DataFrame(X_test, columns=[f'feature_{i}' for i in range(X_test.shape[1])])
            test_data['target'] = y_test
            
            # Predict
            lstm_pred, lstm_prob = lstm.predict(test_data)
            
            # Calculate metrics
            lstm_accuracy = accuracy_score(y_test[-len(lstm_pred):], lstm_pred)
            lstm_f1 = f1_score(y_test[-len(lstm_pred):], lstm_pred)
            
            logger.info(f"LSTM Accuracy: {lstm_accuracy:.4f}, F1 Score: {lstm_f1:.4f}")
            lstm.save()
            results['LSTM'] = {'accuracy': lstm_accuracy, 'f1': lstm_f1}
        except Exception as e:
            logger.error(f"Error evaluating LSTM model: {str(e)}")
            results['LSTM'] = {'accuracy': 0, 'f1': 0, 'error': str(e)}
    except Exception as e:
        logger.error(f"Error training LSTM model: {str(e)}")
        results['LSTM'] = {'accuracy': 0, 'f1': 0, 'error': str(e)}
        # Get the first 80% of data for training in time order
        all_data = pd.concat([X_train, y_train], axis=1)
        all_data = all_data.sample(frac=1, random_state=42).reset_index(drop=True)  # Shuffle
        lstm.train(all_data, 'flood_event', sequence_length=10, epochs=20, batch_size=32)
        
        # Evaluate on test set (simplified - normally needs sequences)
        # Note: This is a simplified evaluation for demonstration
        test_data = pd.concat([X_test, y_test], axis=1)
        test_sequences = []
        test_targets = []
        seq_len = 10
        
        for i in range(len(test_data) - seq_len):
            test_sequences.append(test_data.iloc[i:i+seq_len])
            test_targets.append(test_data.iloc[i+seq_len]['flood_event'])
        
        lstm_predictions = []
        for seq in test_sequences[:50]:  # Limit to first 50 for speed
            # Predict and threshold at 0.5 for binary classification
            pred = lstm.predict(seq) > 0.5
            lstm_predictions.append(int(pred))
        
        lstm_accuracy = accuracy_score(test_targets[:50], lstm_predictions)
        lstm_f1 = f1_score(test_targets[:50], lstm_predictions)
        logger.info(f"LSTM Accuracy: {lstm_accuracy:.4f}, F1 Score: {lstm_f1:.4f}")
        lstm.save()
        results['LSTM'] = {'accuracy': lstm_accuracy, 'f1': lstm_f1}
    except (ImportError, Exception) as e:
        logger.warning(f"LSTM model training skipped: {str(e)}")
    
    # Add the original Random Forest model
    try:
        logger.info("\n====== Original Random Forest Model ======")
        # Train the original model
        original_model_info = train_original_model(evaluate_only=True)
        results['Random Forest'] = {
            'accuracy': original_model_info['accuracy'],
            'f1': original_model_info['f1_score']
        }
    except Exception as e:
        logger.warning(f"Original model training evaluation failed: {str(e)}")
    
    return results


def train_and_evaluate_time_series_models(data):
    """Train and evaluate time series forecasting models"""
    logger.info("\n====== Time Series Forecasting Models ======")
    results = {}
    
    # Make sure we have time-ordered data
    time_series_data = data.sort_values('date')
    
    # Split into train/test sets (keep time ordering)
    train_size = int(len(time_series_data) * 0.8)
    train_data = time_series_data.iloc[:train_size]
    test_data = time_series_data.iloc[train_size:]
    
    # We'll test time series forecasting for water_level
    target_variable = 'water_level'
    
    # 1. ARIMA model
    logger.info("\n----- ARIMA Model for Water Level Forecasting -----")
    try:
        arima = TimeSeriesForecaster(method='arima')
        arima.train(train_data, 'date', target_variable, frequency='D')
        
        # Forecast for the test period
        forecast = arima.forecast(steps=len(test_data))
        
        # Evaluate
        actual = test_data[target_variable].values
        predicted = forecast.values[:len(actual)]
        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))
        logger.info(f"ARIMA - MAE: {mae:.4f}, RMSE: {rmse:.4f}")
        arima.save()
        results['ARIMA'] = {'mae': mae, 'rmse': rmse}
    except Exception as e:
        logger.warning(f"ARIMA model training failed: {str(e)}")
    
    # 2. Exponential Smoothing
    logger.info("\n----- Exponential Smoothing for Water Level Forecasting -----")
    try:
        ets = TimeSeriesForecaster(method='ets')
        ets.train(train_data, 'date', target_variable, frequency='D')
        
        # Forecast for the test period
        forecast = ets.forecast(steps=len(test_data))
        
        # Evaluate
        actual = test_data[target_variable].values
        predicted = forecast.values[:len(actual)]
        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))
        logger.info(f"ETS - MAE: {mae:.4f}, RMSE: {rmse:.4f}")
        ets.save()
        results['Exponential Smoothing'] = {'mae': mae, 'rmse': rmse}
    except Exception as e:
        logger.warning(f"Exponential Smoothing model training failed: {str(e)}")
    
    return results


def train_and_evaluate_spatial_models(data):
    """Train and evaluate spatial analysis models"""
    logger.info("\n====== Spatial Analysis Models ======")
    results = {}
    
    # Check if we have location data
    if 'latitude' not in data.columns or 'longitude' not in data.columns:
        logger.warning("Spatial models require latitude and longitude data, skipping")
        return results
    
    # 1. K-means Clustering
    logger.info("\n----- K-means Spatial Clustering -----")
    try:
        # Filter out rows with missing coordinates
        locations = data[['latitude', 'longitude']].dropna()
        
        # Initialize and fit K-means clusterer
        kmeans = SpatialAnalyzer(method='kmeans')
        kmeans.fit(locations, n_clusters=5)
        
        # Get the clusters
        clusters = kmeans.get_clusters()
        logger.info(f"K-means clustering completed with {len(clusters)} points in 5 clusters")
        kmeans.save()
        
        # Simple evaluation: count points in each cluster
        cluster_counts = clusters['cluster'].value_counts().to_dict()
        logger.info(f"Points per cluster: {cluster_counts}")
        results['K-means'] = {'clusters': cluster_counts}
    except Exception as e:
        logger.warning(f"K-means clustering failed: {str(e)}")
    
    # 2. IDW Interpolation
    logger.info("\n----- IDW Spatial Interpolation -----")
    try:
        # We'll interpolate water level values
        if 'water_level' not in data.columns:
            raise ValueError("'water_level' column not found in historical data")
        
        # Filter out rows with missing coordinates or values
        locations_with_values = data[['latitude', 'longitude', 'water_level']].dropna()
        
        # Initialize and fit IDW interpolator
        idw = SpatialAnalyzer(method='idw')
        idw.fit(locations_with_values[['latitude', 'longitude']], locations_with_values['water_level'])
        
        # Create a grid of test points
        lat_min, lat_max = locations_with_values['latitude'].min(), locations_with_values['latitude'].max()
        lon_min, lon_max = locations_with_values['longitude'].min(), locations_with_values['longitude'].max()
        
        test_grid = pd.DataFrame({
            'latitude': np.linspace(lat_min, lat_max, 5),
            'longitude': np.linspace(lon_min, lon_max, 5)
        })
        
        # Interpolate values at test points
        interpolated = idw.predict(test_grid)
        logger.info(f"IDW interpolation completed for {len(test_grid)} points")
        logger.info(f"Sample interpolated values: {interpolated.head()}")
        idw.save()
        
        results['IDW'] = {'sample_values': interpolated.mean()}
    except Exception as e:
        logger.warning(f"IDW interpolation failed: {str(e)}")
    
    return results


def train_and_evaluate_optimization_algorithms(data):
    """Train and evaluate optimization algorithms"""
    logger.info("\n====== Optimization Algorithms ======")
    results = {}
    
    # 1. Multi-criteria Decision Analysis
    logger.info("\n----- Multi-criteria Decision Analysis -----")
    try:
        # Initialize MCDA
        mcda = MultiCriteriaDecisionAnalyzer()
        
        # Define criteria with weights and direction
        # - 'max' means higher values are better
        # - 'min' means lower values are better
        criteria = {
            'population_affected': {'weight': 0.35, 'direction': 'min'},  # Minimize affected population
            'response_time': {'weight': 0.25, 'direction': 'min'},  # Minimize response time
            'resource_availability': {'weight': 0.20, 'direction': 'max'},  # Maximize resource availability
            'accessibility': {'weight': 0.15, 'direction': 'max'},  # Maximize route accessibility
            'elevation': {'weight': 0.05, 'direction': 'max'}  # Maximize elevation (flood safety)
        }
        mcda.add_criteria(criteria)
        
        # Define evacuation alternatives
        # In a real scenario, these would be based on real route data
        alternatives = {
            'route_a': {
                'population_affected': 5000,
                'response_time': 15,        # minutes
                'resource_availability': 8,  # scale 1-10
                'accessibility': 7,         # scale 1-10
                'elevation': 45            # meters
            },
            'route_b': {
                'population_affected': 3500,
                'response_time': 20,
                'resource_availability': 9,
                'accessibility': 6,
                'elevation': 60
            },
            'route_c': {
                'population_affected': 7500,
                'response_time': 10,
                'resource_availability': 5,
                'accessibility': 9,
                'elevation': 30
            },
            'route_d': {
                'population_affected': 4000,
                'response_time': 25,
                'resource_availability': 10,
                'accessibility': 8,
                'elevation': 55
            }
        }
        mcda.add_alternatives(alternatives)
        
        # Process and rank the alternatives
        mcda.normalize_criteria()
        mcda.calculate_weighted_scores()
        rankings = mcda.rank_alternatives()
        best_route = mcda.get_best_alternative()
        
        logger.info(f"MCDA Rankings (best to worst): {rankings}")
        logger.info(f"Best evacuation route: {best_route[0]} with score {best_route[1]:.4f}")
        
        # Save the model
        mcda.save()
        
        results['MCDA'] = {
            'best_route': best_route[0], 
            'best_score': best_route[1],
            'all_rankings': {route: score for route, score in rankings}
        }
    except Exception as e:
        logger.warning(f"Multi-criteria Decision Analysis failed: {str(e)}")
    
    # 2. Dynamic Time Warping
    logger.info("\n----- Dynamic Time Warping Analysis -----")
    try:
        # Initialize DTW analyzer
        dtw = DynamicTimeWarpingAnalyzer()
        
        # Create synthetic reference patterns for floods
        # In a real scenario, these would be actual historical flood patterns
        # Pattern 1: Rapid rise, slow recession (flash flood)
        flash_flood = np.concatenate([
            np.linspace(0.5, 3.0, 12),  # Rapid rise
            np.linspace(3.0, 2.8, 6),   # Brief plateau
            np.linspace(2.8, 0.8, 18)   # Slow recession
        ])
        
        # Pattern 2: Gradual rise and fall (prolonged flood)
        prolonged_flood = np.concatenate([
            np.linspace(0.5, 2.5, 18),   # Gradual rise
            np.linspace(2.5, 2.4, 12),   # Extended plateau
            np.linspace(2.4, 0.6, 18)    # Gradual recession
        ])
        
        # Pattern 3: Double-peak flood (complex event)
        double_peak = np.concatenate([
            np.linspace(0.5, 2.0, 10),   # First rise
            np.linspace(2.0, 1.5, 5),    # First recession
            np.linspace(1.5, 2.8, 8),    # Second, larger rise
            np.linspace(2.8, 2.7, 4),    # Brief plateau
            np.linspace(2.7, 0.7, 15)    # Final recession
        ])
        
        # Add these patterns to the DTW analyzer
        dtw.add_reference_pattern('flash_flood', flash_flood, {
            'description': 'Rapid rise, slow fall characteristic of flash floods',
            'average_duration': '36 hours',
            'typical_max_height': '3.0 meters',
            'hazard_level': 'High'
        })
        
        dtw.add_reference_pattern('prolonged_flood', prolonged_flood, {
            'description': 'Gradual rise and fall, typical of prolonged rainfall',
            'average_duration': '48 hours',
            'typical_max_height': '2.5 meters',
            'hazard_level': 'Medium'
        })
        
        dtw.add_reference_pattern('double_peak', double_peak, {
            'description': 'Complex event with two distinct peaks',
            'average_duration': '42 hours',
            'typical_max_height': '2.8 meters',
            'hazard_level': 'Very High'
        })
        
        # Set warping window to improve performance
        dtw.set_window_size(10)
        
        # Create a test scenario (current event unfolding)
        # In a real application, this would be real-time water level data
        current_pattern = np.concatenate([
            np.linspace(0.5, 1.8, 8),    # Initial rise
            np.linspace(1.8, 1.6, 4),    # Small dip
            np.linspace(1.6, 2.2, 6)     # Second rise (ongoing)
        ])
        
        # Find similar historical patterns
        similar_patterns = dtw.find_similar_patterns(current_pattern, top_n=3)
        
        # Calculate similarity scores
        similarity_scores = dtw.calculate_similarity_score(current_pattern)
        
        logger.info(f"DTW Analysis - Most similar historical pattern: {similar_patterns[0]['pattern_name']}")
        logger.info(f"Similarity scores: {similarity_scores}")
        
        # Save the model
        dtw.save()
        
        results['DTW'] = {
            'most_similar_pattern': similar_patterns[0]['pattern_name'],
            'similarity_scores': similarity_scores,
            'pattern_metadata': similar_patterns[0]['metadata']
        }
    except Exception as e:
        logger.warning(f"Dynamic Time Warping Analysis failed: {str(e)}")
    
    return results


def plot_comparison_results(classification_results, time_series_results):
    """Plot comparison of model results"""
    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # 1. Classification Models Comparison
    if classification_results:
        models = list(classification_results.keys())
        accuracies = [results['accuracy'] for model, results in classification_results.items()]
        f1_scores = [results['f1'] for model, results in classification_results.items()]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        bar_width = 0.35
        x = range(len(models))
        
        ax.bar(x, accuracies, bar_width, label='Accuracy', color='blue', alpha=0.7)
        ax.bar([i + bar_width for i in x], f1_scores, bar_width, label='F1 Score', color='green', alpha=0.7)
        
        ax.set_xlabel('Models')
        ax.set_ylabel('Score')
        ax.set_title('Comparison of Classification Models')
        ax.set_xticks([i + bar_width/2 for i in x])
        ax.set_xticklabels(models)
        ax.legend()
        plt.tight_layout()
        
        output_file = os.path.join(OUTPUT_DIR, 'classification_comparison.png')
        plt.savefig(output_file)
        logger.info(f"Classification comparison plot saved to {output_file}")
        plt.close()
    
    # 2. Time Series Models Comparison
    if time_series_results:
        models = list(time_series_results.keys())
        maes = [results['mae'] for model, results in time_series_results.items()]
        rmses = [results['rmse'] for model, results in time_series_results.items()]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        bar_width = 0.35
        x = range(len(models))
        
        ax.bar(x, maes, bar_width, label='MAE', color='orange', alpha=0.7)
        ax.bar([i + bar_width for i in x], rmses, bar_width, label='RMSE', color='red', alpha=0.7)
        
        ax.set_xlabel('Models')
        ax.set_ylabel('Error')
        ax.set_title('Comparison of Time Series Models')
        ax.set_xticks([i + bar_width/2 for i in x])
        ax.set_xticklabels(models)
        ax.legend()
        plt.tight_layout()
        
        output_file = os.path.join(OUTPUT_DIR, 'time_series_comparison.png')
        plt.savefig(output_file)
        logger.info(f"Time series comparison plot saved to {output_file}")
        plt.close()


def main():
    """Main function to train and evaluate all models"""
    logger.info("Starting advanced model training and evaluation")
    
    try:
        # Load historical data
        historical_data = load_historical_data()
        logger.info(f"Loaded {len(historical_data)} historical data points")
        
        # Prepare data for different model types
        classification_data, time_series_data = prepare_data(historical_data)
        
        # Train and evaluate classification models
        logger.info("\nTraining and evaluating classification models...")
        classification_results = train_and_evaluate_classification_models(classification_data)
        
        # Train and evaluate time series models
        logger.info("\nTraining and evaluating time series models...")
        time_series_results = train_and_evaluate_time_series_models(time_series_data)
        
        # Train and evaluate spatial models
        logger.info("\nTraining and evaluating spatial models...")
        spatial_results = train_and_evaluate_spatial_models(historical_data)
        
        # Train and evaluate optimization algorithms
        logger.info("\nTraining and evaluating optimization algorithms...")
        optimization_results = train_and_evaluate_optimization_algorithms(historical_data)
        
        # Plot comparison results
        plot_comparison_results(classification_results, time_series_results)
        
        logger.info("\nModel training and evaluation completed successfully!")
        logger.info("\nSummary of Results:")
        logger.info("\nClassification Models:")
        for model, metrics in classification_results.items():
            logger.info(f"{model}: Accuracy={metrics['accuracy']:.4f}, F1={metrics['f1']:.4f}")
        
        logger.info("\nTime Series Models:")
        for model, metrics in time_series_results.items():
            logger.info(f"{model}: MAE={metrics['mae']:.4f}, RMSE={metrics['rmse']:.4f}")
            
        logger.info("\nOptimization Algorithm Results:")
        if 'MCDA' in optimization_results:
            mcda_result = optimization_results['MCDA']
            logger.info(f"MCDA - Best Route: {mcda_result['best_route']} with score {mcda_result['best_score']:.4f}")
        
        if 'DTW' in optimization_results:
            dtw_result = optimization_results['DTW']
            logger.info(f"DTW - Most Similar Pattern: {dtw_result['most_similar_pattern']} ")
            logger.info(f"     Pattern Details: {dtw_result['pattern_metadata']['description']}")
        
    except Exception as e:
        logger.error(f"Error during model training: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
