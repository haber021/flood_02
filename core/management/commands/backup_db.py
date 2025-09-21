import os
import datetime
import subprocess
import tempfile
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core import management

class Command(BaseCommand):
    help = 'Backup the PostgreSQL database to a file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--filename',
            default=None,
            help='Specify a filename for the backup (defaults to flood_monitoring_backup_YYYY-MM-DD_HHMMSS.json)',
        )
        parser.add_argument(
            '--format',
            default='json',
            choices=['json', 'sql'],
            help='Specify the backup format (json or sql). JSON uses Django dumpdata, SQL uses pg_dump',
        )

    def handle(self, *args, **options):
        # Generate a default filename if not provided
        filename = options['filename']
        backup_format = options['format']
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
        
        if not filename:
            if backup_format == 'json':
                filename = f'flood_monitoring_backup_{timestamp}.json'
            else:  # sql format
                filename = f'flood_monitoring_backup_{timestamp}.sql'
        
        # Ensure the backups directory exists
        backups_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backups_dir, exist_ok=True)
        
        # Full path for the backup file
        backup_path = os.path.join(backups_dir, filename)
        
        if backup_format == 'json':
            try:
                # Use Django's dumpdata command to create a JSON backup
                self.stdout.write(f"Creating JSON backup using Django's dumpdata...")
                
                # Redirect output to a file
                with open(backup_path, 'w') as output_file:
                    # Call dumpdata for all apps and redirect output to file
                    management.call_command(
                        'dumpdata',
                        '--all',
                        '--indent=4',
                        stdout=output_file
                    )
                
                # Check if backup file was created and has content
                if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
                    self.stdout.write(self.style.SUCCESS(
                        f'Successfully backed up database to {backup_path}'
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'Backup file was created but appears to be empty.'
                    ))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Error creating JSON backup: {str(e)}'
                ))
        else:  # SQL format using pg_dump
            # Get database credentials from environment variables
            db_name = os.environ.get('PGDATABASE')
            db_user = os.environ.get('PGUSER')
            db_password = os.environ.get('PGPASSWORD')
            db_host = os.environ.get('PGHOST')
            db_port = os.environ.get('PGPORT')
            
            # Create backup command
            pg_dump_cmd = ['pg_dump']
            
            if db_host:
                pg_dump_cmd.extend(['-h', db_host])
            if db_port:
                pg_dump_cmd.extend(['-p', db_port])
            if db_user:
                pg_dump_cmd.extend(['-U', db_user])
                
            # Always specify format as plain SQL
            pg_dump_cmd.extend(['-F', 'p'])
            
            # Add database name
            if db_name:
                pg_dump_cmd.append(db_name)
                
            # Redirect output to file
            pg_dump_cmd.extend(['-f', backup_path])
            
            # Set PGPASSWORD environment variable for the subprocess
            env = os.environ.copy()
            if db_password:
                env['PGPASSWORD'] = db_password
                
            try:
                # Execute pg_dump command
                self.stdout.write(f"Running: {' '.join(pg_dump_cmd)}")
                
                # Set a timeout of 30 seconds for the pg_dump command
                result = subprocess.run(
                    pg_dump_cmd,
                    env=env,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30  # Timeout in seconds
                )
                
                # Check if backup file was created and has content
                if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
                    self.stdout.write(self.style.SUCCESS(
                        f'Successfully backed up database to {backup_path}'
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'Backup file was created but appears to be empty.'
                    ))
                    
            except subprocess.TimeoutExpired:
                self.stdout.write(self.style.ERROR(
                    f'The pg_dump command timed out after 30 seconds. '
                    f'Trying the Django dumpdata method instead...'
                ))
                
                # Fall back to Django's dumpdata for JSON output
                json_backup_path = backup_path.replace('.sql', '.json')
                try:
                    with open(json_backup_path, 'w') as output_file:
                        management.call_command('dumpdata', '--all', '--indent=4', stdout=output_file)
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'Successfully created fallback JSON backup at {json_backup_path}'
                    ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'Failed to create fallback JSON backup: {str(e)}'
                    ))
                    
            except subprocess.CalledProcessError as e:
                self.stdout.write(self.style.ERROR(
                    f'Failed to backup database: {e}\n'
                    f'Error output: {e.stderr.decode()}'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Unexpected error during backup: {str(e)}'
                ))
