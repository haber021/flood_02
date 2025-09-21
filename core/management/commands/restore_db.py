import os
import subprocess
import tempfile
from django.core.management.base import BaseCommand
from django.core import management
from django.conf import settings

class Command(BaseCommand):
    help = 'Restore the PostgreSQL database from a backup file'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            help='Path to the backup file to restore',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            default=False,
            help='Force restore without confirmation (use with caution)',
        )
        parser.add_argument(
            '--format',
            choices=['json', 'sql', 'auto'],
            default='auto',
            help='Specify the backup format (json, sql, or auto to detect from file extension)',
        )

    def handle(self, *args, **options):
        backup_file = options['backup_file']
        force = options['force']
        backup_format = options['format']
        
        # Check if the provided path is absolute or relative
        if not os.path.isabs(backup_file):
            # If relative, assume it's relative to the backups directory
            backups_dir = os.path.join(settings.BASE_DIR, 'backups')
            backup_file = os.path.join(backups_dir, backup_file)
        
        # Check if the backup file exists
        if not os.path.exists(backup_file):
            self.stdout.write(self.style.ERROR(
                f'Backup file not found: {backup_file}'
            ))
            return
        
        # Determine backup format if set to auto
        if backup_format == 'auto':
            if backup_file.endswith('.json'):
                backup_format = 'json'
            elif backup_file.endswith('.sql'):
                backup_format = 'sql'
            else:
                self.stdout.write(self.style.ERROR(
                    f"Could not determine backup format from file extension. "
                    f"Please specify format using --format option."
                ))
                return
        
        # Get database credentials from environment variables
        db_name = os.environ.get('PGDATABASE')
        db_user = os.environ.get('PGUSER')
        db_password = os.environ.get('PGPASSWORD')
        db_host = os.environ.get('PGHOST')
        db_port = os.environ.get('PGPORT')
        
        # Confirm with the user unless force option is provided
        if not force:
            self.stdout.write(self.style.WARNING(
                f'WARNING: This will overwrite the current database with data from {backup_file}.\n'
                f'All current data in the database "{db_name}" will be lost!'
            ))
            confirm = input('Are you sure you want to proceed? (yes/no): ')
            if confirm.lower() not in ('yes', 'y'):
                self.stdout.write(self.style.ERROR('Restore operation cancelled.'))
                return
        
        # Handle JSON backup format (using Django loaddata)
        if backup_format == 'json':
            try:
                # Flush the database to clear existing data
                self.stdout.write("Flushing database to clear existing data...")
                management.call_command('flush', interactive=False, verbosity=0)
                
                # Restore from JSON backup using loaddata
                self.stdout.write(f"Restoring data from JSON backup: {backup_file}")
                management.call_command('loaddata', backup_file, verbosity=1)
                
                self.stdout.write(self.style.SUCCESS(
                    f'Successfully restored database from {backup_file}'
                ))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Failed to restore database from JSON backup: {str(e)}'
                ))
        
        # Handle SQL backup format (using psql)
        else:  # sql format
            # Create restore command using psql
            psql_cmd = ['psql']
            
            if db_host:
                psql_cmd.extend(['-h', db_host])
            if db_port:
                psql_cmd.extend(['-p', db_port])
            if db_user:
                psql_cmd.extend(['-U', db_user])
                
            # Add database name
            if db_name:
                psql_cmd.extend(['-d', db_name])
                
            # Add file input option
            psql_cmd.extend(['-f', backup_file])
            
            # Set PGPASSWORD environment variable for the subprocess
            env = os.environ.copy()
            if db_password:
                env['PGPASSWORD'] = db_password
                
            try:
                # Execute psql command with timeout to restore the database
                self.stdout.write(f"Running: {' '.join(psql_cmd)}")
                result = subprocess.run(
                    psql_cmd,
                    env=env,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30  # 30 second timeout
                )
                
                self.stdout.write(self.style.SUCCESS(
                    f'Successfully restored database from {backup_file}'
                ))
                    
            except subprocess.TimeoutExpired:
                self.stdout.write(self.style.ERROR(
                    f'The psql restore command timed out after 30 seconds.'
                ))
            except subprocess.CalledProcessError as e:
                self.stdout.write(self.style.ERROR(
                    f'Failed to restore database: {e}\n'
                    f'Error output: {e.stderr.decode()}'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Unexpected error during restore: {str(e)}'
                ))
