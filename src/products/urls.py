from django.urls import path

from products import payment_views
from products.khazenly_webhooks import khazenly_order_status_webhook
from products.shakeout_webhooks import shakeout_webhook  # Add Shake-out webhook import
from products.easypay_webhooks import easypay_webhook  # Add EasyPay webhook import
from . import views

app_name = 'products'

urlpatterns = [
    # Customer Endpoints
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('subcategories/', views.SubCategoryListView.as_view(), name='subcategory-list'),
    path('brands/', views.BrandListView.as_view(), name='brand-list'),
    path('subjects/', views.SubjectListView.as_view(), name='subject-list'),
    path('teachers/', views.TeacherListView.as_view(), name='teacher-list'),
    path('teachers/<int:id>/', views.TeacherDetailView.as_view(), name='teacher-detail'),
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/<int:id>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('last-products/', views.Last10ProductsListView.as_view(), name='last-products'),
    path('special-products/active/', views.ActiveSpecialProductsView.as_view(), name='special-products'),
    path('best-products/active/', views.ActiveBestProductsView.as_view(), name='best-products'),
    path('combined-products/', views.CombinedProductsView.as_view(), name='combined-products'),
    path('special-best-products/', views.SpecialBestProductsView.as_view(), name='special-best-products'),
    path('teacher-profile/<int:teacher_id>/', views.TeacherProductsView.as_view(), name='teacher-products'),
    path('cart/', views.UserCartView.as_view(), name='user-cart'),
    path('cart/add/', views.PillItemCreateView.as_view(), name='cart-add'),
    path('cart/update/<int:pk>/', views.PillItemUpdateView.as_view(), name='cart-update'),
    path('cart/delete/<int:pk>/', views.PillItemDeleteView.as_view(), name='cart-delete'),
    path('pills/init/', views.PillCreateView.as_view(), name='pill-create'),
    path('pills/<int:id>/apply-coupon/', views.PillCouponApplyView.as_view(), name='pill-coupon-apply'),
    path('pills/<int:pill_id>/address-info/', views.PillAddressCreateUpdateView.as_view(), name='pill-address-create-update'),
    path('pills/<int:id>/', views.PillDetailView.as_view(), name='pill-detail'),
    path('user-pills/', views.UserPillsView.as_view(), name='user-pills'),
    path('ratings/', views.CustomerRatingListCreateView.as_view(), name='customer-rating-list-create'),
    path('ratings/<int:pk>/', views.CustomerRatingDetailView.as_view(), name='customer-rating-detail'),
    path('colors/', views.getColors.as_view(), name='color-list'),
    path('pay-requests/', views.PayRequestListCreateView.as_view(), name='pay-request-list-create'),
    path('discounts/active/', views.ProductsWithActiveDiscountAPIView.as_view(), name='products-with-discount'),
    path('loved-products/', views.LovedProductListCreateView.as_view(), name='loved-product-list-create'),
    path('loved-products/<int:pk>/', views.LovedProductRetrieveDestroyView.as_view(), name='loved-product-detail'),
    path('alerts/stock/', views.StockAlertCreateView.as_view(), name='stock-alert-create'),
    path('alerts/price-drop/', views.PriceDropAlertCreateView.as_view(), name='price-drop-alert-create'),
    path('alerts/my-alerts/', views.UserActiveAlertsView.as_view(), name='active-alerts'),
    path('alerts/mark-notified/<str:alert_type>/<int:alert_id>/', views.MarkAlertAsNotifiedView.as_view(), name='mark-alert-notified'),
    path('products/new-arrivals/', views.NewArrivalsView.as_view(), name='new-arrivals'),
    path('products/best-sellers/', views.BestSellersView.as_view(), name='best-sellers'),
    path('products/frequently-bought-together/', views.FrequentlyBoughtTogetherView.as_view(), name='frequently-bought-together'),
    path('products/recommendations/', views.ProductRecommendationsView.as_view(), name='recommendations'),
    path('spin-wheel/', views.SpinWheelView.as_view(), name='spin-wheel'),
    path('spin-wheel/history/', views.SpinWheelHistoryView.as_view(), name='spin-wheel-history'),
    path('spin-wheel-coupons/', views.UserSpinWheelCouponsView.as_view(), name='user-spin-wheel-coupons'),
    path('products/<int:product_id>/availabilities/', views.ProductAvailabilitiesView.as_view(), name='product-availabilities'),
    # this endpoint for khazenly to get product availabilities with total
    path('products/<str:product_number>/availabilities-with-total/', 
     views.ProductAvailabilitiesWithTotalView.as_view(), 
     name='product-availabilities-with-total'),
    # Admin Endpoints
    path('dashboard/categories/', views.CategoryListCreateView.as_view(), name='admin-category-list-create'),
    path('dashboard/categories/<int:pk>/', views.CategoryRetrieveUpdateDestroyView.as_view(), name='admin-category-detail'),
    path('dashboard/subcategories/', views.SubCategoryListCreateView.as_view(), name='admin-subcategory-list-create'),
    path('dashboard/subcategories/<int:pk>/', views.SubCategoryRetrieveUpdateDestroyView.as_view(), name='admin-subcategory-detail'),
    path('dashboard/brands/', views.BrandListCreateView.as_view(), name='admin-brand-list-create'),
    path('dashboard/brands/<int:pk>/', views.BrandRetrieveUpdateDestroyView.as_view(), name='admin-brand-detail'),
    path('dashboard/subjects/', views.SubjectListCreateView.as_view(), name='admin-subject-list-create'),
    path('dashboard/subjects/<int:pk>/', views.SubjectRetrieveUpdateDestroyView.as_view(), name='admin-subject-detail'),
    path('dashboard/teachers/', views.TeacherListCreateView.as_view(), name='admin-teacher-list-create'),
    path('dashboard/teachers/<int:pk>/', views.TeacherRetrieveUpdateDestroyView.as_view(), name='admin-teacher-detail'),
    path('dashboard/colors/', views.ColorListCreateView.as_view(), name='admin-color-list-create'),
    path('dashboard/colors/<int:id>/', views.ColorRetrieveUpdateDestroyView.as_view(), name='admin-color-detail'),
    path('dashboard/products/', views.ProductListCreateView.as_view(), name='admin-product-list-create'),
    path('dashboard/products-breifed/', views.ProductListBreifedView.as_view(), name='admin-product-list-breifed'),
    path('dashboard/products/<int:pk>/', views.ProductRetrieveUpdateDestroyView.as_view(), name='admin-product-detail'),
    path('dashboard/product-images/', views.ProductImageListCreateView.as_view(), name='admin-product-image-list-create'),
    path('dashboard/product-images/bulk-upload/', views.ProductImageBulkCreateView.as_view(), name='admin-product-image-bulk-create'),
    path('dashboard/product-images/<int:pk>/', views.ProductImageDetailView.as_view(), name='admin-product-image-detail'),
    path('dashboard/product-descriptions/', views.ProductDescriptionListCreateView.as_view(), name='admin-product-description-list-create'),
    path('dashboard/product-descriptions/bulk/', views.ProductDescriptionBulkCreateView.as_view(), name='admin-product-description-bulk-create'),
    path('dashboard/product-descriptions/<int:pk>/', views.ProductDescriptionRetrieveUpdateDestroyView.as_view(), name='admin-product-description-detail'),
    path('dashboard/special-products/', views.SpecialProductListCreateView.as_view(), name='admin-special-product-list-create'),
    path('dashboard/special-products/<int:pk>/', views.SpecialProductRetrieveUpdateDestroyView.as_view(), name='admin-special-product-detail'),
    path('dashboard/best-products/', views.BestProductListCreateView.as_view(), name='admin-best-product-list-create'),
    path('dashboard/best-products/<int:pk>/', views.BestProductRetrieveUpdateDestroyView.as_view(), name='admin-best-product-detail'),

    
    # PillItems endpoints
    path('dashboard/pill-items/', views.PillItemListCreateView.as_view(), name='pillitem-list'),
    path('dashboard/pill-items/<int:pk>/', views.PillItemRetrieveUpdateDestroyView.as_view(), name='pillitem-detail'),
    
    # LovedItems endpoints
    path('dashboard/loved-items/', views.LovedProductListCreateView.as_view(), name='lovedproduct-list'),
    path('dashboard/loved-items/<int:pk>/', views.LovedProductRetrieveDestroyView.as_view(), name='lovedproduct-detail'),
    
    path('dashboard/pills/', views.PillListCreateView.as_view(), name='admin-pill-list-create'),
    path('dashboard/pills/<int:pk>/', views.PillRetrieveUpdateDestroyView.as_view(), name='admin-pill-detail'),
    path('dashboard/discounts/', views.DiscountListCreateView.as_view(), name='admin-discount-list-create'),
    path('dashboard/discounts/<int:pk>/', views.DiscountRetrieveUpdateDestroyView.as_view(), name='admin-discount-detail'),
    path('dashboard/coupons/', views.CouponListCreateView.as_view(), name='admin-coupon-list-create'),
    path('dashboard/coupons/<int:pk>/', views.CouponRetrieveUpdateDestroyView.as_view(), name='admin-coupon-detail'),
    path('dashboard/shipping/', views.ShippingListCreateView.as_view(), name='admin-shipping-list-create'),
    path('dashboard/shipping/<int:pk>/', views.ShippingRetrieveUpdateDestroyView.as_view(), name='admin-shipping-detail'),
    path('dashboard/ratings/', views.RatingListCreateView.as_view(), name='admin-rating-list-create'),
    path('dashboard/ratings/<int:pk>/', views.RatingDetailView.as_view(), name='admin-rating-detail'),
    path('dashboard/product-availabilities/', views.ProductAvailabilityListCreateView.as_view(), name='admin-product-availability-list-create'),
    path('dashboard/product-availabilities/<int:pk>/', views.ProductAvailabilityDetailView.as_view(), name='admin-product-availability-detail'),
    path('dashboard/pay-requests/create/', views.AdminPayRequestCreateView.as_view(), name='admin-pay-request-create'),
    path('dashboard/pay-requests/<int:id>/apply/', views.ApplyPayRequestView.as_view(), name='admin-pay-request-apply'),
    path('dashboard/spin-wheel/', views.SpinWheelDiscountListCreateView.as_view(), name='spin-wheel-list-create'),
    path('dashboard/spin-wheel/<int:pk>/', views.SpinWheelDiscountRetrieveUpdateDestroyView.as_view(), name='spin-wheel-detail'),
    path('dashboard/spin-wheel-settings/', views.SpinWheelSettingsView.as_view(), name='spin-wheel-settings'),
    path('dashboard/pill-gifts/', views.PillGiftListCreateView.as_view(), name='pill-gift-list-create'),
    path('dashboard/pill-gifts/<int:pk>/', views.PillGiftRetrieveUpdateDestroyView.as_view(), name='pill-gift-detail'),


    # Fawaterak Payment API Endpoints (DRF-based)
    path('api/payment/create/<int:pill_id>/', payment_views.create_payment_view, name='api_create_payment'),
    path('api/payment/webhook/fawaterak/', payment_views.fawaterak_webhook, name='api_fawaterak_webhook'),  # Uses the correct one
    path('api/payment/success/<str:pill_number>/', payment_views.payment_success_view, name='api_payment_success'),
    path('api/payment/failed/<str:pill_number>/', payment_views.payment_failed_view, name='api_payment_failed'),
    path('api/payment/pending/<str:pill_number>/', payment_views.payment_pending_view, name='api_payment_pending'),
    path('api/payment/status/<int:pill_id>/', payment_views.check_payment_status_view, name='api_check_payment_status'),

    # FALLBACK: Handle Fawaterak's incorrect redirect URLs with /products prefix
    path('products/api/payment/success/<str:pill_number>/', payment_views.payment_success_view, name='fallback_payment_success'),
    path('products/api/payment/failed/<str:pill_number>/', payment_views.payment_failed_view, name='fallback_payment_failed'),
    path('products/api/payment/pending/<str:pill_number>/', payment_views.payment_pending_view, name='fallback_payment_pending'),
    

    
    # Khazenly Webhook
    path('api/webhook/khazenly/order-status/', khazenly_order_status_webhook, name='khazenly_order_status_webhook'),
    # Shake-out Webhook
    path('api/webhook/shakeout/', shakeout_webhook, name='shakeout_webhook'),
    # EasyPay Webhook
    path('api/webhook/easypay/', easypay_webhook, name='easypay_webhook'),
    path('api/webhook/easypay/<str:api_key>/', easypay_webhook, name='easypay_webhook_with_key'),
    # Shake-out Invoice Creation Endpoint
    path('pills/<int:pill_id>/create-shakeout-invoice/', payment_views.create_shakeout_invoice_view, name='create_shakeout_invoice'),
    # EasyPay Invoice Creation Endpoint
    path('pills/<int:pill_id>/create-easypay-invoice/', payment_views.create_easypay_invoice_view, name='create_easypay_invoice'),
    # Generic Payment Invoice Creation Endpoint
    path('pills/<int:pill_id>/create-payment-invoice/', payment_views.create_payment_invoice_view, name='create_payment_invoice'),
    
    # Khazenly 
    path('api/resend-khazenly-orders/', views.resend_khazenly_orders_view, name='resend_khazenly_orders'),
]

