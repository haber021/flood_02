import logging
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from core.models import UserProfile, Sensor, SensorData, Municipality, Barangay, FloodAlert, ThresholdSetting

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Initialize user roles and permissions for the flood monitoring system'

    def handle(self, *args, **options):
        self.stdout.write('Creating user roles and permissions...')
        
        # Create user groups
        admin_group, created = Group.objects.get_or_create(name='Administrators')
        managers_group, created = Group.objects.get_or_create(name='Flood Managers')
        officers_group, created = Group.objects.get_or_create(name='Municipal Officers')
        operators_group, created = Group.objects.get_or_create(name='System Operators')
        viewers_group, created = Group.objects.get_or_create(name='Viewers')
        
        # Get content types for our models
        sensor_ct = ContentType.objects.get_for_model(Sensor)
        sensor_data_ct = ContentType.objects.get_for_model(SensorData)
        municipality_ct = ContentType.objects.get_for_model(Municipality)
        barangay_ct = ContentType.objects.get_for_model(Barangay)
        alert_ct = ContentType.objects.get_for_model(FloodAlert)
        threshold_ct = ContentType.objects.get_for_model(ThresholdSetting)
        user_ct = ContentType.objects.get_for_model(User)
        profile_ct = ContentType.objects.get_for_model(UserProfile)
        
        # Define permissions for each role
        # Administrators - Full access to everything
        admin_perms = Permission.objects.filter(
            content_type__in=[sensor_ct, sensor_data_ct, municipality_ct, barangay_ct, alert_ct, threshold_ct, user_ct, profile_ct])
        admin_group.permissions.set(admin_perms)
        
        # Flood Managers - Can manage alerts, sensors, thresholds
        manager_perms = Permission.objects.filter(
            content_type__in=[sensor_ct, sensor_data_ct, alert_ct, threshold_ct])
        managers_group.permissions.set(manager_perms)
        
        # Municipal Officers - Can view everything, create alerts
        view_perms = Permission.objects.filter(codename__startswith='view_')
        add_alert_perm = Permission.objects.get(content_type=alert_ct, codename='add_floodalert')
        change_alert_perm = Permission.objects.get(content_type=alert_ct, codename='change_floodalert')
        officer_perms = list(view_perms) + [add_alert_perm, change_alert_perm]
        officers_group.permissions.set(officer_perms)
        
        # System Operators - Can manage sensors and view data
        add_sensor_perm = Permission.objects.get(content_type=sensor_ct, codename='add_sensor')
        change_sensor_perm = Permission.objects.get(content_type=sensor_ct, codename='change_sensor')
        add_data_perm = Permission.objects.get(content_type=sensor_data_ct, codename='add_sensordata')
        operator_perms = list(view_perms) + [add_sensor_perm, change_sensor_perm, add_data_perm]
        operators_group.permissions.set(operator_perms)
        
        # Data Viewers - Can only view data
        viewers_group.permissions.set(view_perms)
        
        # Update existing admin user to have admin role
        try:
            admin_user = User.objects.get(username='admin')
            # Create profile if it doesn't exist
            if not hasattr(admin_user, 'profile'):
                UserProfile.objects.create(user=admin_user, role='admin')
            else:
                admin_user.profile.role = 'admin'
                admin_user.profile.save()
            admin_user.groups.add(admin_group)
            self.stdout.write(self.style.SUCCESS(f'Updated admin user with admin role'))
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING('Admin user not found, skipping'))
            
        # Create default users for each role if they don't exist
        self._create_test_user('manager', 'Flood Manager', managers_group, 'manager')
        self._create_test_user('officer', 'Municipal Officer', officers_group, 'officer')
        self._create_test_user('operator', 'System Operator', operators_group, 'operator')
        self._create_test_user('viewer', 'Data Viewer', viewers_group, 'viewer')
        
        self.stdout.write(self.style.SUCCESS('Successfully created user roles and permissions'))
        
    def _create_test_user(self, username, first_name, group, role):
        """Helper to create test users"""
        if not User.objects.filter(username=username).exists():
            user = User.objects.create_user(
                username=username,
                email=f'{username}@example.com',
                password='password123',
                first_name=first_name,
                last_name='User',
                is_staff=True  # Needed for admin access
            )
            user.groups.add(group)
            # Create profile if it doesn't exist
            if not hasattr(user, 'profile'):
                profile = UserProfile.objects.create(user=user, role=role)
            else:
                user.profile.role = role
                user.profile.save()
            self.stdout.write(f'Created test user: {username} ({role})')
