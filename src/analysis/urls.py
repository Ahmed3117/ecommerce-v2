from django.urls import path
from .views import CustomerActivityView, DashboardAnalyticsView, OrderAnalysisView, ProductInventoryView, ProductPerformanceView, CategoryPerformanceView, SalesDashboardView, StoreAnalyticsView, ProductBuyersView


urlpatterns = [
    path('products/', ProductPerformanceView.as_view(), name='product-analytics'),
    path('products/<int:pk>/buyers/', ProductBuyersView.as_view(), name='product-buyers'),
    path('categories/', CategoryPerformanceView.as_view(), name='category-analytics'),
    # Sales Analysis
    path('sales-dashboard/', SalesDashboardView.as_view(), name='sales-dashboard'),
    path('product-inventory/', ProductInventoryView.as_view(), name='product-inventory'),
    path('order-analysis/', OrderAnalysisView.as_view(), name='order-analysis'),
    path('customer-activity/', CustomerActivityView.as_view(), name='customer-activity'),
    path('store-analytics/', StoreAnalyticsView.as_view(), name='store-analytics'),
    # a specific endpoint for alot of data
    # path('super-dashboard/', SuperDashboardView.as_view(), name='super-dashboard'),
    path('full-dashboard/', DashboardAnalyticsView.as_view(), name='super-dashboard'),
]