from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse
from django.utils.html import escape
from django.utils.safestring import mark_safe
import csv
from products.models import PillAddress
from .models import GOVERNMENT_CHOICES, User, UserAddress, UserProfileImage


class PillAddressGovernmentFilter(admin.SimpleListFilter):
    title = 'government (from pill addresses)'
    parameter_name = 'pill_government'

    def lookups(self, request, model_admin):
        return GOVERNMENT_CHOICES

    def queryset(self, request, queryset):
        if not self.value():
            return queryset

        matching_user_ids = PillAddress.objects.filter(
            government=self.value(),
            pill__user__isnull=False,
        ).values('pill__user_id').distinct()

        return queryset.filter(pk__in=matching_user_ids)

class UserAddressInline(admin.TabularInline):
    model = UserAddress
    extra = 1
    fields = ('name', 'phone', 'government', 'city', 'address', 'is_default')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'name', 'email', 'phone', 'user_type', 'is_staff', 'get_profile_image_preview')
    list_filter = ('user_type', 'is_staff', 'is_superuser', 'is_active', 'groups', PillAddressGovernmentFilter, 'year')
    actions = ['export_users_csv']
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
            return mark_safe(
                f'<img src="{escape(obj.user_profile_image.image.url)}" width="40" height="40" '
                'style="border-radius:50%;" />'
            )
        return "No Image"

    @admin.action(description='Export selected users to CSV')
    def export_users_csv(self, request, queryset):
        cl = self.get_changelist_instance(request)
        full_queryset = cl.queryset
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'id', 'username', 'name', 'email', 'phone', 'phone2',
            'user_type', 'year', 'division', 'government', 'city', 'address',
            'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login',
        ])
        for user in full_queryset.order_by('-date_joined'):
            writer.writerow([
                user.id,
                user.username,
                user.name,
                user.email,
                user.phone,
                user.phone2,
                user.user_type,
                user.year,
                user.division,
                user.government,
                user.city,
                user.address,
                user.is_active,
                user.is_staff,
                user.is_superuser,
                user.date_joined,
                user.last_login,
            ])
        return response

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
            return mark_safe(f'<img src="{escape(obj.image.url)}" width="100" />')
        return "No Image"
