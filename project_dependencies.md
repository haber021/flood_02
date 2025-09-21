# Flood Monitoring System Dependencies

## Core Framework
- django==5.2
- djangorestframework==3.16.0

## Database
- dj-database-url==2.3.0
- psycopg2-binary==2.9.10

## Data Science and ML Libraries
- numpy==1.26.3
- pandas==2.2.1
- scikit-learn==1.4.1
- joblib==1.3.2
- matplotlib==3.8.2

## Time Series Analysis
- statsmodels==0.14.1

## Deep Learning (optional, for advanced models)
- tensorflow==2.15.0

## Weather and Satellite Data Fetching
- requests==2.31.0
- trafilatura==1.6.3

## Geospatial Utilities
- geopy==2.4.1
- shapely==2.0.3

## Web Scraping (for weather data)
- beautifulsoup4==4.12.3

## Utility Packages
- python-dateutil==2.8.2
- pytz==2024.1

## Development and Testing
- pylint==3.1.0
- black==24.3.0

## Installation Notes

These dependencies are already installed in the Replit environment. If you want to deploy this project elsewhere, you can install the dependencies using:

```bash
pip install -r requirements.txt
```

where requirements.txt contains the above dependencies.

## Core Libraries Used in This Project

### Machine Learning Models
This project uses scikit-learn's RandomForest and other machine learning algorithms for flood prediction based on various environmental factors.

### Data Visualization
The dashboard uses Chart.js for creating interactive charts and visualizations of sensor data, rainfall patterns, and flood predictions.

### Maps and Geospatial Display
Leaflet.js is used for displaying maps, sensor locations, and flood risk zones with color-coded indicators.

### Real-time Data Processing
The system fetches real-time weather data from satellite and regional weather services using the requests library and processes it using pandas.

### Advanced Algorithms
For complex predictions, the system uses a combination of traditional machine learning models and time series analysis to provide accurate flood forecasting.
