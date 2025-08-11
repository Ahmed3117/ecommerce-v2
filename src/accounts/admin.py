from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserAddress, UserProfileImage

class UserAddressInline(admin.TabularInline):
    model = UserAddress
    extra = 1
    fields = ('name', 'phone', 'government', 'city', 'address', 'is_default')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'name', 'email', 'phone', 'user_type', 'is_staff', 'get_profile_image_preview')
    list_filter = ('user_type', 'is_staff', 'is_superuser', 'is_active', 'groups', 'government', 'year')
    search_fields = ('username', 'name', 'email', 'phone')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('name', 'email', 'phone', 'phone2', 'user_profile_image')}),
        ('User Type Specifics', {'fields': ('user_type', 'year')}),
        ('Location', {'fields': ('government', 'city', 'address')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('OTP', {'fields': ('otp', 'otp_created_at')}),
    )
    readonly_fields = ('last_login', 'date_joined', 'otp_created_at')
    inlines = [UserAddressInline]

    @admin.display(description='Profile Image')
    def get_profile_image_preview(self, obj):
        if obj.user_profile_image and obj.user_profile_image.image:
            return format_html('<img src="{}" width="40" height="40" style="border-radius:50%;" />', obj.user_profile_image.image.url)
        return "No Image"

@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'phone', 'government', 'city', 'is_default')
    list_filter = ('government', 'is_default')
    search_fields = ('user__username', 'name', 'phone', 'city', 'address')
    autocomplete_fields = ['user']

@admin.register(UserProfileImage)
class UserProfileImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_image_preview', 'created_at')
    readonly_fields = ('get_image_preview', 'created_at', 'updated_at')
    search_fields = ('id',)

    @admin.display(description='Image Preview')
    def get_image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.image.url)
        return "No Image"