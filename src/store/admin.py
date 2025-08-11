from django.contrib import admin
from django.utils.html import format_html
from .models import StoreRequest, Store, StoreReporting
from accounts.models import User

@admin.register(StoreRequest)
class StoreRequestAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'first_name', 'last_name', 'phone1', 'email', 'status', 'date_added')
    list_filter = ('status', 'government', 'date_added')
    search_fields = ('first_name', 'last_name', 'store_name', 'phone1', 'email', 'address')
    readonly_fields = ('date_added', 'date_updated', 'get_national_id_preview', 'get_image_preview')
    actions = ['accept_request', 'refuse_request']
    fieldsets = (
        ('Request Info', {'fields': ('status', 'refuse_reason')}),
        ('User Info', {'fields': ('user', 'first_name', 'last_name', 'email')}),
        ('Store Info', {'fields': ('store_name', 'address', 'government')}),
        ('Contact Info', {'fields': ('phone1', 'phone2', 'whatsapp_number')}),
        ('Social Links', {'fields': ('facebook_link', 'telegram_link', 'instagram_link', 'youtube_link', 'tiktok_link')}),
        ('Images', {'fields': ('image', 'get_image_preview', 'national_id_image', 'get_national_id_preview')}),
        ('Timestamps', {'fields': ('date_added', 'date_updated')}),
    )

    @admin.display(description='Store Image')
    def get_image_preview(self, obj):
        if obj.image:
            return format_html('<a href="{0}" target="_blank"><img src="{0}" width="100"/></a>', obj.image.url)
        return "No Image"

    @admin.display(description='National ID')
    def get_national_id_preview(self, obj):
        if obj.national_id_image:
            return format_html('<a href="{0}" target="_blank"><img src="{0}" width="100"/></a>', obj.national_id_image.url)
        return "No Image"

    @admin.action(description='Accept selected requests and create stores')
    def accept_request(self, request, queryset):
        for req in queryset.filter(status='pending'):
            user, created = User.objects.get_or_create(
                username=req.phone1,
                defaults={
                    'name': f"{req.first_name} {req.last_name}",
                    'email': req.email,
                    'phone': req.phone1,
                    'user_type': 'store',
                }
            )
            
            Store.objects.update_or_create(
                user=user,
                defaults={
                    'store_name': req.store_name,
                    'image': req.image,
                    'national_id_image': req.national_id_image,
                    'government': req.government,
                    'address': req.address,
                    'phone1': req.phone1,
                    'phone2': req.phone2,
                    'email': req.email,
                    'whatsapp_number': req.whatsapp_number,
                    'facebook_link': req.facebook_link,
                    'telegram_link': req.telegram_link,
                    'instagram_link': req.instagram_link,
                    'youtube_link': req.youtube_link,
                    'tiktok_link': req.tiktok_link,
                }
            )
            req.user = user
            req.status = 'accepted'
            req.save()
        self.message_user(request, "Selected requests have been accepted and stores created/updated.")

    @admin.action(description='Refuse selected requests')
    def refuse_request(self, request, queryset):
        queryset.update(status='refused')
        self.message_user(request, "Selected requests have been refused.")


class StoreReportingInline(admin.TabularInline):
    model = StoreReporting
    extra = 0
    fields = ('user', 'text', 'date', 'is_handled')
    readonly_fields = ('user', 'text', 'date')
    autocomplete_fields = ('user',)

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'user', 'government', 'phone1', 'email')
    search_fields = ('store_name', 'user__username', 'phone1', 'email', 'address')
    list_filter = ('government',)
    autocomplete_fields = ('user',)
    inlines = [StoreReportingInline]
    readonly_fields = ('get_national_id_preview', 'get_image_preview')
    fieldsets = (
        ('Owner Info', {'fields': ('user',)}),
        ('Store Info', {'fields': ('store_name', 'address', 'government')}),
        ('Contact Info', {'fields': ('phone1', 'phone2', 'email', 'whatsapp_number')}),
        ('Social Links', {'fields': ('facebook_link', 'telegram_link', 'instagram_link', 'youtube_link', 'tiktok_link')}),
        ('Images', {'fields': ('image', 'get_image_preview', 'national_id_image', 'get_national_id_preview')}),
    )

    @admin.display(description='Store Image')
    def get_image_preview(self, obj):
        if obj.image:
            return format_html('<a href="{0}" target="_blank"><img src="{0}" width="100"/></a>', obj.image.url)
        return "No Image"

    @admin.display(description='National ID')
    def get_national_id_preview(self, obj):
        if obj.national_id_image:
            return format_html('<a href="{0}" target="_blank"><img src="{0}" width="100"/></a>', obj.national_id_image.url)
        return "No Image"


@admin.register(StoreReporting)
class StoreReportingAdmin(admin.ModelAdmin):
    list_display = ('store', 'user', 'date', 'is_handled')
    list_filter = ('is_handled', 'date')
    search_fields = ('store__name', 'user__username', 'text')
    autocomplete_fields = ('store', 'user')
    list_editable = ('is_handled',)
    actions = ['mark_as_handled']

    @admin.action(description='Mark selected reports as handled')
    def mark_as_handled(self, request, queryset):
        queryset.update(is_handled=True)