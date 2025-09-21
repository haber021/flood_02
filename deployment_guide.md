# Flood Monitoring System Deployment Guide

## Pre-Deployment Checklist

- [ ] Database backup completed
- [ ] All required packages listed in requirements.txt
- [ ] Debug mode set to False
- [ ] Static files collected
- [ ] Security settings configured
- [ ] Database connection tested

## Deployment Steps

### 1. Prepare Your Environment

1. Set up your hosting environment (shared hosting, VPS, cloud provider)
2. Install Python 3.9+ on your server
3. Install MySQL 5.7+ on your server (if not using a managed database service)

### 2. Database Setup

1. Create your MySQL database:
   ```sql
   CREATE DATABASE barangay;
   ```

2. Configure your database credentials in the settings file:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'barangay',      # Database name
           'USER': 'root',          # Database user
           'PASSWORD': 'root',      # Database password
           'HOST': '127.0.0.1',     # Database host
           'PORT': '3305',          # Database port
       }
   }
   ```

### 3. Environment Setup

1. Clone or upload the project to your server
2. Rename `deployment_requirements.txt` to `requirements.txt`
3. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

4. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

### 4. Configuration

1. Copy settings from `deployment_settings.py` to your main `settings.py` file
2. Set a secure `SECRET_KEY` in your settings
3. Update `ALLOWED_HOSTS` with your domain name
4. Configure static and media file paths for production

### 5. Database Migration

1. Run migrations to set up the database schema:
   ```bash
   python manage.py migrate
   ```

2. Create a superuser account:
   ```bash
   python manage.py createsuperuser
   ```

### 6. Static Files

1. Collect static files to the configured static root:
   ```bash
   python manage.py collectstatic
   ```

2. Configure your web server (Nginx/Apache) to serve static files

### 7. Web Server Configuration

#### For Nginx:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /path/to/your/project;
    }

    location /media/ {
        root /path/to/your/project;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/path/to/your/project/flood_monitoring.sock;
    }
}
```

#### For Apache:

```apache
<VirtualHost *:80>
    ServerName yourdomain.com
    ServerAlias www.yourdomain.com
    
    Alias /static/ /path/to/your/project/static/
    Alias /media/ /path/to/your/project/media/
    
    <Directory /path/to/your/project/static>
        Require all granted
    </Directory>
    
    <Directory /path/to/your/project/media>
        Require all granted
    </Directory>
    
    <Directory /path/to/your/project/flood_monitoring>
        <Files wsgi.py>
            Require all granted
        </Files>
    </Directory>
    
    WSGIDaemonProcess flood_monitoring python-home=/path/to/your/venv python-path=/path/to/your/project
    WSGIProcessGroup flood_monitoring
    WSGIScriptAlias / /path/to/your/project/flood_monitoring/wsgi.py
</VirtualHost>
```

### 8. Gunicorn Setup (with Nginx)

1. Create a systemd service file `/etc/systemd/system/gunicorn.service`:

```ini
[Unit]
Description=gunicorn daemon for Flood Monitoring System
After=network.target

[Service]
User=your_user
Group=your_group
WorkingDirectory=/path/to/your/project
ExecStart=/path/to/your/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/path/to/your/project/flood_monitoring.sock flood_monitoring.wsgi:application

[Install]
WantedBy=multi-user.target
```

2. Start and enable the gunicorn service:

```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

### 9. Background Services

Set up systemd services for your background tasks (Weather Update Service and ML Model Training):

1. Create a service file for Weather Update Service `/etc/systemd/system/weather_update.service`:

```ini
[Unit]
Description=Weather Update Service for Flood Monitoring
After=network.target

[Service]
User=your_user
Group=your_group
WorkingDirectory=/path/to/your/project
ExecStart=/path/to/your/venv/bin/python run_weather_update.py
Restart=always
RestartSec=300

[Install]
WantedBy=multi-user.target
```

2. Create a service file for ML Model Training `/etc/systemd/system/model_training.service`:

```ini
[Unit]
Description=ML Model Training for Flood Monitoring
After=network.target

[Service]
User=your_user
Group=your_group
WorkingDirectory=/path/to/your/project
ExecStart=/path/to/your/venv/bin/python run_model_training.py
Restart=always
RestartSec=86400

[Install]
WantedBy=multi-user.target
```

3. Start and enable these services:

```bash
sudo systemctl start weather_update
sudo systemctl enable weather_update
sudo systemctl start model_training
sudo systemctl enable model_training
```

### 10. SSL Certificate (HTTPS)

1. Install certbot for Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx  # For Nginx
# OR
sudo apt install certbot python3-certbot-apache  # For Apache
```

2. Obtain and install SSL certificate:

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com  # For Nginx
# OR
sudo certbot --apache -d yourdomain.com -d www.yourdomain.com  # For Apache
```

### 11. Final Steps

1. Test your deployment by accessing your domain in a web browser
2. Check logs for any errors:
   ```bash
   sudo tail -f /path/to/django/logs/flood_monitoring.log
   ```

3. Set up regular database backups using cron jobs

## Maintenance and Monitoring

### Regular Maintenance Tasks

1. Set up database backups to run daily:

```bash
0 2 * * * mysqldump -u root -p'root' barangay > /path/to/backups/barangay_$(date +\%Y\%m\%d).sql
```

2. Monitor system health and logs
3. Keep the system updated with security patches

### Troubleshooting

- **Issue**: Static files not loading  
  **Solution**: Check your web server configuration and run `collectstatic` again

- **Issue**: Database connection errors  
  **Solution**: Verify your database credentials and ensure the MySQL server is running

- **Issue**: 500 Server Error  
  **Solution**: Check the application logs for detailed error information

## Contact and Support

For assistance with deployment issues, please contact the system administrator or technical support team.
