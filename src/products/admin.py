from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    Category, SubCategory, Brand, Product, ProductImage, ProductDescription,
    Color, ProductAvailability, Shipping, PillItem, Pill, PillAddress,
    PillStatusLog, CouponDiscount, Rating, Discount, PayRequest, LovedProduct,
    StockAlert, PriceDropAlert, SpecialProduct, SpinWheelDiscount,
    SpinWheelResult, SpinWheelSettings, PillGift, KhazenlyWebhookLog
)


import json

class GovernmentListFilter(admin.SimpleListFilter):
    title = 'Government'
    parameter_name = 'government'

    def lookups(self, request, model_admin):
        from .models import GOVERNMENT_CHOICES
        
        # Add custom option for null/blank governments
        choices = [
            ('null', 'No Government (Empty)'),
        ]
        
        # Add all government choices
        choices.extend(GOVERNMENT_CHOICES)
        
        return choices

    def queryset(self, request, queryset):
        if self.value() == 'null':
            return queryset.filter(government__isnull=True) | queryset.filter(government='')
        elif self.value():
            return queryset.filter(government=self.value())
        return queryset

class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_image_preview')
    search_fields = ('name',)
    inlines = [SubCategoryInline]

    @admin.display(description='Image')
    def get_image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return "No Image"

# FIX: Added a dedicated admin for SubCategory with search_fields
@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    search_fields = ('name', 'category__name')
    autocomplete_fields = ('category',)
    list_filter = ('category',)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_logo_preview')
    search_fields = ('name',)

    @admin.display(description='Logo')
    def get_logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="50" height="50" />', obj.logo.url)
        return "No Logo"

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductDescriptionInline(admin.TabularInline):
    model = ProductDescription
    extra = 1

class ProductAvailabilityInline(admin.TabularInline):
    model = ProductAvailability
    extra = 1
    autocomplete_fields = ['color']

class DiscountInline(admin.TabularInline):
    model = Discount
    extra = 0
    fields = ('discount', 'discount_start', 'discount_end', 'is_active')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name','product_number' ,'type','get_base_image_preview', 'category', 'price', 'get_total_quantity', 'average_rating', 'is_important', 'date_added')
    list_filter = ('category', 'brand', 'is_important', 'date_added')
    search_fields = ('name', 'description')
    autocomplete_fields = ('category', 'sub_category', 'brand')
    readonly_fields = ('average_rating', 'number_of_ratings', 'get_total_quantity')
    inlines = [ProductImageInline, ProductDescriptionInline, ProductAvailabilityInline, DiscountInline]
    list_select_related = ('category', 'brand')
    list_editable = ('type',)

    @admin.display(description='Image')
    def get_base_image_preview(self, obj):
        if obj.base_image:
            return format_html('<img src="{}" width="50" height="50" />', obj.base_image.url)
        return "No Image"
    
    @admin.display(description='Total Quantity', ordering='total_quantity')
    def get_total_quantity(self, obj):
        return obj.total_quantity()


@admin.register(ProductAvailability)
class ProductAvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        'product', 
        'size', 
        'color', 
        'quantity', 
        'native_price', 
        'date_added'
    )
    list_filter = (
        'product__category', 
        'color', 
        'size', 
        'date_added'
    )
    search_fields = (
        'product__name', 
        'color__name', 
        'size'
    )
    readonly_fields = ('date_added',)
    ordering = ('-date_added',)
    date_hierarchy = 'date_added'

    autocomplete_fields = ['product', 'color']
    list_select_related = ['product', 'color']

    def get_queryset(self, request):
        # Optimize queryset by selecting related objects
        qs = super().get_queryset(request)
        return qs.select_related('product', 'color')

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('name', 'degree')
    search_fields = ('name', 'degree')

class PillAddressInline(admin.StackedInline):
    model = PillAddress
    can_delete = False

class PillStatusLogInline(admin.TabularInline):
    model = PillStatusLog
    extra = 0
    readonly_fields = ('status', 'changed_at')
    can_delete = False

# class PillItemInline(admin.TabularInline):
#     model = PillItem
#     extra = 0
#     autocomplete_fields = ('product', 'color')
#     readonly_fields = ('price_at_sale', 'native_price_at_sale', 'date_sold')
    
class FinalPriceListFilter(admin.SimpleListFilter):
    title = 'Max Final Price'
    parameter_name = 'max_final_price'

    def lookups(self, request, model_admin):
        # Provide choices for max price: 100, 200, ..., 1000
        return [(str(price), f'≤ {price}') for price in range(100, 1100, 100)]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            try:
                max_price = float(value)
                # Filter pills with final_price <= max_price
                return queryset.filter(id__in=[
                    pill.id for pill in queryset if pill.final_price() is not None and pill.final_price() <= max_price
                ])
            except Exception:
                return queryset
        return queryset

@admin.register(Pill)
class PillAdmin(admin.ModelAdmin):
    list_display = [
        'pill_number', 'user', 'paid', 'status', 'is_shipped',
        'khazenly_status', 'khazenly_actions', 'final_price_display'
    ]
    list_filter = ['status', 'paid', 'is_shipped', FinalPriceListFilter]
    search_fields = ['pill_number', 'user__username']
    readonly_fields = ['pill_number']
    list_editable = ['paid', 'status']
    actions = ['send_to_khazenly_bulk']

    def final_price_display(self, obj):
        return obj.final_price()
    final_price_display.short_description = 'Final Price'
    final_price_display.admin_order_field = None

    def khazenly_status(self, obj):
        if obj.has_khazenly_order:
            return format_html('<span style="color: green;">✓ Created</span>')
        elif obj.is_shipped:
            return format_html('<span style="color: orange;">⚠ Pending</span>')
        else:
            return format_html('<span style="color: gray;">-</span>')
    khazenly_status.short_description = 'Khazenly'

    @admin.display(description='Khazenly Actions')
    def khazenly_actions(self, obj):
        """Add manual Khazenly action button for each row"""
        if obj.has_khazenly_order:
            # Already has Khazenly order - show success status with order number
            return format_html(
                '<span style="color: green; padding: 3px 8px; font-weight: bold; background: #d4edda; border-radius: 3px;">✓ Sent ({0})</span>',
                obj.khazenly_sales_order_number or 'Created'
            )
        elif obj.paid:
            # Paid but no Khazenly order - show clickable send button
            return format_html(
                '<a href="/admin/products/pill/{}/send_to_khazenly/" '
                'class="button" '
                'style="background: #28a745; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; display: inline-block; border: none; cursor: pointer;" '
                'onclick="return confirm(\'Are you sure you want to send Pill {} to Khazenly?\');">'
                '🚀 Send to Khazenly</a>',
                obj.id,
                obj.pill_number
            )
        else:
            # Not paid - show why it can't be sent
            return format_html(
                '<span style="color: #6c757d; padding: 3px 8px; font-style: italic; background: #f8f9fa; border-radius: 3px;">💸 Not Paid</span>'
            )

    khazenly_actions.short_description = 'Khazenly Actions'
    khazenly_actions.admin_order_field = None
    khazenly_actions.allow_tags = True

    @admin.action(description='Send selected pills to Khazenly (paid pills only)')
    def send_to_khazenly_bulk(self, request, queryset):
        """Bulk action to send multiple pills to Khazenly"""
        success_count = 0
        error_messages = []

        # Filter only paid pills that don't have Khazenly orders
        eligible_pills = queryset.filter(paid=True)

        for pill in eligible_pills:
            try:
                pill._create_khazenly_order()
                # Refresh to check if it was successful
                pill.refresh_from_db()
                if pill.has_khazenly_order:
                    success_count += 1
                else:
                    error_messages.append(f"Pill {pill.pill_number}: Order not created (no exception)")
            except Exception as e:
                error_messages.append(f"Pill {pill.pill_number}: {str(e)}")

        if success_count > 0:
            self.message_user(
                request,
                f'Successfully sent {success_count} pills to Khazenly.',
                level='SUCCESS'
            )
        if error_messages:
            error_summary = "; ".join(error_messages[:3])  # Show first 3 errors
            if len(error_messages) > 3:
                error_summary += f" ... and {len(error_messages) - 3} more errors"
            self.message_user(
                request,
                f'Failed to send {len(error_messages)} pills to Khazenly: {error_summary}',
                level='ERROR'
            )

    def get_urls(self):
        """Add custom URL for individual Khazenly send action"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pill_id>/send_to_khazenly/',
                self.admin_site.admin_view(self.send_to_khazenly_view),
                name='pill_send_to_khazenly',
            ),
        ]
        return custom_urls + urls

    def send_to_khazenly_view(self, request, pill_id):
        """Handle manual send to Khazenly for individual pill"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages

        pill = get_object_or_404(Pill, id=pill_id)

        # Check if pill is eligible
        if not pill.paid:
            messages.error(request, f'❌ Pill {pill.pill_number} is not paid yet.')
            return redirect('admin:products_pill_changelist')

        if pill.has_khazenly_order:
            messages.warning(request, f'⚠️ Pill {pill.pill_number} already has a Khazenly order: {pill.khazenly_sales_order_number}')
            return redirect('admin:products_pill_changelist')

        try:
            # Manually trigger Khazenly order creation
            pill._create_khazenly_order()

            # Refresh pill from database to get updated data
            pill.refresh_from_db()

            if pill.has_khazenly_order:
                messages.success(
                    request,
                    f'✅ Successfully sent Pill {pill.pill_number} to Khazenly! '
                    f'Sales Order Number: {pill.khazenly_sales_order_number}'
                )
            else:
                messages.error(
                    request,
                    f'❌ Failed to send Pill {pill.pill_number} to Khazenly. No exception was raised but order was not created.'
                )

        except Exception as e:
            # Show the actual error message instead of generic message
            messages.error(
                request,
                f'❌ Error sending Pill {pill.pill_number} to Khazenly: {str(e)}'
            )

        return redirect('admin:products_pill_changelist')
    

@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'discount', 'discount_start', 'discount_end', 'is_active', 'is_currently_active')
    list_filter = ('is_active', 'category')
    search_fields = ('product__name', 'category__name')
    autocomplete_fields = ('product', 'category')

@admin.register(CouponDiscount)
class CouponDiscountAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'discount_value', 'available_use_times', 'is_wheel_coupon', 'coupon_start', 'coupon_end')
    search_fields = ('coupon', 'user__username')
    readonly_fields = ('coupon',)
    autocomplete_fields = ['user']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'star_number', 'date_added')
    list_filter = ('star_number', 'date_added')
    search_fields = ('product__name', 'user__username', 'review')
    autocomplete_fields = ['product', 'user']

@admin.register(Shipping)
class ShippingAdmin(admin.ModelAdmin):
    list_display = ('get_government_display', 'shipping_price')
    list_editable = ('shipping_price',)

@admin.register(PayRequest)
class PayRequestAdmin(admin.ModelAdmin):
    list_display = ('pill', 'date', 'is_applied', 'get_image_preview')
    list_filter = ('is_applied', 'date')
    search_fields = ('pill__pill_number',)
    autocomplete_fields = ['pill']
    actions = ['mark_as_applied']

    @admin.display(description='Image')
    def get_image_preview(self, obj):
        if obj.image:
            return format_html('<a href="{0}" target="_blank"><img src="{0}" width="100"/></a>', obj.image.url)
        return "No Image"

    @admin.action(description='Mark selected requests as applied')
    def mark_as_applied(self, request, queryset):
        queryset.update(is_applied=True)

@admin.register(SpecialProduct)
class SpecialProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'order', 'is_active', 'created_at', 'get_image_preview')
    list_filter = ('is_active',)
    search_fields = ('product__name',)
    autocomplete_fields = ['product']
    list_editable = ('order', 'is_active')

    @admin.display(description='Special Image')
    def get_image_preview(self, obj):
        if obj.special_image:
            return format_html('<img src="{}" width="50" height="50" />', obj.special_image.url)
        return "No Image"

@admin.register(PillGift)
class PillGiftAdmin(admin.ModelAdmin):
    list_display = ('discount_value', 'min_order_value', 'max_order_value', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('discount_value',)

@admin.register(SpinWheelDiscount)
class SpinWheelDiscountAdmin(admin.ModelAdmin):
    list_display = ('name', 'discount_value', 'probability', 'is_active', 'start_date', 'end_date', 'max_winners')
    list_filter = ('is_active',)

@admin.register(LovedProduct)
class LovedProductAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    autocomplete_fields = ('user', 'product')
    search_fields = ('user__username', 'product__name')

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'product', 'is_notified', 'created_at')
    list_filter = ('is_notified',)
    autocomplete_fields = ('user', 'product')
    search_fields = ('user__username', 'email', 'product__name')

@admin.register(PillAddress)
class PillAddressAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone','government', 'pill_number', 'email', 'city','address', 'pill__paid')
    list_filter = (GovernmentListFilter, 'pay_method', 'city', 'pill__status','pill__paid')
    search_fields = ('name', 'phone', 'pill__pill_number', 'email')
    autocomplete_fields = ('pill',)
    list_editable = ('government',)
    readonly_fields = ('pill_number',)
    
    
    @admin.display(description='Pill Number', ordering='pill__pill_number')
    def pill_number(self, obj):
        return obj.pill.pill_number if obj.pill else '-'
    
    def get_queryset(self, request):
        # Optimize queryset by selecting related objects
        qs = super().get_queryset(request)
        return qs.select_related('pill')


@admin.register(KhazenlyWebhookLog)
class KhazenlyWebhookLogAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp', 'method', 'response_status', 'pill_number', 
        'webhook_status', 'order_reference', 'remote_addr', 
        'duration_display', 'is_successful', 'hmac_verified'
    )
    list_filter = (
        'method', 'response_status', 'webhook_status', 'hmac_verified', 
        'pill_found', 'status_updated', 'timestamp'
    )
    search_fields = (
        'pill_number', 'order_reference', 'merchant_reference', 
        'remote_addr', 'user_agent', 'error_message'
    )
    readonly_fields = (
        'timestamp', 'method', 'url_path', 'query_params', 'remote_addr',
        'user_agent', 'referer', 'x_forwarded_for', 'x_real_ip', 'headers',
        'body', 'content_type', 'content_length', 'response_status',
        'response_body', 'response_headers', 'processing_time_ms',
        'pill_found', 'pill_number', 'status_updated', 'error_message',
        'hmac_verified', 'webhook_status', 'order_reference',
        'merchant_reference', 'order_supplier_id', 'duration_display',
        'is_successful'
    )
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    list_per_page = 50
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('timestamp', 'method', 'url_path', 'response_status', 'duration_display', 'is_successful')
        }),
        ('Request Source', {
            'fields': ('remote_addr', 'user_agent', 'referer', 'x_forwarded_for', 'x_real_ip'),
            'classes': ('collapse',)
        }),
        ('Request Content', {
            'fields': ('headers', 'body', 'content_type', 'content_length'),
            'classes': ('collapse',)
        }),
        ('Response', {
            'fields': ('response_body', 'response_headers'),
            'classes': ('collapse',)
        }),
        ('Webhook Data', {
            'fields': ('webhook_status', 'order_reference', 'merchant_reference', 'order_supplier_id')
        }),
        ('Processing Results', {
            'fields': ('pill_found', 'pill_number', 'status_updated', 'hmac_verified', 'error_message')
        }),
    )
    
    def has_add_permission(self, request):
        # Prevent manual creation of webhook logs
        return False
    
    def has_change_permission(self, request, obj=None):
        # Make logs read-only
        return False
    
    @admin.display(description='Success', boolean=True)
    def is_successful(self, obj):
        return obj.is_successful
    
    @admin.display(description='Duration')
    def duration_display(self, obj):
        return obj.duration_display


admin.site.register(ProductImage)
admin.site.register(ProductDescription)
admin.site.register(PillItem)
# admin.site.register(PillAddress)
admin.site.register(PillStatusLog)
admin.site.register(PriceDropAlert)
admin.site.register(SpinWheelResult)
admin.site.register(SpinWheelSettings)