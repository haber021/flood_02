# MySQL Migration Guide for Flood Monitoring System

## Overview

This guide outlines the process for migrating the Flood Monitoring System from PostgreSQL to MySQL. Follow these steps to ensure a smooth transition.

## Pre-Migration Steps

### 1. Backup Your Current PostgreSQL Database

```bash
pg_dump -U postgres -d flood_monitoring > flood_monitoring_backup.sql
```

### 2. Install MySQL and Required Python Packages

```bash
# Install MySQL server
sudo apt-get update
sudo apt-get install mysql-server

# Install Python MySQL packages
pip install mysqlclient==2.2.4 PyMySQL==1.1.0
```

## Database Setup

### 1. Create MySQL Database

```sql
CREATE DATABASE barangay CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Create MySQL User (Optional - If Not Using Root)

```sql
CREATE USER 'flooduser'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON barangay.* TO 'flooduser'@'localhost';
FLUSH PRIVILEGES;
```

## Configuration Changes

### 1. Update settings.py

Replace the existing PostgreSQL configuration with:

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

### 2. Add MySQL Configuration (my.cnf)

Create or edit `/etc/mysql/my.cnf` to include:

```ini
[client]
default-character-set = utf8mb4

[mysql]
default-character-set = utf8mb4

[mysqld]
port = 3305
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

## Migration Process

### 1. Reset Django Migrations (Optional)

If you want to start fresh with migrations:

```bash
# Delete all migration files (except __init__.py)
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

# Create new migrations
python manage.py makemigrations
```

### 2. Apply Migrations to MySQL

```bash
python manage.py migrate
```

### 3. Load Data (If Starting Fresh)

```bash
# Create a superuser
python manage.py createsuperuser

# Run your data initialization script
python init_test_data.py
```

## Database Specific Considerations

### 1. Field Type Differences

- **PostgreSQL TEXT vs MySQL TEXT**: MySQL has various TEXT types (TINYTEXT, TEXT, MEDIUMTEXT, LONGTEXT) with different size limits
- **JSON Fields**: MySQL 5.7+ supports JSON data type, but with different functions
- **Array Fields**: MySQL doesn't support array types; consider using JSON or separate tables

### 2. Function Differences

- **Substring**: In MySQL, use `SUBSTRING()` instead of PostgreSQL's `SUBSTR()`
- **Concatenation**: In MySQL, use `CONCAT()` function instead of the `||` operator
- **Case Sensitivity**: MySQL is case-insensitive by default

### 3. Update ORM Usage

Review your codebase for any PostgreSQL-specific ORM functionality:

- Replace any PostgreSQL-specific lookups (e.g., `__search`) with MySQL-compatible alternatives
- Update any raw SQL queries to use MySQL syntax

## Testing

### 1. Verify Data Integrity

```bash
# Run Django shell
python manage.py shell

# Example verification code
from core.models import Sensor, SensorData, Municipality, Barangay
print(f"Sensors: {Sensor.objects.count()}")
print(f"Sensor Data: {SensorData.objects.count()}")
print(f"Municipalities: {Municipality.objects.count()}")
print(f"Barangays: {Barangay.objects.count()}")
```

### 2. Test Application Functionality

Test all functionality to ensure proper database interaction:

- User authentication
- Sensor data display
- Flood alerts
- Prediction algorithms
- Map visualization

## Troubleshooting

### Common Issues

1. **Connection Refused**: 
   - Verify MySQL is running on port 3305 (`sudo systemctl status mysql`)
   - Check firewall settings (`sudo ufw status`)

2. **Authentication Issues**:
   - Verify username and password
   - Check user privileges (`SHOW GRANTS FOR 'root'@'localhost';`)

3. **Migration Errors**:
   - For foreign key issues, try temporarily setting `FOREIGN_KEY_CHECKS=0`
   - For max key length issues, make sure you're using the utf8mb4 charset

4. **Performance Issues**:
   - Review index usage (`EXPLAIN SELECT ...`)
   - Check MySQL configuration for proper memory allocation

## Post-Migration

### 1. Update Backup Scripts

Update your backup scripts to use mysqldump instead of pg_dump:

```bash
mysqldump -u root -p'root' barangay > barangay_backup.sql
```

### 2. Update Cron Jobs and Services

Ensure all cron jobs and systemd services that interact with the database have been updated with the new configuration.

### 3. Performance Tuning

Optimize MySQL for your specific needs:

```ini
[mysqld]
innodb_buffer_pool_size = 512M  # Adjust based on your server RAM
innodb_log_file_size = 128M
max_connections = 100
```

## Conclusion

After following this guide, your Flood Monitoring System should be successfully migrated from PostgreSQL to MySQL. Monitor the system closely for a few days to ensure everything is functioning correctly with the new database backend.
