from django.contrib import admin
from .models import AllowedEndpoint, AllowedEndpointGroup, UserPermission, FrontEndPage, AllowedFrontEndPage


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


@admin.register(FrontEndPage)
class FrontEndPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'created_at', 'updated_at')
    search_fields = ('title', 'url')
    list_filter = ('created_at', 'updated_at')
    ordering = ('title',)


@admin.register(AllowedFrontEndPage)
class AllowedFrontEndPageAdmin(admin.ModelAdmin):
    list_display = ('user', 'frontendpage', 'created_at')
    list_filter = ('frontendpage', 'created_at')
    search_fields = ('user__email', 'user__name', 'frontendpage__title', 'frontendpage__url')
    raw_id_fields = ('user',)
    autocomplete_fields = ('frontendpage',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'frontendpage')


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'direct_endpoints_count', 'effective_endpoints_count', 'frontend_pages_count')
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
    
    def frontend_pages_count(self, obj):
        return obj.user.allowed_frontend_pages.count()
    frontend_pages_count.short_description = 'Frontend Pages'
    
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
