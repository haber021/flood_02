# Deployment settings for the Flood Monitoring System
# Copy these settings to your settings.py file when deploying to production

import os
import dj_database_url

# Database configuration for MySQL
# Replace the existing PostgreSQL configuration with this MySQL configuration

# Use DATABASE_URL environment variable if available
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config()
    }
else:
    # MySQL database configuration
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
            'TEST': {
                'CHARSET': 'utf8mb4',
                'COLLATION': 'utf8mb4_unicode_ci',
            }
        }
    }

# Production settings
DEBUG = False

# Security settings
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com', 'your-deployment-url.com']

# Static file settings for production
STATIC_ROOT = '/path/to/static/root/'

# HTTPS settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Middleware for production
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add whitenoise for static files
    # ... other middleware ...
]

# Static files with whitenoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Logging configuration for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': '/path/to/django/logs/flood_monitoring.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': True,
        },
    },
}

# Email settings for alerts (configure based on your email provider)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.youremailprovider.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-email-password'

# Additional deployment notes:
# 1. Replace placeholder values with your actual production values
# 2. Make sure to run 'python manage.py collectstatic' before deployment
# 3. Configure your web server (Apache/Nginx) to serve static files
# 4. Set up proper backups for your MySQL database
# 5. Update SECRET_KEY with a secure value for production
