from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin
from django import forms
from .models import (
    Sensor, SensorData, Municipality, Barangay, FloodRiskZone, 
    FloodAlert, ThresholdSetting, NotificationLog, EmergencyContact, UserProfile,
    ResilienceScore
)

class SensorAdminForm(forms.ModelForm):
    class Meta:
        model = Sensor
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make lat/lon optional in admin UI; they'll be auto-filled from barangay
        if 'latitude' in self.fields:
            self.fields['latitude'].required = False
            self.fields['latitude'].widget = forms.HiddenInput()
        if 'longitude' in self.fields:
            self.fields['longitude'].required = False
            self.fields['longitude'].widget = forms.HiddenInput()
        if 'barangay' in self.fields:
            self.fields['barangay'].required = False
            self.fields['barangay'].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        barangay = cleaned.get('barangay')
        lat = cleaned.get('latitude')
        lon = cleaned.get('longitude')
        muni = cleaned.get('municipality')

        # Auto-fill from selected barangay when missing
        if barangay and (lat is None or lon is None):
            b_lat = getattr(barangay, 'latitude', None)
            b_lon = getattr(barangay, 'longitude', None)
            if b_lat is not None and b_lon is not None:
                cleaned['latitude'] = b_lat
                cleaned['longitude'] = b_lon
                lat, lon = b_lat, b_lon
            else:
                self.add_error('barangay', 'Selected barangay has no coordinates defined.')

        # Align municipality to barangay's municipality if mismatched
        if barangay and barangay.municipality and (not muni or barangay.municipality_id != getattr(muni, 'id', None)):
            cleaned['municipality'] = barangay.municipality
            muni = cleaned['municipality']

        # Fallback: if no barangay provided, use municipality coordinates
        if not barangay and muni and (cleaned.get('latitude') is None or cleaned.get('longitude') is None):
            m_lat = getattr(muni, 'latitude', None)
            m_lon = getattr(muni, 'longitude', None)
            if m_lat is not None and m_lon is not None:
                cleaned['latitude'] = m_lat
                cleaned['longitude'] = m_lon

        # Ensure final presence with clearer guidance
        if cleaned.get('latitude') is None:
            self.add_error('municipality', 'Coordinates missing. Provide a barangay (via URL ?barangay_id=...) or set municipality coordinates.')
            self.add_error('latitude', 'Latitude is required and will be auto-filled from the barangay or municipality.')
        if cleaned.get('longitude') is None:
            self.add_error('municipality', 'Coordinates missing. Provide a barangay (via URL ?barangay_id=...) or set municipality coordinates.')
            self.add_error('longitude', 'Longitude is required and will be auto-filled from the barangay or municipality.')
        return cleaned

@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    form = SensorAdminForm
    list_display = ('name', 'sensor_type', 'active', 'last_updated')
    list_filter = ('sensor_type', 'active')
    search_fields = ('name',)

    def save_model(self, request, obj, form, change):
        # Final guard to ensure coordinates exist
        if (obj.latitude is None or obj.longitude is None):
            if getattr(obj, 'barangay', None) and obj.barangay.latitude is not None and obj.barangay.longitude is not None:
                obj.latitude = obj.barangay.latitude
                obj.longitude = obj.barangay.longitude
                if not obj.municipality_id and obj.barangay.municipality_id:
                    obj.municipality_id = obj.barangay.municipality_id
            elif getattr(obj, 'municipality', None) and obj.municipality.latitude is not None and obj.municipality.longitude is not None:
                obj.latitude = obj.municipality.latitude
                obj.longitude = obj.municipality.longitude
        super().save_model(request, obj, form, change)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        brgy_id = request.GET.get('barangay') or request.GET.get('barangay_id')
        if brgy_id:
            try:
                b = Barangay.objects.get(pk=brgy_id)
                initial['barangay'] = b.id
                initial['municipality'] = b.municipality_id
                initial['latitude'] = b.latitude
                initial['longitude'] = b.longitude
            except Barangay.DoesNotExist:
                pass
        return initial

@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'value', 'timestamp')
    list_filter = ('sensor__sensor_type', 'timestamp')
    date_hierarchy = 'timestamp'

@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'province', 'population', 'contact_person', 'contact_number')
    list_filter = ('province', 'is_active')
    search_fields = ('name', 'province', 'contact_person')

@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ('name', 'municipality', 'population', 'contact_person', 'contact_number')
    list_filter = ('municipality',)
    search_fields = ('name', 'contact_person')

@admin.register(FloodRiskZone)
class FloodRiskZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'severity_level')
    list_filter = ('severity_level',)
    search_fields = ('name',)

@admin.register(FloodAlert)
class FloodAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'severity_level', 'active', 'issued_at', 'predicted_flood_time')
    list_filter = ('severity_level', 'active', 'issued_at')
    search_fields = ('title', 'description')
    filter_horizontal = ('affected_barangays',)
    date_hierarchy = 'issued_at'

@admin.register(ThresholdSetting)
class ThresholdSettingAdmin(admin.ModelAdmin):
    list_display = ('parameter', 'advisory_threshold', 'warning_threshold', 'emergency_threshold', 'updated_at')
    list_filter = ('parameter',)

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('alert', 'notification_type', 'recipient', 'status', 'sent_at')
    list_filter = ('notification_type', 'status', 'sent_at')
    search_fields = ('recipient',)
    date_hierarchy = 'sent_at'

@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'phone', 'email', 'barangay')
    list_filter = ('role', 'barangay')
    search_fields = ('name', 'role', 'phone', 'email')
    
# Define an inline admin descriptor for UserProfile model
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fk_name = 'user'

# Define a new User admin
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline, )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_role')
    list_select_related = ('profile', )
    
    def get_role(self, instance):
        if hasattr(instance, 'profile'):
            return instance.profile.get_role_display()
        return '-'
    get_role.short_description = 'Role'
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        return super().get_inline_instances(request, obj)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'municipality', 'barangay', 'phone_number', 'receive_alerts')
    list_filter = ('role', 'municipality', 'barangay', 'receive_alerts', 'receive_sms', 'receive_email')
    search_fields = ('user__username', 'user__email', 'phone_number')
    raw_id_fields = ('user',)

# Resilience Score admin
@admin.register(ResilienceScore)
class ResilienceScoreAdmin(admin.ModelAdmin):
    list_display = ('get_location_name', 'overall_score', 'resilience_category', 'assessment_date', 'is_current')
    list_filter = ('resilience_category', 'is_current', 'assessment_date', 'municipality', 'barangay')
    search_fields = ('municipality__name', 'barangay__name', 'recommendations')
    readonly_fields = ('overall_score', 'resilience_category')
    fieldsets = (
        ('Location', {
            'fields': ('municipality', 'barangay')
        }),
        ('Assessment Scores', {
            'fields': (
                'infrastructure_score', 'social_capital_score', 'institutional_score',
                'economic_score', 'environmental_score', 'overall_score', 'resilience_category'
            )
        }),
        ('Recommendations & Notes', {
            'fields': ('recommendations', 'notes')
        }),
        ('Assessment Metadata', {
            'fields': ('assessed_by', 'assessment_date', 'valid_until', 'methodology', 'is_current')
        })
    )
    
    def get_location_name(self, obj):
        if obj.barangay:
            return f"{obj.barangay.name}, {obj.municipality.name}"
        elif obj.municipality:
            return f"{obj.municipality.name}"
        return "Unknown Location"
    get_location_name.short_description = "Location"

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
