from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import path
from django.utils.html import format_html
import json
import csv
from .models import AllowedEndpoint, AllowedEndpointGroup, UserPermission, FrontEndPage, FrontEndPagePermission


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
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export/', self.admin_site.admin_view(self.export_pages), name='permissions_frontendpage_export'),
            path('import/', self.admin_site.admin_view(self.import_pages), name='permissions_frontendpage_import'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['export_url'] = 'export/'
        extra_context['import_url'] = 'import/'
        return super().changelist_view(request, extra_context)
    
    def export_pages(self, request):
        """Export all FrontEndPage records to JSON"""
        pages = FrontEndPage.objects.all().values('title', 'url')
        data = list(pages)
        
        response = HttpResponse(
            json.dumps(data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="frontend_pages_export.json"'
        return response
    
    def import_pages(self, request):
        """Import FrontEndPage records from JSON file"""
        if request.method == 'POST':
            if 'file' not in request.FILES:
                messages.error(request, 'Please select a file to import.')
                return redirect('..')
            
            file = request.FILES['file']
            
            if not file.name.endswith('.json'):
                messages.error(request, 'Please upload a JSON file.')
                return redirect('..')
            
            try:
                data = json.loads(file.read().decode('utf-8'))
                
                if not isinstance(data, list):
                    messages.error(request, 'Invalid file format. Expected a JSON array.')
                    return redirect('..')
                
                created_count = 0
                updated_count = 0
                error_count = 0
                
                for item in data:
                    try:
                        if 'title' not in item or 'url' not in item:
                            error_count += 1
                            continue
                        
                        page, created = FrontEndPage.objects.get_or_create(
                            url=item['url'],
                            defaults={'title': item['title']}
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            # Update title if it's different
                            if page.title != item['title']:
                                page.title = item['title']
                                page.save()
                                updated_count += 1
                    
                    except Exception as e:
                        error_count += 1
                        continue
                
                success_msg = f'Import completed: {created_count} created, {updated_count} updated'
                if error_count > 0:
                    success_msg += f', {error_count} errors'
                
                messages.success(request, success_msg)
                return redirect('..')
                
            except json.JSONDecodeError:
                messages.error(request, 'Invalid JSON file format.')
                return redirect('..')
            except Exception as e:
                messages.error(request, f'Error importing file: {str(e)}')
                return redirect('..')
        
        # GET request - show import form
        return render(request, 'admin/permissions/frontendpage/import.html')
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
        js = ('admin/js/custom_admin.js',)


# AllowedFrontEndPageAdmin removed - using FrontEndPagePermissionAdmin instead


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
        try:
            return obj.user.frontend_page_permission.pages.count()
        except:
            return 0
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


@admin.register(FrontEndPagePermission)
class FrontEndPagePermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'page_count', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__name', 'pages__title', 'pages__url')
    filter_horizontal = ('pages',)  # This gives you the filter_horizontal widget!
    raw_id_fields = ('user',)
    
    def page_count(self, obj):
        return obj.pages.count()
    page_count.short_description = "Number of Pages"
    
    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
        ('Page Permissions', {
            'fields': ('pages',),
            'description': 'Select all frontend pages this user should have access to.'
        }),
    )
