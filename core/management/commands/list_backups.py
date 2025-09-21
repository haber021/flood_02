import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'List all available database backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sort',
            choices=['name', 'date', 'size'],
            default='date',
            help='Sort backups by name, date, or size (default: date)',
        )
        parser.add_argument(
            '--reverse',
            action='store_true',
            default=False,
            help='Reverse the sort order',
        )

    def handle(self, *args, **options):
        # Get the backups directory
        backups_dir = os.path.join(settings.BASE_DIR, 'backups')
        
        # Create the directory if it doesn't exist
        if not os.path.exists(backups_dir):
            os.makedirs(backups_dir, exist_ok=True)
            self.stdout.write(self.style.WARNING('No backups found (directory was just created)'))
            return
        
        # Get all SQL files in the backups directory
        backup_files = [f for f in os.listdir(backups_dir) if f.endswith('.sql')]
        
        if not backup_files:
            self.stdout.write(self.style.WARNING('No backup files found'))
            return
        
        # Get sort option
        sort_by = options['sort']
        reverse_sort = options['reverse']
        
        # Prepare file information for sorting and display
        file_info = []
        for filename in backup_files:
            file_path = os.path.join(backups_dir, filename)
            size_bytes = os.path.getsize(file_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # Calculate human-readable size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes/1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                size_str = f"{size_bytes/(1024*1024):.1f} MB"
            else:
                size_str = f"{size_bytes/(1024*1024*1024):.1f} GB"
                
            file_info.append({
                'filename': filename,
                'size': size_bytes,
                'size_str': size_str,
                'modified': mod_time,
                'modified_str': mod_time.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Sort by requested parameter
        if sort_by == 'name':
            file_info.sort(key=lambda x: x['filename'], reverse=reverse_sort)
        elif sort_by == 'size':
            file_info.sort(key=lambda x: x['size'], reverse=reverse_sort)
        else:  # default: sort by date
            file_info.sort(key=lambda x: x['modified'], reverse=reverse_sort)
        
        # Display the backup files
        self.stdout.write(self.style.SUCCESS(f'Found {len(file_info)} backup files:'))
        self.stdout.write("\n{:<40} {:<15} {:<20}".format('Filename', 'Size', 'Modified'))
        self.stdout.write("-" * 75)
        
        for info in file_info:
            self.stdout.write("{:<40} {:<15} {:<20}".format(
                info['filename'],
                info['size_str'],
                info['modified_str']
            ))
