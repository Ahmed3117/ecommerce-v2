from django.contrib import admin
from .models import AllowedEndpoint, AllowedEndpointGroup, UserPermission


@admin.register(AllowedEndpoint)
class AllowedEndpointAdmin(admin.ModelAdmin):
    list_display = ('url', 'method')
    list_filter = ('method',)
    search_fields = ('url',)
    ordering = ('url', 'method')


@admin.register(AllowedEndpointGroup)
class AllowedEndpointGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'endpoint_count')
    search_fields = ('name', 'description')
    filter_horizontal = ('allowed_endpoints',)
    
    def endpoint_count(self, obj):
        return obj.allowed_endpoints.count()
    endpoint_count.short_description = 'Number of Endpoints'


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'direct_endpoints_count', 'effective_endpoints_count')
    list_filter = ('group',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    filter_horizontal = ('allowed_endpoints',)
    raw_id_fields = ('user',)
    
    def direct_endpoints_count(self, obj):
        return obj.allowed_endpoints.count()
    direct_endpoints_count.short_description = 'Direct Endpoints'
    
    def effective_endpoints_count(self, obj):
        return obj.get_allowed_endpoints().count()
    effective_endpoints_count.short_description = 'Effective Endpoints'
    
    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
        ('Group Permissions', {
            'fields': ('group',),
            'description': 'If a group is selected, it takes precedence over direct endpoint permissions.'
        }),
        ('Direct Endpoint Permissions', {
            'fields': ('allowed_endpoints',),
            'description': 'These permissions are used only if no group is assigned.'
        }),
    )
