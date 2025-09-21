# Local development settings for SQLite database

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Use SQLite for local development in Replit
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Keep Debug on for local development
DEBUG = True

# Define hosts to allow connections from localhost
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']

# CORS settings for local development
CORS_ALLOW_ALL_ORIGINS = True  # Allow all cross-origin requests
CORS_ALLOW_CREDENTIALS = True   # Allow cookies in cross-origin requests

# Trust all CSRF origins for local development
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:*', 
    'http://127.0.0.1:*',
    'https://*.replit.dev',
    'https://*.replit.app',
    'https://*.repl.co',
    'https://*.janeway.replit.dev'
]

# Static and media URLs
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static_root')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Settings for sensors data
ALLOW_EMPTY_SENSOR_VALUES = True  # Always allow empty values to avoid client-side errors

# Don't retry database connections too many times
DATABASE_RETRY_LIMIT = 1

# Weather service settings for local development
WEATHER_UPDATE_INTERVAL = 300  # seconds

# Weather API configuration
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY', '')

# Logging settings for development
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'core': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'api': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
