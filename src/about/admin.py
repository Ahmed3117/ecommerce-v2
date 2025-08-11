from django.contrib import admin
from about.models import About, AboutDescription, Count, Caption, FAQ, SupportDescription

# Register your models here.
@admin.register(About)
class AboutAdmin(admin.ModelAdmin):
    list_display = ('title', 'email', 'created_at')
    search_fields = ('title', 'description', 'email')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {
            'fields': ('title', 'subtitle', 'description', 'image')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone1', 'phone2', 'whatsapp_number')
        }),
        ('Social Media', {
            'fields': ('facebook_link', 'telegram_link', 'instagram_link',
                      'youtube_link', 'tiktok_link')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )

@admin.register(AboutDescription)
class AboutDescriptionAdmin(admin.ModelAdmin):
    list_display = ('about', 'title', 'order', 'is_active')
    list_filter = ('is_active', 'about')
    search_fields = ('title', 'description')
    list_editable = ('order', 'is_active')
    fieldsets = (
        (None, {
            'fields': ('about', 'title', 'description')
        }),
        ('Settings', {
            'fields': ('order', 'is_active')
        }),
    )


@admin.register(SupportDescription)
class SupportDescriptionAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    list_editable = ('is_active',)
    date_hierarchy = 'created_at'

@admin.register(Count)
class CountAdmin(admin.ModelAdmin):
    list_display = ('subscribers_count', 'doctors_count', 'students_count')
    fieldsets = (
        (None, {
            'fields': ('subscribers_count', 'doctors_count', 'students_count')
        }),
    )

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {
            'fields': ('title', 'description')
        }),
        ('Media', {
            'fields': ('file', 'video_url')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        }),
    )

@admin.register(Caption)
class CaptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'caption', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('caption',)
    readonly_fields = ('created_at',)
    list_editable = ('is_active',)
    list_per_page = 20
