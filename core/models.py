from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError

class Sensor(models.Model):
    """Model for environmental sensors in the system"""
    name = models.CharField(max_length=100)
    sensor_type = models.CharField(max_length=50, choices=[
        ('temperature', 'Temperature'),
        ('humidity', 'Humidity'),
        ('rainfall', 'Rainfall'),
        ('water_level', 'Water Level'),
        ('wind_speed', 'Wind Speed'),
    ])
    latitude = models.FloatField()
    longitude = models.FloatField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    municipality = models.ForeignKey('Municipality', on_delete=models.CASCADE, related_name='sensors', null=True, blank=True)
    barangay = models.ForeignKey('Barangay', on_delete=models.CASCADE, related_name='sensors', null=True, blank=True)
    description = models.TextField(blank=True, null=True)  # Add this field

    
    def __str__(self):
        return f"{self.name} ({self.sensor_type})"

class SensorData(models.Model):
    """Model for storing sensor readings"""
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='readings')
    value = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.sensor.name}: {self.value} ({self.timestamp})"

class Municipality(models.Model):
    """Model for municipality data"""
    name = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    population = models.IntegerField()
    area_sqkm = models.FloatField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name}, {self.province}"

    def clean(self):
        super().clean()
        # Prevent duplicate coordinates within Municipality and across Barangay
        if self.latitude is not None and self.longitude is not None:
            # Exact duplicate within municipalities (excluding self)
            if Municipality.objects.filter(latitude=self.latitude, longitude=self.longitude).exclude(pk=self.pk).exists():
                raise ValidationError({
                    'latitude': 'These coordinates are already used by another municipality.',
                    'longitude': 'These coordinates are already used by another municipality.',
                })
            # Cross-model duplicate: same coordinates as a barangay
            if Barangay.objects.filter(latitude=self.latitude, longitude=self.longitude).exists():
                raise ValidationError('These coordinates are already used by an existing barangay. Please provide distinct coordinates for the municipality center.')

    def save(self, *args, **kwargs):
        # Ensure validations run on every save (admin, forms, API)
        self.full_clean()
        return super().save(*args, **kwargs)
    
    class Meta:
        verbose_name_plural = "Municipalities"

class Barangay(models.Model):
    """Model for barangay (neighborhood/village) data"""
    name = models.CharField(max_length=100)
    municipality = models.ForeignKey(Municipality, on_delete=models.CASCADE, related_name='barangays', null=True)
    population = models.IntegerField()
    area_sqkm = models.FloatField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # Prevent duplicate coordinates within Barangay and across Municipality
        if self.latitude is not None and self.longitude is not None:
            # Exact duplicate within barangays (excluding self)
            if Barangay.objects.filter(latitude=self.latitude, longitude=self.longitude).exclude(pk=self.pk).exists():
                raise ValidationError({
                    'latitude': 'These coordinates are already used by another barangay.',
                    'longitude': 'These coordinates are already used by another barangay.',
                })
            # Cross-model duplicate: same coordinates as a municipality
            if Municipality.objects.filter(latitude=self.latitude, longitude=self.longitude).exists():
                raise ValidationError('These coordinates are already used by an existing municipality. Please provide distinct coordinates for the barangay center.')

    def save(self, *args, **kwargs):
        # Ensure validations run on every save (admin, forms, API)
        self.full_clean()
        return super().save(*args, **kwargs)
    
    class Meta:
        verbose_name_plural = "Barangays"

class FloodRiskZone(models.Model):
    """Model for flood risk zones"""
    name = models.CharField(max_length=100)
    severity_level = models.IntegerField(choices=[
        (1, 'Low Risk'),
        (2, 'Medium Risk'),
        (3, 'High Risk'),
        (4, 'Severe Risk'),
        (5, 'Extreme Risk'),
    ])
    description = models.TextField(blank=True, null=True)
    # GeoJSON data for map visualization
    geojson = models.TextField()
    
    def __str__(self):
        return f"{self.name} (Level {self.severity_level})"

class FloodAlert(models.Model):
    """Model for flood alerts/warnings"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity_level = models.IntegerField(choices=[
        (1, 'Advisory'),
        (2, 'Watch'),
        (3, 'Warning'),
        (4, 'Emergency'),
        (5, 'Catastrophic'),
    ])
    active = models.BooleanField(default=True)
    predicted_flood_time = models.DateTimeField(blank=True, null=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    affected_barangays = models.ManyToManyField(Barangay, related_name='flood_alerts')
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.get_severity_level_display()}: {self.title}"
    
    class Meta:
        ordering = ['-issued_at']

class ThresholdSetting(models.Model):
    """Model for threshold settings for alerts"""
    parameter = models.CharField(max_length=50, choices=[
        ('temperature', 'Temperature'),
        ('humidity', 'Humidity'),
        ('rainfall', 'Rainfall'),
        ('water_level', 'Water Level'),
        ('wind_speed', 'Wind Speed'),
    ])
    advisory_threshold = models.FloatField()
    watch_threshold = models.FloatField()
    warning_threshold = models.FloatField()
    emergency_threshold = models.FloatField()
    catastrophic_threshold = models.FloatField()
    unit = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def clean(self):
        msg = "Thresholds must be strictly increasing: Advisory < Watch < Warning < Emergency < Catastrophic."
        a = self.advisory_threshold
        w = self.watch_threshold
        wn = self.warning_threshold
        e = self.emergency_threshold
        c = self.catastrophic_threshold
        # Only validate when all values are present
        if None not in (a, w, wn, e, c):
            if not (a < w < wn < e < c):
                raise ValidationError({
                    'advisory_threshold': msg,
                    'watch_threshold': msg,
                    'warning_threshold': msg,
                    'emergency_threshold': msg,
                    'catastrophic_threshold': msg,
                })
    
    def save(self, *args, **kwargs):
        # Ensure model-level validation runs on every save
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.parameter} Thresholds"
    
    class Meta:
        unique_together = ['parameter']

class NotificationLog(models.Model):
    """Model for logging notifications sent"""
    alert = models.ForeignKey(FloodAlert, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=[
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('app', 'App Notification'),
    ])
    recipient = models.CharField(max_length=100)
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    ], default='pending')
    
    def __str__(self):
        return f"{self.notification_type} to {self.recipient} at {self.sent_at}"
    
    class Meta:
        ordering = ['-sent_at']

class EmergencyContact(models.Model):
    """Model for emergency contacts"""
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    barangay = models.ForeignKey(Barangay, on_delete=models.CASCADE, related_name='emergency_contacts', null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.role})"


class UserProfile(models.Model):
    """Extended profile for users in the system"""
    USER_ROLES = [
        ('admin', 'Administrator'),
        ('manager', 'Flood Manager'),
        ('officer', 'Municipal Officer'),
        ('operator', 'System Operator'),
        ('viewer', 'Data Viewer'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=USER_ROLES, default='viewer')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    municipality = models.ForeignKey(Municipality, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='assigned_users')
    barangay = models.ForeignKey(Barangay, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='assigned_users')
    receive_alerts = models.BooleanField(default=True)
    receive_sms = models.BooleanField(default=False)
    receive_email = models.BooleanField(default=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"
    
    def has_role(self, role):
        """Check if user has a specific role"""
        return self.role == role
    
    def is_admin(self):
        """Check if user is an admin"""
        return self.role == 'admin'
        
    def is_manager(self):
        """Check if user is a flood manager"""
        return self.role == 'manager' or self.role == 'admin'
        
    def is_officer(self):
        """Check if user is a municipal officer"""
        return self.role == 'officer' or self.is_manager()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile instance when a User is created"""
    if created:
        UserProfile.objects.create(user=instance)
        
        # Add to default group based on role
        if not instance.is_superuser:
            default_group, _ = Group.objects.get_or_create(name='Viewers')
            instance.groups.add(default_group)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if not hasattr(instance, 'profile'):
        UserProfile.objects.create(user=instance)
    instance.profile.save()


class ResilienceScore(models.Model):
    """Model for community resilience scoring"""
    # Location associations
    municipality = models.ForeignKey(Municipality, on_delete=models.CASCADE, related_name='resilience_scores', null=True, blank=True)
    barangay = models.ForeignKey(Barangay, on_delete=models.CASCADE, related_name='resilience_scores', null=True, blank=True)
    
    # Core resilience metric scores (0-100 scale)
    infrastructure_score = models.IntegerField(help_text="Score for infrastructure preparedness (0-100)")
    social_capital_score = models.IntegerField(help_text="Score for community cohesion and social capital (0-100)")
    institutional_score = models.IntegerField(help_text="Score for institutional capacity and governance (0-100)")
    economic_score = models.IntegerField(help_text="Score for economic resources and recovery capacity (0-100)")
    environmental_score = models.IntegerField(help_text="Score for environmental protection and natural buffers (0-100)")
    
    # Weighted overall score
    overall_score = models.FloatField(help_text="Overall weighted resilience score (0-100)")
    
    # Score interpretation - textual category
    RESILIENCE_CATEGORIES = [
        ('very_low', 'Very Low Resilience'),
        ('low', 'Low Resilience'),
        ('moderate', 'Moderate Resilience'),
        ('high', 'High Resilience'),
        ('very_high', 'Very High Resilience'),
    ]
    resilience_category = models.CharField(
        max_length=20, 
        choices=RESILIENCE_CATEGORIES,
        help_text="Category interpretation of the overall score"
    )
    
    # Recommendations field
    recommendations = models.TextField(help_text="Suggestions for improving resilience", null=True, blank=True)
    
    # Assessment metadata
    assessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='resilience_assessments')
    assessment_date = models.DateField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True, help_text="Date when reassessment is recommended")
    methodology = models.CharField(max_length=100, default="Standard Assessment", help_text="Assessment methodology used")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Boolean to track if this is the most recent assessment
    is_current = models.BooleanField(default=True, help_text="Whether this is the most current assessment")
    
    class Meta:
        ordering = ['-assessment_date']
        verbose_name = "Community Resilience Score"
        verbose_name_plural = "Community Resilience Scores"
    
    def __str__(self):
        location = self.barangay if self.barangay else self.municipality
        return f"{location} Resilience: {self.overall_score:.1f} ({self.get_resilience_category_display()})"
    
    def save(self, *args, **kwargs):
        # Calculate overall score if not provided
        if not self.overall_score:
            # Default weights for different components
            weights = {
                'infrastructure': 0.25,
                'social': 0.2,
                'institutional': 0.2,
                'economic': 0.2,
                'environmental': 0.15
            }
            
            self.overall_score = (
                self.infrastructure_score * weights['infrastructure'] +
                self.social_capital_score * weights['social'] +
                self.institutional_score * weights['institutional'] +
                self.economic_score * weights['economic'] +
                self.environmental_score * weights['environmental']
            )
        
        # Determine resilience category based on overall score
        if self.overall_score < 20:
            self.resilience_category = 'very_low'
        elif self.overall_score < 40:
            self.resilience_category = 'low'
        elif self.overall_score < 60:
            self.resilience_category = 'moderate'
        elif self.overall_score < 80:
            self.resilience_category = 'high'
        else:
            self.resilience_category = 'very_high'
        
        # If this is marked as current, update other assessments for same location
        if self.is_current:
            if self.barangay:
                ResilienceScore.objects.filter(
                    barangay=self.barangay, 
                    is_current=True
                ).exclude(pk=self.pk).update(is_current=False)
            elif self.municipality:
                ResilienceScore.objects.filter(
                    municipality=self.municipality, 
                    barangay__isnull=True,
                    is_current=True
                ).exclude(pk=self.pk).update(is_current=False)
        
        super().save(*args, **kwargs)

# In your models.py where SensorData is defined
class SensorData(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE)
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    accuracy_rating = models.FloatField(null=True, blank=True)  # Add this field
    
    class Meta:
        ordering = ['-timestamp']