# views.py
from rest_framework.viewsets import ViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Count, Avg, F, Q, FloatField, Case, When, BooleanField, Subquery, OuterRef, IntegerField, ExpressionWrapper
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear,TruncDate
from accounts.models import GOVERNMENT_CHOICES, User
from accounts.pagination import CustomPageNumberPagination
from analysis.serializers import CategoryAnalyticsSerializer, InventoryAlertSerializer, ProductAnalyticsSerializer, SalesTrendSerializer
from products.models import PILL_STATUS_CHOICES, Category, Discount, LovedProduct, Pill, PillAddress, PillItem, Product, ProductAvailability, Rating, SpecialProduct
from rest_framework import generics, filters
from rest_framework.response import Response
from django_filters import rest_framework as django_filters
from datetime import datetime


from django.db.models import Count, Sum, Q, F, Case, When, Value, IntegerField, Avg
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
from django.utils import timezone
from django.db.models import OuterRef, Subquery

from store.models import Store, StoreRequest



class ProductAnalyticsFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(method='filter_by_sale_date')
    end_date = django_filters.DateFilter(method='filter_by_sale_date')
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = django_filters.NumberFilter(field_name='category__id')
    is_low_stock = django_filters.BooleanFilter(method='filter_is_low_stock')
    class Meta:
        model = Product
        fields = ['category', 'brand', 'min_price', 'max_price', 'is_low_stock']

    def filter_by_sale_date(self, queryset, name, value):
        # This logic is now handled correctly within the subqueries in the view
        return queryset
    
    def filter_is_low_stock(self, queryset, name, value):
        """
        Filters the queryset based on the annotated 'is_low_stock' field.
        The annotation (total_available <= threshold) is performed in the view.
        """
        # The `is_low_stock` annotation is already added in the view's get_queryset.
        # This method will now correctly filter on that pre-calculated value.
        if value in (True, 'true', 'True', 1):
            return queryset.filter(is_low_stock=True)
        if value in (False, 'false', 'False', 0):
            return queryset.filter(is_low_stock=False)
        return queryset

class ProductPerformanceView(generics.ListAPIView):
    serializer_class = ProductAnalyticsSerializer
    filter_backends = [django_filters.DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = ProductAnalyticsFilter
    ordering_fields = ['total_sold', 'revenue', 'average_rating', 'total_available', 'price', 'name']
    search_fields = ['name']
    #pagination_class = CustomPageNumberPagination  # Add pagination for large datasets
    
    def get_queryset(self):
        # Parse date parameters once
        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')
        low_stock_threshold = self.request.query_params.get('low_stock_threshold')
        
        parsed_start = parse_date(start_date_str) if start_date_str else None
        parsed_end = parse_date(end_date_str) if end_date_str else None
        
        # Build date filter once for reuse
        has_date_filter = parsed_start and parsed_end
        end_of_day_exclusive = parsed_end + timedelta(days=1) if parsed_end else None
        
        # --- 1. Subquery for total available stock ---
        avail_sq = ProductAvailability.objects.filter(
            product=OuterRef('pk')
        ).values('product').annotate(total=Sum('quantity')).values('total')[:1]
        
        # --- 2. Subquery for stock added (only if date filter specified) ---
        if has_date_filter:
            added_sq = ProductAvailability.objects.filter(
                product=OuterRef('pk'),
                date_added__gte=parsed_start,
                date_added__lt=end_of_day_exclusive
            ).values('product').annotate(total=Sum('quantity')).values('total')[:1]
        else:
            added_sq = ProductAvailability.objects.filter(
                product=OuterRef('pk')
            ).values('product').annotate(total=Sum('quantity')).values('total')[:1]

        # --- 3. Sales subqueries with combined filter ---
        sales_base_filter = {'product': OuterRef('pk'), 'status__in': ['p', 'd']}
        if has_date_filter:
            sales_base_qs = PillItem.objects.filter(
                product=OuterRef('pk'),
                status__in=['p', 'd'],
                date_sold__gte=parsed_start,
                date_sold__lt=end_of_day_exclusive
            )
        else:
            sales_base_qs = PillItem.objects.filter(
                product=OuterRef('pk'),
                status__in=['p', 'd']
            )
        
        total_sold_sq = sales_base_qs.values('product').annotate(
            total=Sum('quantity')
        ).values('total')[:1]
        
        revenue_sq = sales_base_qs.values('product').annotate(
            total=Sum(F('quantity') * F('price_at_sale'))
        ).values('total')[:1]
        
        # --- 4. Single combined rating subquery ---
        avg_rating_sq = Rating.objects.filter(
            product=OuterRef('pk')
        ).values('product').annotate(avg=Avg('star_number')).values('avg')[:1]
        
        total_ratings_sq = Rating.objects.filter(
            product=OuterRef('pk')
        ).values('product').annotate(count=Count('id')).values('count')[:1]

        # --- 5. Current discount subquery (optimized with limit) ---
        now = timezone.now()
        current_discount_sq = Discount.objects.filter(
            Q(product=OuterRef('pk')) | Q(category=OuterRef('category')),
            discount_start__lte=now,
            discount_end__gte=now,
            is_active=True
        ).order_by('-discount').values('discount')[:1]

        # --- Main Query with all annotations in a single pass ---
        queryset = Product.objects.select_related('category', 'brand').only(
            'id', 'name', 'price', 'threshold', 'date_added',
            'category__id', 'category__name', 'brand__id', 'brand__name'
        ).annotate(
            total_available=Coalesce(Subquery(avail_sq), 0, output_field=IntegerField()),
            total_added=Coalesce(Subquery(added_sq), 0, output_field=IntegerField()),
            total_sold=Coalesce(Subquery(total_sold_sq), 0, output_field=IntegerField()),
            revenue=Coalesce(Subquery(revenue_sq), 0.0, output_field=FloatField()),
            average_rating=Coalesce(Subquery(avg_rating_sq), 0.0, output_field=FloatField()),
            total_ratings=Coalesce(Subquery(total_ratings_sq), 0, output_field=IntegerField()),
            current_discount=Coalesce(Subquery(current_discount_sq), 0.0, output_field=FloatField()),
        ).annotate(
            price_after_discount=Case(
                When(current_discount__gt=0, then=F('price') * (1 - F('current_discount') / 100.0)),
                default=F('price'),
                output_field=FloatField()
            ),
            has_discount=Case(
                When(current_discount__gt=0, then=True),
                default=False,
                output_field=BooleanField()
            ),
            is_low_stock=Case(
                When(total_available__lte=F('threshold'), then=True),
                default=False,
                output_field=BooleanField()
            )
        )

        # Apply low stock threshold filter if requested
        if low_stock_threshold is not None:
            try:
                threshold_val = int(low_stock_threshold)
                queryset = queryset.filter(total_available__lte=threshold_val)
            except (ValueError, TypeError):
                pass
        
        return queryset

class ProductBuyerFilter(django_filters.FilterSet):
    purchase_type = django_filters.CharFilter(method='filter_purchase_type')
    
    class Meta:
        model = User
        fields = ['year']

    def filter_purchase_type(self, queryset, name, value):
        # Access the view instance from the parent filterset
        view = getattr(self, 'view', None) or getattr(self.request, 'parser_context', {}).get('view')
        product_id = view.kwargs.get('pk') if view else None
        if not product_id:
            return queryset
            
        value = str(value).strip()
        
        # Get user IDs who have paid purchases for this product
        paid_user_ids = set(User.objects.filter(
            pill_items__product_id=product_id,
            pill_items__pill__isnull=False
        ).values_list('id', flat=True).distinct())
        
        # Get user IDs who have manual assignments for this product
        manual_user_ids = set(User.objects.filter(
            pill_items__product_id=product_id,
            pill_items__pill__isnull=True
        ).values_list('id', flat=True).distinct())
        
        # 'paid' / 'شراء' -> ONLY paid (not manual)
        if value in ['paid', 'شراء']:
            only_paid_ids = paid_user_ids - manual_user_ids
            return queryset.filter(id__in=only_paid_ids)
        
        # 'manual' / 'اضافة يدوية' -> ONLY manual (not paid)
        elif value in ['manual', 'اضافة يدوية']:
            only_manual_ids = manual_user_ids - paid_user_ids
            return queryset.filter(id__in=only_manual_ids)
        
        # 'both' / 'كلاهما' -> Has BOTH
        elif value in ['both', 'كلاهما']:
            both_ids = paid_user_ids & manual_user_ids
            return queryset.filter(id__in=both_ids)
        
        return queryset

class ProductBuyersView(generics.ListAPIView):
    """
    Get all users who bought a specific product.
    Supports filtering by year and searching by name/username.
    """
    from analysis.serializers import ProductBuyerSerializer
    serializer_class = ProductBuyerSerializer
    # pagination_class = CustomPageNumberPagination
    filter_backends = [filters.SearchFilter, django_filters.DjangoFilterBackend]
    search_fields = ['name', 'username']
    filterset_class = ProductBuyerFilter

    def get_queryset(self):
        product_id = self.kwargs.get('pk')
        # distinct() is crucial here because one user might have bought the product multiple times
        return User.objects.filter(pill_items__product_id=product_id).distinct()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['product_id'] = self.kwargs.get('pk')
        return context


class CategoryPerformanceView(generics.ListAPIView):
    serializer_class = CategoryAnalyticsSerializer

    def get_queryset(self):
        # Subquery for total available quantity
        avail_sq = Subquery(
            Product.objects.filter(
                category=OuterRef('pk')
            ).values('category').annotate(
                total=Sum('availabilities__quantity')
            ).values('total')
        )

        # Base subquery for sold items
        sold_items = PillItem.objects.filter(
            product__category=OuterRef('pk'),
            status__in=['p', 'd']
        )
        
        # Subquery for total sales quantity
        sales_sq = Subquery(
            sold_items.values('product__category').annotate(
                total=Sum('quantity')
            ).values('total')
        )

        # Subquery for total revenue
        revenue_sq = Subquery(
            sold_items.values('product__category').annotate(
                total=Sum(F('quantity') * F('price_at_sale'))
            ).values('total')
        )

        return Category.objects.annotate(
            total_products=Count('products', distinct=True),
            total_available_quantity=Coalesce(avail_sq, 0, output_field=IntegerField()),
            total_sales=Coalesce(sales_sq, 0, output_field=IntegerField()),
            revenue=Coalesce(revenue_sq, 0.0, output_field=FloatField())
        ).order_by('-revenue')

######################### New Consolidated Views #########################


class SalesDashboardView(APIView):
    """
    Consolidated sales dashboard endpoint with multiple metrics
    """
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Base query for sold items (paid or delivered)
        sold_items = PillItem.objects.filter(
            Q(status='p') | Q(status='d'),
            date_sold__range=[start_date, end_date]
        )
        
        # 1. Sales Trends (Daily)
        daily_sales = sold_items.annotate(
            day=TruncDay('date_sold')
        ).values('day').annotate(
            total_sales=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('price_at_sale')),
            total_cost=Sum(F('quantity') * F('native_price_at_sale'))
        ).order_by('day')
        
        # 2. Product Performance
        product_sales = sold_items.values(
            'product__id', 'product__name'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('price_at_sale')),
            total_cost=Sum(F('quantity') * F('native_price_at_sale')),
            avg_price=Avg('price_at_sale')
        ).order_by('-total_revenue')
        
        # 3. Inventory Metrics
        inventory_cost = ProductAvailability.objects.filter(
            date_added__range=[start_date, end_date]
        ).aggregate(
            total_cost=Sum(F('quantity') * F('native_price'))
        )['total_cost'] or 0
        
        # 4. Financial Summary
        sales_revenue = sold_items.aggregate(
            total_revenue=Sum(F('quantity') * F('price_at_sale'))
        )['total_revenue'] or 0
        
        cogs = sold_items.aggregate(
            total_cost=Sum(F('quantity') * F('native_price_at_sale'))
        )['total_cost'] or 0
        
        profit = sales_revenue - cogs
        margin = (profit / sales_revenue * 100) if sales_revenue else 0
        
        return Response({
            'time_period': {'start_date': start_date, 'end_date': end_date},
            'daily_sales': list(daily_sales),
            'product_performance': list(product_sales),
            'financial_summary': {
                'sales_revenue': sales_revenue,
                'cost_of_goods_sold': cogs,
                'gross_profit': profit,
                'gross_margin': margin,
                'inventory_cost': inventory_cost
            }
        })

class ProductInventoryView(APIView):
    """
    Consolidated product inventory analysis
    """
    def get(self, request):
        # 1. Low stock products
        total_quantity = ProductAvailability.objects.filter(
            product=OuterRef('pk')
        ).values('product').annotate(
            total=Sum('quantity')
        ).values('total')
        
        low_stock = Product.objects.annotate(
            current_quantity=Subquery(total_quantity)
        ).filter(
            current_quantity__lte=F('threshold')
        ).values('id', 'name', 'threshold', 'current_quantity')
        
        # 2. Special products count
        special_count = SpecialProduct.objects.filter(is_active=True).count()
        important_count = Product.objects.filter(is_important=True).count()
        
        # 4. Most loved products
        loved_products = LovedProduct.objects.values(
            'product__id', 'product__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'low_stock_products': list(low_stock),
            'special_products': {
                'important_count': important_count,
                'special_count': special_count
            },
            'most_loved_products': list(loved_products)
        })

class OrderAnalysisView(APIView):
    """
    Consolidated order and pill analysis
    """
    permission_classes = [IsAdminUser] # Recommended to protect this endpoint

    def get(self, request):
        # 1. Pill status counts
        pill_status = Pill.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        status_counts = {status[0]: 0 for status in PILL_STATUS_CHOICES}
        for item in pill_status:
            status_counts[item['status']] = item['count']
        
        # 2. Pill items status counts
        item_status = PillItem.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        item_status_counts = {status[0]: 0 for status in PILL_STATUS_CHOICES}
        for item in item_status:
            item_status_counts[item['status']] = item['count']
        
        # 3. Best sellers
        best_sellers = PillItem.objects.filter(
            Q(status='p') | Q(status='d')
        ).values(
            'product__id', 'product__name'
        ).annotate(
            total_sold=Sum('quantity'),
            # Use Coalesce to handle cases where Sum might return None
            total_revenue=Coalesce(Sum(F('quantity') * F('price_at_sale')), 0, output_field=FloatField()),
            total_native_price=Coalesce(Sum(F('quantity') * F('native_price_at_sale')), 0, output_field=FloatField())
        ).annotate(
            # Calculate the profit, named as requested
            total_native_revenue=F('total_revenue') - F('total_native_price')
        ).order_by('-total_sold')[:10]
        
        return Response({
            'pill_status_counts': status_counts,
            'pill_item_status_counts': item_status_counts,
            'best_selling_products': list(best_sellers)
        })



class CustomerActivityView(APIView):
    """
    Customer and government activity analysis
    """
    def get(self, request):
        # 1. User type breakdown
        user_types = User.objects.values('user_type').annotate(
            count=Count('id')
        )
        
        # 2. Active vs inactive users
        active_users = User.objects.filter(
            pills__isnull=False
        ).distinct().count()
        total_users = User.objects.count()
        
        # 3. Government activity
        gov_activity = Pill.objects.filter(
            pilladdress__isnull=False
        ).values(
            'pilladdress__government'
        ).annotate(
            pill_count=Count('id'),
            user_count=Count('user', distinct=True)
        ).order_by('-pill_count')
        
        gov_map = {code: name for code, name in GOVERNMENT_CHOICES}
        formatted_gov = []
        for item in gov_activity:
            gov_code = item['pilladdress__government']
            formatted_gov.append({
                'government_code': gov_code,
                'government_name': gov_map.get(gov_code, 'Unknown'),
                'pill_count': item['pill_count'],
                'user_count': item['user_count']
            })
        
        return Response({
            'user_types': list(user_types),
            'user_activity': {
                'active_users': active_users,
                'inactive_users': total_users - active_users,
                'total_users': total_users
            },
            'government_activity': formatted_gov
        })


class StoreAnalyticsView(APIView):
    """
    Store-related analytics
    """
    def get(self, request):
        # 1. Store requests
        store_requests = StoreRequest.objects.values('status').annotate(
            count=Count('id')
        )
        
        request_counts = {status: 0 for status, _ in StoreRequest.STATUS_CHOICES}
        for item in store_requests:
            request_counts[item['status']] = item['count']
        
        # 2. Stores by government
        stores_by_gov = Store.objects.values('government').annotate(
            count=Count('id')
        )
        
        # Create mapping from code to name and vice versa
        gov_code_to_name = {code: name for code, name in GOVERNMENT_CHOICES}
        gov_name_to_code = {name: code for code, name in GOVERNMENT_CHOICES}
        
        formatted_gov = []
        for item in stores_by_gov:
            gov_code = item['government']
            gov_name = gov_code_to_name.get(gov_code, 'Unknown')
            
            formatted_gov.append({
                'government_code': gov_code,  # Keep the original code (e.g., '1')
                'government_name': gov_name,  # Full name (e.g., 'Cairo')
                'store_count': item['count']
            })
        
        # Sort by government name alphabetically
        formatted_gov.sort(key=lambda x: x['government_name'])
        
        return Response({
            'store_requests': request_counts,
            'stores_by_government': formatted_gov,
            'total_stores': Store.objects.count()
        })


###################### specific endpoint to get alot of analysis data #########################
from rest_framework.pagination import PageNumberPagination


import logging

logger = logging.getLogger(__name__)


class AnalyticsPagination(PageNumberPagination):
    """Custom pagination for analytics data"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class DashboardAnalyticsView(APIView):
    """
    Unified comprehensive dashboard endpoint consolidating key metrics across 
    sales, inventory, customers, and stores.
    
    Features:
    - Complete date filtering support with proper validation
    - Pagination for large datasets
    - Robust error handling
    - Optimized database queries
    - Comprehensive metrics coverage
    
    Query Parameters:
    - start_date (YYYY-MM-DD): Start of analysis period. Defaults to 30 days ago.
    - end_date (YYYY-MM-DD): End of analysis period. Defaults to today.
    - page: Page number for paginated results
    - page_size: Number of items per page (max 100)
    """
    
    pagination_class = AnalyticsPagination

    def get(self, request, *args, **kwargs):
        try:
            # --- 1. Enhanced Date Handling with Validation ---
            start_date, end_date, end_date_for_query = self._get_date_range(request)
            if isinstance(start_date, Response):  # Error response from validation
                return start_date

            # --- 2. Core Querysets ---
            # Base queryset for sold items with date filtering
            sold_items = PillItem.objects.filter(
                status__in=['p', 'd'],
                date_sold__gte=start_date,
                date_sold__lt=end_date_for_query
            ).select_related('product', 'product__category')

            # Base queryset for orders with date filtering
            orders = Pill.objects.filter(
                status__in=['p', 'd'],
                date_added__gte=start_date,
                date_added__lt=end_date_for_query
            )

            # --- 3. Core KPI Calculations ---
            financial_summary = self._calculate_financial_metrics(sold_items)
            basic_counts = self._get_basic_counts(orders)

            # --- 4. Time Series Analysis ---
            time_series_data = self._get_time_series_data(sold_items)

            # --- 5. Performance Metrics with Pagination ---
            performance_metrics = self._get_performance_metrics(sold_items, request)

            # --- 6. Inventory Analysis ---
            inventory_metrics = self._get_enhanced_inventory_metrics(start_date, end_date)

            # --- 7. Order & Customer Analytics ---
            order_metrics = self._get_comprehensive_order_metrics()
            customer_metrics = self._get_enhanced_customer_metrics()

            # --- 8. Store Analytics ---
            store_metrics = self._get_enhanced_store_metrics()

            # --- 9. Assemble Unified Response ---
            response_data = {
                # Core KPIs
                **basic_counts,
                **financial_summary,
                
                # Time Series
                **time_series_data,
                
                # Performance Analytics
                **performance_metrics,
                
                # Detailed Metrics
                "inventory_metrics": inventory_metrics,
                **order_metrics,
                **customer_metrics,
                "store_metrics": store_metrics,
                
                # Metadata
                "date_range": {
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d')
                },
                "generated_at": timezone.now().isoformat()
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Dashboard analytics error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred while generating analytics: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_date_range(self, request):
        """Enhanced date range handling with validation"""
        try:
            today = timezone.now().date()
            
            # Parse dates with better error handling
            end_date_str = request.query_params.get('end_date')
            start_date_str = request.query_params.get('start_date')
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = today
                
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                start_date = today - timedelta(days=30)
            
            # Validation
            if start_date > end_date:
                return Response(
                    {"error": "start_date cannot be after end_date"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if end_date > today:
                return Response(
                    {"error": "end_date cannot be in the future"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            end_date_for_query = end_date + timedelta(days=1)
            return start_date, end_date, end_date_for_query
            
        except ValueError as e:
            return Response(
                {"error": f"Invalid date format. Use YYYY-MM-DD. Details: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _calculate_financial_metrics(self, sold_items):
        """Calculate comprehensive financial metrics"""
        financial_data = sold_items.aggregate(
            total_sales_quantity=Coalesce(Sum('quantity'), 0, output_field=IntegerField()),
            gross_revenue=Coalesce(Sum(F('quantity') * F('price_at_sale')), 0.0, output_field=FloatField()),
            cogs=Coalesce(Sum(F('quantity') * F('native_price_at_sale')), 0.0, output_field=FloatField())
        )
        
        profit = financial_data['gross_revenue'] - financial_data['cogs']
        
        return {
            "total_sales": financial_data['total_sales_quantity'],
            "total_cost": round(financial_data['gross_revenue'], 2),
            "native_cost": round(financial_data['cogs'], 2),
            "total_revenue": round(profit, 2),
            "total_orders_value": round(profit, 2),  # Alias for compatibility
            "profit_margin": round((profit / financial_data['gross_revenue'] * 100) if financial_data['gross_revenue'] > 0 else 0, 2)
        }

    def _get_basic_counts(self, orders):
        """Get basic entity counts"""
        return {
            "total_users": User.objects.count(),
            "total_products": Product.objects.count(),
            "total_categories": Category.objects.count(),
            "total_orders": orders.count(),
            "total_pills": Pill.objects.count(),
            "total_pill_items": PillItem.objects.count()
        }

    def _get_time_series_data(self, sold_items):
        """Generate time series data for sales trends"""
        def _get_sales_trend(trunc_func):
            return sold_items.annotate(period=trunc_func('date_sold')) \
                .values('period') \
                .annotate(
                    total_sales=Sum('quantity'),
                    total_cost=Sum(F('quantity') * F('price_at_sale')),
                    native_cost=Sum(F('quantity') * F('native_price_at_sale'))
                ).annotate(
                    total_revenue=F('total_cost') - F('native_cost')
                ).order_by('period')

        return {
            "daily_sales": list(_get_sales_trend(TruncDay)),
            "monthly_sales": list(_get_sales_trend(TruncMonth)),
            "yearly_sales": list(_get_sales_trend(TruncYear))
        }

    def _get_performance_metrics(self, sold_items, request):
        """Get performance metrics - top 10 for all performance lists"""
        # Current stock subquery
        current_stock_sq = ProductAvailability.objects.filter(
            product=OuterRef('product__id')
        ).values('product').annotate(
            total=Sum('quantity')
        ).values('total')
        
        # Product Performance - Top 10 only (no pagination)
        product_performance = sold_items.values('product__id', 'product__name') \
            .annotate(
                total_sales=Sum('quantity'),
                revenue=Sum(F('quantity') * F('price_at_sale')),
                native_cost=Sum(F('quantity') * F('native_price_at_sale')),
                profit=Sum(F('quantity') * F('price_at_sale')) - Sum(F('quantity') * F('native_price_at_sale')),
                total_available=Coalesce(Subquery(current_stock_sq), 0)
            ).order_by('-revenue')[:10]

        # Category Performance (Enhanced)
        category_performance = Category.objects.annotate(
            total_products=Count('products', distinct=True),
            total_sales=Coalesce(
                Sum(
                    'products__pill_items__quantity',
                    filter=Q(products__pill_items__status__in=['p', 'd'])
                ), 0, output_field=IntegerField()
            ),
            revenue=Coalesce(
                Sum(
                    F('products__pill_items__quantity') * F('products__pill_items__price_at_sale'),
                    filter=Q(products__pill_items__status__in=['p', 'd'])
                ) - Sum(
                    F('products__pill_items__quantity') * F('products__pill_items__native_price_at_sale'),
                    filter=Q(products__pill_items__status__in=['p', 'd'])
                ), 0.0, output_field=FloatField()
            )
        ).values('id', 'name', 'total_products', 'total_sales', 'revenue').order_by('-revenue')

        # Best Selling Products (All time) - Top 10 only
        best_selling_products = PillItem.objects.filter(status__in=['p', 'd']) \
            .values('product__id', 'product__name') \
            .annotate(
                total_sold=Sum('quantity'),
                total_revenue=Sum(F('quantity') * F('price_at_sale')) - Sum(F('quantity') * F('native_price_at_sale'))
            ).order_by('-total_sold')[:10]

        return {
            "product_performance": list(product_performance),
            "category_performance": list(category_performance),
            "best_selling_products": list(best_selling_products)
        }

    def _get_enhanced_inventory_metrics(self, start_date, end_date):
        """Enhanced inventory metrics with date filtering"""
        # Current stock subquery
        current_stock_sq = ProductAvailability.objects.filter(
            product=OuterRef('pk')
        ).values('product').annotate(total=Sum('quantity')).values('total')

        # Low stock products
        low_stock = Product.objects.select_related('category').annotate(
            current_quantity=Coalesce(Subquery(current_stock_sq), 0)
        ).filter(
            current_quantity__lte=F('threshold')
        ).values('id', 'name', 'threshold', 'current_quantity', 'category__name')

        # Inventory cost calculation
        inventory_cost_filter = Q()
        if start_date and end_date:
            inventory_cost_filter = Q(date_added__range=(start_date, end_date))
        
        inventory_cost = ProductAvailability.objects.filter(inventory_cost_filter).aggregate(
            total_cost=Coalesce(Sum(F('quantity') * F('native_price')), 0.0, output_field=FloatField())
        )['total_cost']

        # Most loved products
        most_loved = LovedProduct.objects.select_related('product', 'product__category') \
            .values('product__id', 'product__name', 'product__category__name') \
            .annotate(count=Count('id')).order_by('-count')[:10]

        return {
            "low_stock_products": list(low_stock),
            "inventory_cost": round(inventory_cost, 2),
            "special_products": {
                "important_count": Product.objects.filter(is_important=True).count(),
                "special_count": SpecialProduct.objects.filter(is_active=True).count()
            },
            "most_loved_products": list(most_loved),
            "inventory_summary": {
                "total_products_in_stock": ProductAvailability.objects.filter(quantity__gt=0).count(),
                "out_of_stock_products": Product.objects.annotate(
                    current_quantity=Coalesce(Subquery(current_stock_sq), 0)
                ).filter(current_quantity=0).count()
            }
        }

    def _get_comprehensive_order_metrics(self):
        """Comprehensive order metrics including status counts"""
        # Pill status counts
        pill_status_qs = Pill.objects.values('status').annotate(count=Count('id'))
        pill_status_counts = {code: 0 for code, name in PILL_STATUS_CHOICES}
        for item in pill_status_qs:
            if item['status'] in pill_status_counts:
                pill_status_counts[item['status']] = item['count']

        # Pill item status counts (including null)
        item_status_qs = PillItem.objects.values('status').annotate(count=Count('id'))
        pill_item_status_counts = {code: 0 for code, name in PILL_STATUS_CHOICES}
        pill_item_status_counts['null'] = 0
        
        for item in item_status_qs:
            status_key = item['status'] if item['status'] is not None else 'null'
            if status_key in pill_item_status_counts:
                pill_item_status_counts[status_key] = item['count']

        return {
            "total_pills": Pill.objects.count(),
            "pill_status_counts": pill_status_counts,
            "pill_item_status_counts": pill_item_status_counts,
            "order_summary": {
                "completed_orders": Pill.objects.filter(status='d').count(),
                "pending_orders": Pill.objects.filter(status='p').count(),
                "average_order_value": self._calculate_average_order_value()
            }
        }

    def _calculate_average_order_value(self):
        """Calculate average order value"""
        completed_orders = Pill.objects.filter(status__in=['p', 'd'])
        if not completed_orders.exists():
            return 0
        
        total_value = PillItem.objects.filter(
            pill__in=completed_orders,
            status__in=['p', 'd']
        ).aggregate(
            total=Sum(F('quantity') * F('price_at_sale'))
        )['total'] or 0
        
        return round(total_value / completed_orders.count(), 2) if completed_orders.count() > 0 else 0

    def _get_enhanced_customer_metrics(self):
        """Enhanced customer analytics"""
        # User type distribution
        user_types = User.objects.values('user_type').annotate(count=Count('id')).order_by('-count')
        
        # Active users (with orders in last 30 days)
        active_users = User.objects.filter(
            pills__status__in=['p', 'd'],
            pills__date_added__gte=timezone.now() - timedelta(days=30)
        ).distinct().count()
        
        total_users = User.objects.count()

        # Government activity analysis
        gov_activity_qs = Pill.objects.filter(
            pilladdress__isnull=False, 
            status__in=['p', 'd']
        ).values('pilladdress__government') \
         .annotate(
             pill_count=Count('id'), 
             user_count=Count('user', distinct=True)
         ).order_by('-pill_count')

        gov_map = dict(GOVERNMENT_CHOICES)
        gov_activity = [{
            'government_code': item['pilladdress__government'],
            'government_name': gov_map.get(item['pilladdress__government'], 'Unknown'),
            'pill_count': item['pill_count'],
            'user_count': item['user_count']
        } for item in gov_activity_qs]

        return {
            "user_types": list(user_types),
            "user_activity": {
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "total_users": total_users,
                "activity_rate": round((active_users / total_users * 100) if total_users > 0 else 0, 2)
            },
            "government_activity": gov_activity
        }

    def _get_enhanced_store_metrics(self):
        """Enhanced store analytics"""
        # Store request status counts
        store_req_qs = StoreRequest.objects.values('status').annotate(count=Count('id'))
        req_counts = {code: 0 for code, name in StoreRequest.STATUS_CHOICES}
        for item in store_req_qs:
            req_counts[item['status']] = item['count']

        # Stores by government
        stores_by_gov_qs = Store.objects.values('government').annotate(count=Count('id'))
        gov_name_to_code_map = {name: code for code, name in GOVERNMENT_CHOICES}
        
        stores_by_gov = []
        for item in stores_by_gov_qs:
            gov_name = item['government']
            if gov_name:  # Skip null/empty government names
                stores_by_gov.append({
                    'government_code': gov_name_to_code_map.get(gov_name, 'N/A'),
                    'government_name': gov_name,
                    'store_count': item['count']
                })

        return {
            "store_requests": req_counts,
            "stores_by_government": sorted(stores_by_gov, key=lambda x: x.get('government_name', '')),
            "total_stores": Store.objects.count(),
            "store_summary": {
                "active_stores": Store.objects.filter(is_active=True).count() if hasattr(Store, 'is_active') else None,
                "pending_requests": req_counts.get('pending', 0),
                "approved_requests": req_counts.get('approved', 0)
            }
        }




