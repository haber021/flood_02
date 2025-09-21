import os
import subprocess
import datetime
import mimetypes
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse
from django.core.management import call_command
from io import StringIO

# Helper function to check if user is an admin
def is_admin(user):
    return user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'admin')

# Get a list of backup files with their information
def get_backup_files():
    backups_dir = os.path.join(settings.BASE_DIR, 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    
    backup_files = []
    
    if os.path.exists(backups_dir):
        # Get all SQL files in the backups directory
        files = [f for f in os.listdir(backups_dir) if f.endswith('.sql')]
        
        for filename in files:
            file_path = os.path.join(backups_dir, filename)
            size_bytes = os.path.getsize(file_path)
            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # Calculate human-readable size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes/1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                size_str = f"{size_bytes/(1024*1024):.1f} MB"
            else:
                size_str = f"{size_bytes/(1024*1024*1024):.1f} GB"
                
            backup_files.append({
                'filename': filename,
                'size': size_str,
                'modified': mod_time.strftime('%Y-%m-%d %H:%M:%S'),
                'filepath': file_path
            })
        
        # Sort by modified date (newest first)
        backup_files.sort(key=lambda x: x['modified'], reverse=True)
    
    return backup_files

# View for database management page
@login_required
@user_passes_test(is_admin)
def database_management(request):
    backups = get_backup_files()
    
    context = {
        'backups': backups,
        'active_page': 'database_management'
    }
    
    return render(request, 'database_management.html', context)

# View for creating database backup
@login_required
@user_passes_test(is_admin)
def create_backup(request):
    if request.method == 'POST':
        filename = request.POST.get('backup_filename')
        backup_format = request.POST.get('backup_format', 'json')
        
        # Capture output from the management command
        output = StringIO()
        
        try:
            # Call the backup_db management command
            if filename:
                call_command('backup_db', filename=filename, format=backup_format, stdout=output)
            else:
                call_command('backup_db', format=backup_format, stdout=output)
            
            # Get the command output
            result = output.getvalue().strip()
            
            # Check if it was successful
            if 'Successfully backed up database' in result:
                messages.success(request, 'Database backup created successfully.')
            else:
                messages.warning(request, f'Backup completed with warnings: {result}')
                
        except Exception as e:
            messages.error(request, f'Failed to create backup: {str(e)}')
    
    return redirect('database_management')

# View for restoring database from backup
@login_required
@user_passes_test(is_admin)
def restore_backup(request):
    if request.method == 'POST':
        backup_file = request.POST.get('restore_file')
        confirm_restore = request.POST.get('confirm_restore') == 'on'
        
        if not backup_file:
            messages.error(request, 'No backup file selected for restore.')
            return redirect('database_management')
        
        if not confirm_restore:
            messages.error(request, 'You must confirm that you understand the restore action.')
            return redirect('database_management')
        
        # Determine backup format from file extension
        backup_format = 'auto'  # Let the restore command auto-detect
        
        # Capture output from the management command
        output = StringIO()
        
        try:
            # Call the restore_db management command with force option
            call_command('restore_db', backup_file, force=True, format=backup_format, stdout=output)
            
            # Get the command output
            result = output.getvalue().strip()
            
            # Check if it was successful
            if 'Successfully restored database' in result:
                messages.success(request, 'Database restored successfully.')
            else:
                messages.warning(request, f'Restore completed with warnings: {result}')
                
        except Exception as e:
            messages.error(request, f'Failed to restore database: {str(e)}')
    
    return redirect('database_management')

# View for downloading a backup file
@login_required
@user_passes_test(is_admin)
def download_backup(request, filename):
    backups_dir = os.path.join(settings.BASE_DIR, 'backups')
    file_path = os.path.join(backups_dir, filename)
    
    if not os.path.exists(file_path):
        raise Http404("Backup file does not exist")
    
    # Set the content type for the file
    content_type, encoding = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'
    
    # Return the file as a response
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

# View for deleting a backup file
@login_required
@user_passes_test(is_admin)
def delete_backup(request, filename):
    backups_dir = os.path.join(settings.BASE_DIR, 'backups')
    file_path = os.path.join(backups_dir, filename)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            messages.success(request, f'Backup {filename} deleted successfully.')
        except Exception as e:
            messages.error(request, f'Failed to delete backup {filename}: {str(e)}')
    else:
        messages.warning(request, f'Backup file {filename} not found.')
    
    return redirect('database_management')
