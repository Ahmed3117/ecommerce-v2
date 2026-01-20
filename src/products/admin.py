from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from django.utils import timezone
from django.http import HttpResponse
from .models import (
    Category, SubCategory, Brand, Subject, Teacher, Product, ProductImage, ProductDescription,
    Color, ProductAvailability, Shipping, PillItem, Pill, PillAddress,
    PillStatusLog, CouponDiscount, Rating, Discount, PayRequest, LovedProduct,
    StockAlert, PriceDropAlert, SpecialProduct, SpinWheelDiscount,
    SpinWheelResult, SpinWheelSettings, CartSettings, PillGift, KhazenlyWebhookLog,
    OverTaxConfig, FreeShippingOffer
)

import json
try:
    import xlsxwriter
    EXCEL_AVAILABLE = True
except ImportError:
    try:
        import openpyxl
        EXCEL_AVAILABLE = True
    except ImportError:
        EXCEL_AVAILABLE = False
import io
from datetime import datetime

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

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'created_at')
    search_fields = ('name', 'subject__name')
    autocomplete_fields = ('subject',)
    list_filter = ('subject', 'created_at')
    readonly_fields = ('created_at',)

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
    list_display = ('name','product_number' ,'type','is_active','get_base_image_preview', 'category', 'price', 'get_total_quantity', 'average_rating', 'is_important', 'date_added')
    list_filter = ('category', 'brand', 'is_important', 'date_added', 'is_active')
    search_fields = ('name', 'description')
    autocomplete_fields = ('category', 'sub_category', 'brand')
    readonly_fields = ('average_rating', 'number_of_ratings', 'get_total_quantity')
    inlines = [ProductImageInline, ProductDescriptionInline, ProductAvailabilityInline, DiscountInline]
    list_select_related = ('category', 'brand')
    list_editable = ('type', 'is_active')

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

class StockProblemListFilter(admin.SimpleListFilter):
    title = 'Stock Problem Status'
    parameter_name = 'stock_problem'

    def lookups(self, request, model_admin):
        return [
            ('has_problem', 'Has Stock Problem'),
            ('resolved', 'Resolved'),
            ('no_problem', 'No Stock Problem'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'has_problem':
            return queryset.filter(has_stock_problem=True, is_resolved=False)
        elif self.value() == 'resolved':
            return queryset.filter(has_stock_problem=True, is_resolved=True)
        elif self.value() == 'no_problem':
            return queryset.filter(has_stock_problem=False)
        return queryset

@admin.register(Pill)
class PillAdmin(admin.ModelAdmin):
    list_display = [
        'pill_number', 'easypay_invoice_sequence', 'easypay_invoice_uid', 'user', 'paid', 'status', 'is_shipped',
        'khazenly_status', 'khazenly_actions', 'stock_problem_status', 'final_price_display', 'get_calculate_over_tax_price',
    ]
    list_filter = ['status', 'paid', 'is_shipped', 'has_stock_problem', 'is_resolved', StockProblemListFilter, FinalPriceListFilter]
    search_fields = ['pill_number', 'user__username']
    readonly_fields = ['pill_number', 'stock_problem_items']
    list_editable = ['paid', 'status', 'is_shipped']
    actions = ['send_to_khazenly_bulk', 'export_to_excel_for_khazenly', 'mark_stock_problems_resolved', 'check_stock_problems']

    def final_price_display(self, obj):
        return obj.final_price()
    def get_calculate_over_tax_price(self, obj):
        return obj.calculate_over_tax_price()
    final_price_display.short_description = 'Final Price'
    get_calculate_over_tax_price.short_description = 'Over Tax Price'
    final_price_display.admin_order_field = None
    get_calculate_over_tax_price.admin_order_field = None

    def khazenly_status(self, obj):
        if obj.has_khazenly_order:
            return format_html('<span style="color: green;">✓ Created</span>')
        elif obj.is_shipped:
            return format_html('<span style="color: orange;">⚠ Pending</span>')
        else:
            return format_html('<span style="color: gray;">-</span>')
    khazenly_status.short_description = 'Khazenly'

    def stock_problem_status(self, obj):
        """Display stock problem status with color coding"""
        if obj.has_stock_problem:
            if obj.is_resolved:
                return format_html('<span style="color: #28a745; font-weight: bold;">✓ Resolved</span>')
            else:
                problem_count = len(obj.stock_problem_items) if obj.stock_problem_items else 0
                return format_html(
                    '<span style="color: #dc3545; font-weight: bold;">⚠ Problem ({} items)</span>',
                    problem_count
                )
        else:
            return format_html('<span style="color: #6c757d;">-</span>')
    
    stock_problem_status.short_description = 'Stock Status'
    stock_problem_status.admin_order_field = 'has_stock_problem'

    @admin.action(description='Mark selected pills as stock problems resolved')
    def mark_stock_problems_resolved(self, request, queryset):
        """Mark selected pills with stock problems as resolved"""
        updated_count = 0
        
        for pill in queryset.filter(has_stock_problem=True, is_resolved=False):
            # Check current stock availability
            availability_check = pill.check_all_items_availability()
            
            if availability_check['all_available']:
                # Stock is now available, mark as resolved
                pill.is_resolved = True
                pill.has_stock_problem = False
                pill.stock_problem_items = None
                pill.save(update_fields=['is_resolved', 'has_stock_problem', 'stock_problem_items'])
                updated_count += 1
            else:
                # Still has stock problems, update the problem items
                pill.stock_problem_items = availability_check['problem_items']
                pill.save(update_fields=['stock_problem_items'])
        
        if updated_count > 0:
            self.message_user(
                request,
                f'Successfully resolved stock problems for {updated_count} pills.',
                level='SUCCESS'
            )
        else:
            self.message_user(
                request,
                'No pills were resolved. Selected pills either still have stock problems or were already resolved.',
                level='WARNING'
            )

    @admin.action(description='Check stock problems for selected pills')
    def check_stock_problems(self, request, queryset):
        """Manually check stock problems for selected pills"""
        checked_count = 0
        problems_found = 0
        
        for pill in queryset.filter(paid=True):
            pill._check_and_update_stock_problems()
            pill.refresh_from_db()
            checked_count += 1
            
            if pill.has_stock_problem and not pill.is_resolved:
                problems_found += 1
        
        self.message_user(
            request,
            f'Checked {checked_count} pills. Found {problems_found} pills with stock problems.',
            level='INFO'
        )

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

    @admin.action(description='Export selected pills to Excel for Khazenly manual import')
    def export_to_excel_for_khazenly(self, request, queryset):
        """Export selected pills to Excel with all Khazenly order data"""
        
        # Check if Excel libraries are available
        if not EXCEL_AVAILABLE:
            self.message_user(
                request,
                '❌ Excel export not available. Please install xlsxwriter or openpyxl: pip install xlsxwriter',
                level='ERROR'
            )
            return None
            
        try:
            # Create workbook and worksheet
            output = io.BytesIO()
            # Enable remove_timezone to avoid xlsxwriter TypeError with aware datetimes
            workbook = xlsxwriter.Workbook(output, {
                'in_memory': True,
                'remove_timezone': True
            })

            # Helper to make a datetime naive (Excel can't store tz info)
            from django.utils import timezone as dj_tz
            def _naive(dt):
                try:
                    from datetime import datetime as _dt
                    if isinstance(dt, _dt) and getattr(dt, 'tzinfo', None) is not None:
                        return dj_tz.localtime(dt).replace(tzinfo=None)
                except Exception:
                    pass
                return dt
            
            # Create worksheets
            orders_sheet = workbook.add_worksheet('Orders')
            items_sheet = workbook.add_worksheet('Line Items')
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'align': 'center'
            })
            
            cell_format = workbook.add_format({
                'border': 1,
                'text_wrap': True,
                'valign': 'top'
            })
            
            currency_format = workbook.add_format({
                'border': 1,
                'num_format': '#,##0.00',
                'valign': 'top'
            })
            
            date_format = workbook.add_format({
                'border': 1,
                'num_format': 'yyyy-mm-dd hh:mm:ss',
                'valign': 'top'
            })

            # Orders sheet headers
            order_headers = [
                'Order ID', 'Order Number', 'Store Name', 'Customer Name', 'Primary Tel',
                'Secondary Tel', 'Email', 'Address1', 'Address2', 'City', 'Government',
                'Country', 'Customer ID', 'Total Amount', 'Shipping Fees', 'Gift Discount',
                'Coupon Discount', 'Additional Notes', 'Created Date', 'User ID', 'User Email',
                'Payment Status', 'Khazenly Status', 'Line Items Count', 'lineItems JSON'
            ]
            
            # Write order headers
            for col, header in enumerate(order_headers):
                orders_sheet.write(0, col, header, header_format)
                if header == 'lineItems JSON':
                    orders_sheet.set_column(col, col, 60)
                else:
                    orders_sheet.set_column(col, col, 15)  # Set column width
            
            # Line items sheet headers
            item_headers = [
                'Order Number', 'Order ID', 'SKU', 'Item Name', 'Price', 'Quantity',
                'Discount Amount', 'Item ID', 'Product ID', 'Product Number',
                'Original Price', 'Color', 'Size', 'Line Total'
            ]
            
            # Write item headers
            for col, header in enumerate(item_headers):
                items_sheet.write(0, col, header, header_format)
                items_sheet.set_column(col, col, 15)  # Set column width
            
            # Import Khazenly service to get the data structure
            from services.khazenly_service import khazenly_service
            
            order_row = 1
            item_row = 1
            processed_pills = 0
            skip_stats = { 'no_address': 0, 'no_items': 0, 'exception': 0 }
            error_rows = []  # (pill_number, message)
            
            for pill in queryset:
                try:
                    # Debug: Check pill structure
                    print(f"Processing pill: {pill.pill_number}")
                    
                    # Check for address - PillAddress has OneToOne relationship
                    address = None
                    try:
                        address = pill.pilladdress
                        print(f"Found address: {address.name} - {address.address}")
                    except Exception as e:
                        print(f"No address found for pill {pill.pill_number}: {e}")
                        skip_stats['no_address'] += 1
                        error_rows.append((pill.pill_number, f"No address: {e}"))
                        continue
                    
                    if not address:
                        print(f"Address is None for pill {pill.pill_number}")
                        skip_stats['no_address'] += 1
                        error_rows.append((pill.pill_number, "Address relation empty"))
                        continue
                        
                    # Get pill items - try both relationships
                    pill_items = None
                    items_count = 0
                    
                    # Try many-to-many first
                    try:
                        pill_items = pill.items.all()
                        items_count = pill_items.count()
                        print(f"Found {items_count} items via M2M relationship")
                    except Exception as e:
                        print(f"M2M items failed: {e}")
                    
                    # If M2M didn't work or returned 0, try reverse FK
                    if not pill_items or items_count == 0:
                        try:
                            pill_items = pill.pill_items.all()
                            items_count = pill_items.count()
                            print(f"Found {items_count} items via reverse FK relationship")
                        except Exception as e:
                            print(f"Reverse FK items failed: {e}")
                    
                    # Skip pills with no items
                    if not pill_items or items_count == 0:
                        print(f"No items found for pill {pill.pill_number}")
                        skip_stats['no_items'] += 1
                        error_rows.append((pill.pill_number, "No items attached"))
                        continue
                    
                    print(f"Processing pill {pill.pill_number} with {items_count} items")
                    
                    # Generate the same data structure as in Khazenly service
                    from django.utils import timezone
                    timestamp_suffix = int(timezone.now().timestamp())
                    unique_order_id = f"{pill.pill_number}-{timestamp_suffix}"
                    
                    # Get government display + city name
                    city_name = "Cairo"
                    government_display = ''
                    if hasattr(address, 'government') and address.government:
                        from products.models import GOVERNMENT_CHOICES
                        gov_dict = dict(GOVERNMENT_CHOICES)
                        government_name = gov_dict.get(address.government, address.government)
                        government_display = government_name
                        city_part = address.city if address.city else ""
                        if city_part:
                            full_city = f"{government_name} - {city_part}"
                            if len(full_city) > 80:
                                max_city_length = 80 - len(government_name) - 3
                                if max_city_length > 0:
                                    truncated_city = city_part[:max_city_length].strip()
                                    city_name = f"{government_name} - {truncated_city}"
                                else:
                                    city_name = government_name[:80]
                            else:
                                city_name = full_city
                        else:
                            city_name = government_name
                    elif address.city:
                        city_name = address.city[:80] if len(address.city) > 80 else address.city
                    
                    # Prepare phone numbers
                    phone_numbers = []
                    if pill.user.phone:
                        phone_numbers.append(pill.user.phone)
                    if address.phone:
                        phone_numbers.append(address.phone)
                    
                    unique_phones = list(dict.fromkeys(phone_numbers))
                    primary_tel = address.phone if address.phone else (unique_phones[0] if unique_phones else "")
                    secondary_phones = [phone for phone in unique_phones if phone != primary_tel]
                    secondary_tel = " | ".join(secondary_phones) if secondary_phones else ""
                    
                    # Calculate amounts
                    line_items = []
                    total_product_price = 0
                    
                    for item in pill_items:
                        product = item.product
                        original_price = float(product.price) if product.price else 0
                        discounted_price = float(product.discounted_price())
                        item_total = discounted_price * item.quantity
                        item_discount = (original_price - discounted_price) * item.quantity
                        total_product_price += item_total
                        
                        # Build item description
                        color_text = f" - {item.color.name}" if item.color else ""
                        size_text = f" - Size: {item.size}" if item.size else ""
                        item_description = f"{product.name}{color_text}{size_text}"
                        item_description = item_description[:150]
                        
                        line_items.append({
                            'sku': product.product_number if product.product_number else f"PROD-{product.id}",
                            'item_name': item_description,
                            'price': discounted_price,
                            'quantity': item.quantity,
                            'discount_amount': item_discount,
                            'item_id': item.id,
                            'product_id': product.id,
                            'product_number': product.product_number or '',
                            'original_price': original_price,
                            'color': item.color.name if item.color else '',
                            'size': item.size or '',
                            'line_total': item_total
                        })
                    
                    shipping_fees = float(pill.shipping_price())
                    gift_discount = float(pill.calculate_gift_discount())
                    coupon_discount = float(pill.coupon_discount) if pill.coupon_discount else 0
                    total_discount = gift_discount + coupon_discount
                    total_amount = total_product_price + shipping_fees - total_discount
                    
                    # Prepare lineItems JSON snip for convenience (schema similar to Khazenly service)
                    line_items_json_data = [
                        {
                            'sku': li['sku'],
                            'itemName': li['item_name'],
                            'price': li['price'],
                            'quantity': li['quantity'],
                            'discountAmount': li['discount_amount'],
                            'itemId': li['item_id']
                        } for li in line_items
                    ]
                    line_items_json_str = json.dumps(line_items_json_data, ensure_ascii=False)

                    # Write order data (extended columns at end)
                    order_data = [
                        unique_order_id,  # Order ID
                        pill.pill_number,  # Order Number
                        'BOOKIFAY',  # Store Name
                        address.name or pill.user.name or pill.user.username,  # Customer Name
                        primary_tel,  # Primary Tel
                        secondary_tel,  # Secondary Tel
                        pill.user.email,  # Email
                        address.address or '',  # Address1
                        getattr(address, 'detailed_address', '') or '',  # Address2 (safe)
                        city_name,  # City
                        government_display,  # Government (display)
                        'Egypt',  # Country
                        f"USER-{pill.user.id}",  # Customer ID
                        total_amount,  # Total Amount
                        shipping_fees,  # Shipping Fees
                        gift_discount,  # Gift Discount
                        coupon_discount,  # Coupon Discount
                        f"Prepaid order for pill {pill.pill_number} - {len(line_items)} items",  # Additional Notes
                        getattr(pill, 'created_at', None) or getattr(pill, 'date_added', None),  # Created Date
                        pill.user.id,  # User ID
                        pill.user.email,  # User Email
                        'Paid' if pill.paid else 'Unpaid',  # Payment Status
                        'Has Order' if pill.has_khazenly_order else 'Pending',  # Khazenly Status
                        len(line_items),  # Line Items Count
                        line_items_json_str  # lineItems JSON
                    ]
                    
                    for col, value in enumerate(order_data):
                        if isinstance(value, (int, float)) and col in [13, 14, 15, 16]:  # Currency columns
                            orders_sheet.write(order_row, col, value, currency_format)
                        elif isinstance(value, datetime):
                            orders_sheet.write(order_row, col, _naive(value), date_format)
                        else:
                            orders_sheet.write(order_row, col, value, cell_format)
                    
                    # Write line items
                    for item in line_items:
                        item_data = [
                            pill.pill_number,  # Order Number
                            unique_order_id,  # Order ID
                            item['sku'],  # SKU
                            item['item_name'],  # Item Name
                            item['price'],  # Price
                            item['quantity'],  # Quantity
                            item['discount_amount'],  # Discount Amount
                            item['item_id'],  # Item ID
                            item['product_id'],  # Product ID
                            item['product_number'],  # Product Number
                            item['original_price'],  # Original Price
                            item['color'],  # Color
                            item['size'],  # Size
                            item['line_total']  # Line Total
                        ]
                        
                        for col, value in enumerate(item_data):
                            if isinstance(value, (int, float)) and col in [4, 6, 10, 13]:  # Currency columns
                                items_sheet.write(item_row, col, value, currency_format)
                            else:
                                items_sheet.write(item_row, col, value, cell_format)
                        
                        item_row += 1
                    
                    order_row += 1
                    processed_pills += 1
                    
                except Exception as e:
                    # Capture exception details but continue
                    from traceback import format_exc
                    print(f"Error exporting pill {getattr(pill,'pill_number','?')}: {e}\n{format_exc()}")
                    skip_stats['exception'] += 1
                    error_rows.append((getattr(pill,'pill_number','?'), f"Exception: {e}"))
                    continue
            
            # Add summary sheet
            summary_sheet = workbook.add_worksheet('Summary')
            summary_sheet.write(0, 0, 'Export Summary', header_format)
            summary_sheet.write(1, 0, 'Total Pills Selected:', cell_format)
            summary_sheet.write(1, 1, len(queryset), cell_format)
            summary_sheet.write(2, 0, 'Pills Processed:', cell_format)
            summary_sheet.write(2, 1, processed_pills, cell_format)
            summary_sheet.write(3, 0, 'Total Orders:', cell_format)
            summary_sheet.write(3, 1, order_row - 1, cell_format)
            summary_sheet.write(4, 0, 'Total Line Items:', cell_format)
            summary_sheet.write(4, 1, item_row - 1, cell_format)
            summary_sheet.write(5, 0, 'Skipped (No Address):', cell_format)
            summary_sheet.write(5, 1, skip_stats['no_address'], cell_format)
            summary_sheet.write(6, 0, 'Skipped (No Items):', cell_format)
            summary_sheet.write(6, 1, skip_stats['no_items'], cell_format)
            summary_sheet.write(7, 0, 'Exceptions:', cell_format)
            summary_sheet.write(7, 1, skip_stats['exception'], cell_format)
            summary_sheet.write(8, 0, 'Export Date:', cell_format)
            summary_sheet.write(8, 1, datetime.now(), date_format)
            summary_sheet.write(9, 0, 'Instructions:', header_format)
            summary_sheet.write(10, 0, '1. Send the "Orders" sheet data to Khazenly for order creation', cell_format)
            summary_sheet.write(11, 0, '2. The "Line Items" sheet contains detailed product information', cell_format)
            summary_sheet.write(12, 0, '3. All amounts are in EGP', cell_format)
            if error_rows:
                error_sheet = workbook.add_worksheet('Errors')
                error_sheet.write(0,0,'Pill Number', header_format)
                error_sheet.write(0,1,'Reason', header_format)
                erow = 1
                for pn, msg in error_rows:
                    error_sheet.write(erow,0,pn,cell_format)
                    error_sheet.write(erow,1,msg,cell_format)
                    erow += 1
            
            workbook.close()
            
            zero_processed = processed_pills == 0
            
            # Create HTTP response
            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
            # Set filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'khazenly_orders_export_{timestamp}.xlsx'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Add message (success or warning) but still return file
            if zero_processed:
                self.message_user(
                    request,
                    f'⚠️ Export file generated but no pills qualified (Selected: {len(queryset)}). Check that each pill has an address + items.',
                    level='WARNING'
                )
            else:
                self.message_user(
                    request,
                    f'✅ Exported {processed_pills} pills with {item_row - 1} items to Excel file: {filename}',
                    level='SUCCESS'
                )
            
            return response
            
        except Exception as e:
            self.message_user(
                request,
                f'❌ Error exporting to Excel: {str(e)}',
                level='ERROR'
            )
            return None
    

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
@admin.register(PillItem)
class PillItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'user', 'quantity', 'status', 'price_at_sale', 'date_added', 'date_sold', 'get_pill_number']
    list_filter = ['status', 'date_added', 'date_sold', 'size', 'color']
    search_fields = ['product__name', 'user__username', 'user__email', 'pill__pill_number']
    autocomplete_fields = ['product', 'user', 'pill']
    readonly_fields = ['date_added', 'date_sold']
    date_hierarchy = 'date_added'

    @admin.display(description='Pill Number', ordering='pill__pill_number')
    def get_pill_number(self, obj):
        return obj.pill.pill_number if obj.pill else '-'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'user', 'pill', 'color')
# admin.site.register(PillAddress)
admin.site.register(PillStatusLog)
admin.site.register(PriceDropAlert)
admin.site.register(SpinWheelResult)
admin.site.register(SpinWheelSettings)
admin.site.register(CartSettings)


@admin.register(OverTaxConfig)
class OverTaxConfigAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'max_products_without_tax', 'tax_amount_per_item', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['max_products_without_tax', 'tax_amount_per_item']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Tax Configuration', {
            'fields': ('max_products_without_tax', 'tax_amount_per_item', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-created_at')
    
    def save_model(self, request, obj, form, change):
        # Ensure only one active configuration
        if obj.is_active:
            OverTaxConfig.objects.filter(is_active=True).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(FreeShippingOffer)
class FreeShippingOfferAdmin(admin.ModelAdmin):
    list_display = [
        'description', 'target_type', 'get_target_name', 'start_date', 'end_date', 
        'is_active', 'is_currently_active', 'created_at'
    ]
    list_filter = ['target_type', 'is_active', 'start_date', 'end_date', 'created_at']
    search_fields = ['description', 'category__name', 'subcategory__name', 'brand__name', 'subject__name', 'teacher__name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['category', 'subcategory', 'brand', 'subject', 'teacher']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('description', 'target_type', 'is_active')
        }),
        ('Target Selection', {
            'fields': ('category', 'subcategory', 'brand', 'subject', 'teacher'),
            'description': 'Select the target based on the target type chosen above.'
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Currently Active', boolean=True)
    def is_currently_active(self, obj):
        return obj.is_currently_active
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'category', 'subcategory', 'brand', 'subject', 'teacher'
        )






