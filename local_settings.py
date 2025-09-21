# Local development settings for MySQL
# Copy this to flood_monitoring/settings.py or include it

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent

# Use this MySQL configuration for local development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'barangay',      # Database name
        'USER': 'root',          # Database user
        'PASSWORD': 'root',      # Database password
        'HOST': '127.0.0.1',     # Database host
        'PORT': '3305',          # Database port
        'OPTIONS': {
            'charset': 'utf8mb4',  # Full Unicode support
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",  # Strict mode for data integrity
            'autocommit': True,    # Auto-commit transactions
        },
    }
}

# Keep Debug on for local development
DEBUG = True

# Local hosts
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Static files settings for local development
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Media files settings
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
