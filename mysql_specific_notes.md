# MySQL-Specific Notes for Deployment

## Database Preparation for Migration

### 1. Install MySQL at Port 3305

This application is configured to use MySQL on port 3305. If you need to configure MySQL to use this specific port:

#### For Linux:

1. Edit the MySQL configuration file `/etc/mysql/my.cnf` and add:
   ```
   [mysqld]
   port = 3305
   ```

2. Restart MySQL:
   ```bash
   sudo systemctl restart mysql
   ```

#### For Windows:

1. Edit the MySQL configuration file (usually at `C:\ProgramData\MySQL\MySQL Server x.x\my.ini`) and set:
   ```
   [mysqld]
   port=3305
   ```

2. Restart MySQL service from Services management console

### 2. Create Database and Set Character Set

```sql
CREATE DATABASE barangay CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Optimize MySQL for the Flood Monitoring System

Add the following to your MySQL configuration file for better performance:

```
[mysqld]
innodb_buffer_pool_size = 256M  # Adjust based on your server RAM
innodb_log_file_size = 64M
max_connections = 100
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

## Django Model Field Considerations

When working with MySQL as your database backend, consider these differences from PostgreSQL:

### 1. Text Fields

MySQL has several text field types with different storage capacities:
- `TINYTEXT`: Up to 255 bytes
- `TEXT`: Up to 65,535 bytes
- `MEDIUMTEXT`: Up to 16,777,215 bytes
- `LONGTEXT`: Up to 4,294,967,295 bytes

Django's TextField maps to TEXT by default, which may not be enough for very large content. If you need larger storage, you can specify it in your model:

```python
from django.db import models

class LargeContentModel(models.Model):
    content = models.TextField()
    
    class Meta:
        db_table = 'large_content'
```

And then create a database migration that alters the field type:

```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [...]
    
    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE large_content MODIFY content LONGTEXT;',
            reverse_sql='ALTER TABLE large_content MODIFY content TEXT;'
        ),
    ]
```

### 2. JSON Fields

MySQL 5.7+ supports native JSON fields, but with syntax differences:

**PostgreSQL**:
```sql
SELECT data->>'key' FROM table;
```

**MySQL**:
```sql
SELECT JSON_EXTRACT(data, '$.key') FROM table;
```

In Django, use `KeyTextTransform` in your queries:

```python
from django.db.models import F
from django.db.models.functions import Cast
from django.db.models.fields.json import KeyTextTransform

# Query with JSON field in MySQL
queryset = Model.objects.annotate(
    key_value=KeyTextTransform('key', 'json_field')
).filter(key_value='value')
```

### 3. Index Considerations

MySQL has a maximum index length of 767 bytes (or 3072 bytes for InnoDB with innodb_large_prefix enabled). For UTF8MB4 encoding, this limits indexed VARCHAR fields to 191 characters.

When creating indexes on VARCHAR fields, keep this limit in mind:

```python
class MyModel(models.Model):
    # This will work well with MySQL indexing
    email = models.CharField(max_length=191, db_index=True)
    
    # This might cause index issues if fully indexed
    long_field = models.CharField(max_length=255)
```

## Backup and Restore Procedures for MySQL

### Backup Database

```bash
mysqldump -P 3305 -u root -p barangay > barangay_backup.sql
```

### Restore Database

```bash
mysql -P 3305 -u root -p barangay < barangay_backup.sql
```

### Automated Backups

Create a cron job for regular backups:

```bash
# Add to crontab (run 'crontab -e')
0 2 * * * mysqldump -P 3305 -u root -p'root' barangay > /path/to/backups/barangay_$(date +\%Y\%m\%d).sql
```

## Performance Monitoring

For MySQL performance monitoring, you can use:

```sql
-- Check slow queries
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- View currently running queries
SHOW PROCESSLIST;

-- Check table status
SHOW TABLE STATUS;

-- Check index usage
SELECT
  TABLE_NAME,
  INDEX_NAME,
  CARDINALITY
FROM
  INFORMATION_SCHEMA.STATISTICS
WHERE
  TABLE_SCHEMA = 'barangay'
ORDER BY
  TABLE_NAME, INDEX_NAME;
```

## Common MySQL Connection Issues

1. **Error:** "Can't connect to MySQL server on '127.0.0.1' (10061)"
   **Solution:** Check that MySQL is running and listening on port 3305

2. **Error:** "Access denied for user 'root'@'localhost'"
   **Solution:** Verify username and password credentials

3. **Error:** "Unknown database 'barangay'"
   **Solution:** Create the database first with `CREATE DATABASE barangay;`

4. **Error:** "Too many connections"
   **Solution:** Increase max_connections in MySQL configuration or optimize connection pooling