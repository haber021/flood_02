#!/usr/bin/env python
"""
PostgreSQL to MySQL Migration Script for Flood Monitoring System

This script migrates data from a PostgreSQL database to a MySQL database for the
Flood Monitoring System. It handles the necessary format conversions and adaptations
for all relevant tables used in the system.

Usage:
    python pg_to_mysql_migration.py

Requires:
    - psycopg2-binary
    - mysqlclient
    - tqdm (for progress bars)

Set the database connection parameters at the top of the script before running.
"""

import os
import sys
import json
import datetime
import warnings

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Error: psycopg2 is required. Install it using 'pip install psycopg2-binary'")
    sys.exit(1)

try:
    import MySQLdb
except ImportError:
    print("Error: mysqlclient is required. Install it using 'pip install mysqlclient'")
    sys.exit(1)

try:
    from tqdm import tqdm
    SHOW_PROGRESS = True
except ImportError:
    SHOW_PROGRESS = False
    print("Warning: tqdm not installed. Progress bars will not be shown.")
    print("Install tqdm for progress bars using 'pip install tqdm'")

# PostgreSQL connection parameters
PG_PARAMS = {
    'database': 'flood_monitoring',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': '5432'
}

# MySQL connection parameters
MYSQL_PARAMS = {
    'db': 'barangay',
    'user': 'root',
    'passwd': 'root',
    'host': '127.0.0.1',
    'port': 3305,
    'charset': 'utf8mb4'
}

# List of tables to migrate, in dependency order
TABLES = [
    'auth_group',
    'auth_user',
    'django_content_type',
    'auth_permission',
    'auth_group_permissions',
    'auth_user_groups',
    'auth_user_user_permissions',
    'django_admin_log',
    'django_session',
    'core_municipality',
    'core_barangay',
    'core_userprofile',
    'core_floodriskzone',
    'core_sensor',
    'core_sensordata',
    'core_thresholdsetting',
    'core_floodalert',
    'core_floodalert_affected_barangays',
    'core_emergencycontact',
    'core_notificationlog',
    'core_resiliencescore'
]

def connect_to_postgres():
    """Connect to PostgreSQL database and return connection"""
    try:
        conn = psycopg2.connect(**PG_PARAMS)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        sys.exit(1)

def connect_to_mysql():
    """Connect to MySQL database and return connection"""
    try:
        conn = MySQLdb.connect(**MYSQL_PARAMS)
        return conn
    except MySQLdb.Error as e:
        print(f"Error connecting to MySQL: {e}")
        sys.exit(1)

def get_pg_tables(pg_conn):
    """Get list of tables in PostgreSQL database"""
    with pg_conn.cursor() as cursor:
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        return [row[0] for row in cursor.fetchall()]

def get_table_columns(pg_conn, table):
    """Get columns for a specific table"""
    with pg_conn.cursor() as cursor:
        cursor.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = '{table}'
            ORDER BY ordinal_position
        """)
        return [(row[0], row[1]) for row in cursor.fetchall()]

def get_table_data(pg_conn, table, columns):
    """Get all data from a table"""
    column_names = [col[0] for col in columns]
    query = f"SELECT {', '.join(column_names)} FROM {table}"
    
    with pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute(query)
        return cursor.fetchall()

def handle_value_conversion(value, data_type):
    """Convert PostgreSQL data types to MySQL compatible formats"""
    if value is None:
        return None
        
    # Handle JSON data
    if data_type in ('json', 'jsonb'):
        if isinstance(value, str):
            # Already stringified
            return value
        return json.dumps(value)
    
    # Handle boolean
    if data_type == 'boolean':
        return 1 if value else 0
    
    # Handle timestamp/date
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    
    if isinstance(value, datetime.date):
        return value.strftime('%Y-%m-%d')
    
    # Handle arrays (convert to comma-separated string)
    if data_type.startswith('ARRAY'):
        if value and isinstance(value, list):
            return ','.join(str(item) for item in value)
        return ''
    
    return value

def insert_into_mysql(mysql_conn, table, columns, data):
    """Insert data into MySQL table"""
    if not data:
        print(f"No data to insert for table {table}")
        return
        
    column_names = [col[0] for col in columns]
    placeholders = ", ".join("%s" for _ in column_names)
    
    query = f"INSERT INTO {table} ({', '.join(column_names)}) VALUES ({placeholders})"
    
    # Prepare the data with proper type conversions
    prepared_data = []
    for row in data:
        converted_row = []
        for i, col in enumerate(columns):
            column_name, data_type = col
            value = row[column_name]
            converted_value = handle_value_conversion(value, data_type)
            converted_row.append(converted_value)
        prepared_data.append(converted_row)
    
    # Insert data in batches to avoid memory issues
    with mysql_conn.cursor() as cursor:
        batch_size = 1000
        if SHOW_PROGRESS:
            for i in tqdm(range(0, len(prepared_data), batch_size), desc=f"Inserting {table}"):
                batch = prepared_data[i:i+batch_size]
                cursor.executemany(query, batch)
        else:
            for i in range(0, len(prepared_data), batch_size):
                print(f"Inserting {table} - batch {i//batch_size + 1}/{(len(prepared_data)-1)//batch_size + 1}")
                batch = prepared_data[i:i+batch_size]
                cursor.executemany(query, batch)
    
    mysql_conn.commit()
    print(f"✓ Successfully inserted {len(data)} rows into {table}")

def prepare_mysql_database(mysql_conn):
    """Prepare MySQL database by disabling constraints and clearing tables"""
    with mysql_conn.cursor() as cursor:
        # Disable foreign key checks temporarily
        cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
        mysql_conn.commit()
        print("Foreign key checks disabled for migration")

def cleanup_mysql_database(mysql_conn):
    """Re-enable constraints after migration"""
    with mysql_conn.cursor() as cursor:
        # Re-enable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
        mysql_conn.commit()
        print("Foreign key checks re-enabled")

def main():
    # Connect to both databases
    print("\n=== Flood Monitoring System Database Migration ===\n")
    print("Connecting to PostgreSQL...")
    pg_conn = connect_to_postgres()
    
    print("Connecting to MySQL...")
    mysql_conn = connect_to_mysql()
    
    # Get list of actual tables in PostgreSQL
    all_pg_tables = get_pg_tables(pg_conn)
    
    # Filter to only include tables that actually exist
    tables_to_migrate = [table for table in TABLES if table in all_pg_tables]
    missing_tables = [table for table in TABLES if table not in all_pg_tables]
    
    if missing_tables:
        print(f"Warning: The following tables were not found in PostgreSQL and will be skipped:")
        for table in missing_tables:
            print(f"  - {table}")
    
    # Confirm with user
    print(f"\nReady to migrate {len(tables_to_migrate)} tables from PostgreSQL to MySQL.")
    confirm = input("Continue? (y/n): ")
    if confirm.lower() != 'y':
        print("Migration cancelled.")
        return
    
    # Prepare MySQL database
    prepare_mysql_database(mysql_conn)
    
    try:
        # Migrate each table
        print(f"\nStarting migration of {len(tables_to_migrate)} tables...\n")
        
        for table in tables_to_migrate:
            print(f"Processing table: {table}")
            columns = get_table_columns(pg_conn, table)
            data = get_table_data(pg_conn, table, columns)
            print(f"Retrieved {len(data)} rows from {table}")
            
            insert_into_mysql(mysql_conn, table, columns, data)
            print(f"Completed migration of table: {table}\n")
        
        # Re-enable constraints
        cleanup_mysql_database(mysql_conn)
        
        print("\n=== Migration Complete ===\n")
        print(f"Successfully migrated {len(tables_to_migrate)} tables from PostgreSQL to MySQL.")
        
    except Exception as e:
        print(f"\nError during migration: {e}")
        print("Rolling back and re-enabling foreign key checks...")
        mysql_conn.rollback()
        cleanup_mysql_database(mysql_conn)
        print("Migration failed. The database may be in an inconsistent state.")
    
    finally:
        # Close connections
        pg_conn.close()
        mysql_conn.close()

if __name__ == "__main__":
    # Suppress MySQL warnings about displaying passwords in connection strings
    warnings.filterwarnings('ignore', category=MySQLdb.Warning)
    main()
