
from rest_framework import serializers

from products.models import Category, Product
from accounts.models import User

class ProductAnalyticsSerializer(serializers.ModelSerializer):
    # Use select_related in the view for this field for efficiency
    category_name = serializers.CharField(source='category.name', read_only=True, default="No Category")
    
    # These fields are all calculated in the view's annotation
    total_available = serializers.IntegerField(read_only=True)
    total_added = serializers.IntegerField(read_only=True) 
    total_sold = serializers.IntegerField(read_only=True)
    revenue = serializers.FloatField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    total_ratings = serializers.IntegerField(read_only=True)
    has_discount = serializers.BooleanField(read_only=True)
    current_discount = serializers.FloatField(read_only=True)
    price_after_discount = serializers.FloatField(read_only=True)

    # We will annotate this field in the view to avoid N+1 queries
    is_low_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category_name', 'price', 'threshold', 'date_added',
            'total_available', 'total_added', 'total_sold', 'revenue', 
            'average_rating', 'total_ratings', 'has_discount', 'current_discount', 
            'price_after_discount', 'is_low_stock'
        ]

class ProductBuyerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'username', 'year']

class CategoryAnalyticsSerializer(serializers.ModelSerializer):
    total_products = serializers.IntegerField(read_only=True)
    total_sales = serializers.IntegerField(read_only=True)
    revenue = serializers.FloatField(read_only=True)
    total_available_quantity = serializers.IntegerField(read_only=True) # <-- Add this line

    class Meta:
        model = Category
        fields = [
            'id', 
            'name', 
            'total_products', 
            'total_sales', 
            'revenue', 
            'total_available_quantity' # <-- And add it here
        ]


class InventoryAlertSerializer(serializers.ModelSerializer):
    total_available = serializers.IntegerField()
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'total_available', 'category']


class SalesTrendSerializer(serializers.Serializer):
    total_sales = serializers.IntegerField()
    revenue = serializers.FloatField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()





