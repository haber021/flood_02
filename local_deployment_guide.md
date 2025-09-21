# Local Deployment Guide for Flood Monitoring System

This guide will help you deploy the Flood Monitoring System on your local machine using MySQL for data storage.

## Prerequisites

- Python 3.9+ installed
- MySQL installed and running on port 3305
- Git (optional, for cloning the repository)

## Step 1: Clone and Setup the Project

1. Clone or download the project to your local machine
2. Navigate to the project directory

## Step 2: Set Up MySQL Database

1. Log in to MySQL:
   ```bash
   mysql -u root -p
   ```

2. Create the database:
   ```sql
   CREATE DATABASE barangay CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

3. Exit MySQL:
   ```sql
   EXIT;
   ```

4. Verify MySQL is running on port 3305:
   ```bash
   # For Linux
   sudo netstat -tlnp | grep mysql
   
   # For Windows
   netstat -ano | findstr 3305
   ```

   If MySQL isn't running on port 3305, modify your MySQL configuration file to use this port:
   
   **For Linux**: Edit `/etc/mysql/my.cnf`
   **For Windows**: Edit `C:\ProgramData\MySQL\MySQL Server x.x\my.ini`
   
   Add or modify:
   ```
   [mysqld]
   port=3305
   ```
   
   Then restart MySQL service.

## Step 3: Create a Virtual Environment (Optional but Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it (Linux/Mac)
source venv/bin/activate

# Activate it (Windows)
venv\Scripts\activate
```

## Step 4: Install Dependencies

1. Use the deployment_requirements.txt file (rename it first):
   ```bash
   cp deployment_requirements.txt requirements.txt
   pip install -r requirements.txt
   ```

## Step 5: Configure the Application

1. Copy the local settings file to your project settings:
   ```bash
   cp local_settings.py flood_monitoring/local_settings.py
   ```

2. Modify your main settings.py file to include local settings:
   
   Add this at the end of `flood_monitoring/settings.py`:
   ```python
   # Import local settings if available
   try:
       from .local_settings import *
   except ImportError:
       pass
   ```

## Step 6: Initialize the Database

1. Apply migrations to set up the database schema:
   ```bash
   python manage.py migrate
   ```

2. Create a superuser account:
   ```bash
   python manage.py createsuperuser
   ```

3. Run the test data initialization script to populate your database with sample data:
   ```bash
   python init_test_data.py
   ```

## Step 7: Run the Development Server

```bash
python manage.py runserver
```

Visit http://localhost:8000 in your browser to access the application.

## Step 8: Set Up Background Services

### Weather Update Service

Open a new terminal window and run:
```bash
python run_weather_update.py
```

### ML Model Training

Open another terminal window and run:
```bash
python run_model_training.py
```

## Accessing Your Data

### Database Management

You can use MySQL Workbench or phpMyAdmin to view and manage your data.

To connect using the MySQL command line:
```bash
mysql -u root -p -P 3305 barangay
```

Common queries for checking your data:

```sql
-- Check the municipalities in your system
SELECT * FROM core_municipality;

-- Check sensor data
SELECT * FROM core_sensordata ORDER BY timestamp DESC LIMIT 10;

-- Check barangays
SELECT * FROM core_barangay;

-- Check flood alerts
SELECT * FROM core_floodalert;
```

### Database Backup

To back up your data:

```bash
mysqldump -u root -p -P 3305 barangay > barangay_backup.sql
```

### Database Restore

To restore from a backup:

```bash
mysql -u root -p -P 3305 barangay < barangay_backup.sql
```

## Troubleshooting

### MySQL Connection Issues

1. **Wrong Port**: Ensure MySQL is running on port 3305
2. **Authentication Error**: Verify username and password
3. **Database Not Found**: Make sure you've created the 'barangay' database

### Django Errors

1. **Migrations Fail**: Check MySQL connection and privileges
2. **Missing Modules**: Ensure all dependencies are installed with `pip install -r requirements.txt`
3. **Static Files Not Loading**: Run `python manage.py collectstatic`

### Data Issues

1. **No Data Showing**: Check if initialization script ran successfully
2. **Weather Updates Not Working**: Ensure weather_update service is running

## Security Notes for Local Development

1. Keep DEBUG=True for development, but switch to False when exposing to a network
2. Use strong passwords for database access
3. Don't expose development server to the internet (it's not meant for production use)

## Next Steps

For a more production-like environment:

1. Install and configure Apache or Nginx as a front-end server
2. Set up Gunicorn or uWSGI as a WSGI server
3. Configure systemd services for background processes
4. Implement HTTPS using a self-signed certificate for testing
