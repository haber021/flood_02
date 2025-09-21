#!/usr/bin/env python
"""
MySQL Setup Script for Flood Monitoring System

This script automates the setup of MySQL for local development:
1. Checks if MySQL is running on port 3305
2. Creates the 'barangay' database if it doesn't exist
3. Updates Django settings to use the MySQL database
4. Applies migrations

Usage:
    python setup_mysql_local.py
"""

import os
import sys
import subprocess
import socket
import getpass
import time

# MySQL connection parameters
MYSQL_HOST = '127.0.0.1'
MYSQL_PORT = 3305
MYSQL_DB = 'barangay'

# Django project details
SETTINGS_FILE = 'flood_monitoring/settings.py'
MANAGE_PY = 'manage.py'

def check_mysql_connection(host, port, user, password):
    """Check if MySQL server is accessible on the specified port"""
    try:
        # First, check if the port is open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result != 0:
            print(f"\n❌ MySQL is not running on port {port}.")
            print(f"Please make sure MySQL is running and configured to use port {port}.")
            return False
            
        # Now check if we can connect with credentials
        try:
            import MySQLdb
            conn = MySQLdb.connect(
                host=host,
                port=port,
                user=user,
                passwd=password
            )
            conn.close()
            return True
        except MySQLdb.Error as e:
            if e.args[0] == 1045:  # Access denied error
                print(f"\n❌ MySQL connection failed: Access denied for user '{user}'.")
                return False
            else:
                print(f"\n❌ MySQL connection error: {e}")
                return False
    except Exception as e:
        print(f"\n❌ Error checking MySQL connection: {e}")
        return False

def create_database(host, port, user, password, db_name):
    """Create database if it doesn't exist"""
    try:
        import MySQLdb
        
        # Connect to MySQL
        conn = MySQLdb.connect(
            host=host,
            port=port,
            user=user,
            passwd=password
        )
        
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SHOW DATABASES LIKE '{db_name}'")
        result = cursor.fetchone()
        
        if result:
            print(f"\n✅ Database '{db_name}' already exists.")
        else:
            # Create database with UTF8MB4 charset
            cursor.execute(f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"\n✅ Database '{db_name}' created successfully with UTF8MB4 charset.")
        
        conn.close()
        return True
    except MySQLdb.Error as e:
        print(f"\n❌ Database creation error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error creating database: {e}")
        return False

def update_django_settings():
    """Update Django settings to use MySQL"""
    try:
        # Check if settings file exists
        if not os.path.exists(SETTINGS_FILE):
            print(f"\n❌ Django settings file not found at {SETTINGS_FILE}")
            return False
        
        # Read current settings
        with open(SETTINGS_FILE, 'r') as f:
            settings_content = f.read()
        
        # Check if MySQL is already configured
        if "'ENGINE': 'django.db.backends.mysql'" in settings_content:
            print("\n✅ Django settings already configured for MySQL.")
            return True
        
        # Create a backup of the original settings
        backup_file = f"{SETTINGS_FILE}.bak"
        if not os.path.exists(backup_file):
            with open(backup_file, 'w') as f:
                f.write(settings_content)
            print(f"\n✅ Created backup of original settings at {backup_file}")
        
        # Check if local_settings import is already present
        if "from .local_settings import *" not in settings_content:
            # Add import line at the end of the file
            with open(SETTINGS_FILE, 'a') as f:
                f.write("\n\n# Import local settings for MySQL configuration\n")
                f.write("try:\n")
                f.write("    from .local_settings import *\n")
                f.write("except ImportError:\n")
                f.write("    pass\n")
            
            print("\n✅ Updated Django settings to import local MySQL configuration.")
        else:
            print("\n✅ Django settings already set up to import local configuration.")
        
        # Copy local_settings.py to the flood_monitoring directory if it exists
        if os.path.exists('local_settings.py') and not os.path.exists('flood_monitoring/local_settings.py'):
            # Create the destination directory if it doesn't exist
            os.makedirs('flood_monitoring', exist_ok=True)
            
            # Read the content and update BASE_DIR path if needed
            with open('local_settings.py', 'r') as f:
                local_settings_content = f.read()
            
            # Update BASE_DIR path for the new location
            local_settings_content = local_settings_content.replace(
                "BASE_DIR = Path(__file__).resolve().parent",
                "BASE_DIR = Path(__file__).resolve().parent.parent"
            )
            
            # Write the updated content to the destination file
            with open('flood_monitoring/local_settings.py', 'w') as f:
                f.write(local_settings_content)
                
            print("\n✅ Copied local_settings.py to flood_monitoring directory with adjusted paths.")
        
        return True
    except Exception as e:
        print(f"\n❌ Error updating Django settings: {e}")
        return False

def apply_migrations():
    """Apply Django migrations to set up the database"""
    try:
        # Check if manage.py exists
        if not os.path.exists(MANAGE_PY):
            print(f"\n❌ Django manage.py file not found at {MANAGE_PY}")
            return False
        
        print("\n🔄 Applying migrations to set up the MySQL database schema...")
        subprocess.run([sys.executable, MANAGE_PY, 'migrate'], check=True)
        
        print("\n✅ Migrations applied successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error applying migrations: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error during migration process: {e}")
        return False

def main():
    print("\n===== MySQL Setup for Flood Monitoring System =====\n")
    
    # Get MySQL credentials
    print("Please enter your MySQL credentials:")
    user = input("Username [root]: ") or "root"
    password = getpass.getpass("Password [root]: ") or "root"
    
    # Check MySQL connection
    print(f"\n🔄 Checking MySQL connection on port {MYSQL_PORT}...")
    if not check_mysql_connection(MYSQL_HOST, MYSQL_PORT, user, password):
        port_fix = input("\nWould you like to try a different port? (y/n): ")
        if port_fix.lower() == 'y':
            try:
                new_port = int(input("Enter MySQL port [3306]: ") or 3306)
                global MYSQL_PORT
                MYSQL_PORT = new_port
                
                print(f"\n🔄 Checking MySQL connection on port {MYSQL_PORT}...")
                if not check_mysql_connection(MYSQL_HOST, MYSQL_PORT, user, password):
                    print("\n❌ MySQL connection failed. Please check your MySQL installation and credentials.")
                    return False
            except ValueError:
                print("\n❌ Invalid port number. Exiting.")
                return False
        else:
            print("\n❌ MySQL connection failed. Please check your MySQL installation and credentials.")
            return False
    
    # Create database
    print(f"\n🔄 Setting up database '{MYSQL_DB}'...")
    if not create_database(MYSQL_HOST, MYSQL_PORT, user, password, MYSQL_DB):
        return False
    
    # Update Django settings
    print("\n🔄 Updating Django settings to use MySQL...")
    if not update_django_settings():
        return False
    
    # Apply migrations
    apply_migrations_choice = input("\nWould you like to apply database migrations now? (y/n): ")
    if apply_migrations_choice.lower() == 'y':
        if not apply_migrations():
            return False
    
    print("\n🎉 MySQL setup completed successfully!")
    print("\nTo start the development server, run: python manage.py runserver")
    
    return True

if __name__ == "__main__":
    try:
        # Check if MySQLdb is installed
        import MySQLdb
    except ImportError:
        print("\n❌ Required package 'mysqlclient' is not installed.")
        install_choice = input("Would you like to install it now? (y/n): ")
        if install_choice.lower() == 'y':
            try:
                print("\n🔄 Installing mysqlclient...")
                subprocess.run([sys.executable, "-m", "pip", "install", "mysqlclient"], check=True)
                # Give the system a moment to complete the installation
                time.sleep(2)
                print("\n✅ mysqlclient installed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"\n❌ Error installing mysqlclient: {e}")
                print("Please install it manually: pip install mysqlclient")
                sys.exit(1)
        else:
            print("Please install it manually: pip install mysqlclient")
            sys.exit(1)
    
    # Run main setup process
    success = main()
    sys.exit(0 if success else 1)
