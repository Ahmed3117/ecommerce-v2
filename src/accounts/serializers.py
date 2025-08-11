from django.db.models import Count, Sum, F
from rest_framework import serializers
from rest_framework.fields import ImageField

from products.models import PILL_STATUS_CHOICES, LovedProduct, Pill, Product
from products.serializers import LovedProductSerializer, PillDetailSerializer
from .models import User, UserAddress, UserProfileImage
from django.db.models import Count, Sum, Case, When, Value, FloatField
from django.db.models.functions import Coalesce

class UserProfileImageSerializer(serializers.ModelSerializer):
    image = ImageField(use_url=True) # Explicitly set use_url to True

    class Meta:
        model = UserProfileImage
        fields = ['id', 'image', 'created_at', 'updated_at']

class UserProfileImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfileImage
        fields = ['image']
        
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)  # Make password optional for updates
    user_profile_image = UserProfileImageSerializer(read_only=True)
    user_profile_image_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfileImage.objects.all(),
        source='user_profile_image',
        required=False,
        allow_null=True
    )
    cart_items_count = serializers.SerializerMethodField()
    last_cart_added = serializers.SerializerMethodField()
    loved_count = serializers.SerializerMethodField()
    pill_stats = serializers.SerializerMethodField()
    financial_summary = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'password', 'name','government', 'city',
            'is_staff', 'is_superuser', 'user_type', 'phone','phone2','parent_phone',
            'year', 'address', 'user_profile_image',
            'user_profile_image_id','created_at', 
            'cart_items_count', 'last_cart_added',
            'loved_count', 'pill_stats', 'financial_summary'
        )
        extra_kwargs = {
            'is_staff': {'read_only': True},
            'is_superuser': {'read_only': True},
            'email': {'required': False, 'allow_null': True, 'allow_blank': True},
            'user_type': {'required': False, 'allow_null': True},
            'phone': {'required': False, 'allow_null': True, 'allow_blank': True},
            'phone2': {'required': False, 'allow_null': True, 'allow_blank': True},
            'parent_phone': {'required': False, 'allow_null': True, 'allow_blank': True},
            'year': {'required': False, 'allow_null': True},
            'address': {'required': False, 'allow_null': True, 'allow_blank': True},
            'password': {'required': False},  # Make password optional for updates
        }
    
    def update(self, instance, validated_data):
        """
        Handle user updates with proper password hashing
        """
        # Extract password from validated_data
        password = validated_data.pop('password', None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle password separately to ensure proper hashing
        if password:
            instance.set_password(password)  # This properly hashes the password
        
        instance.save()
        return instance

    def create(self, validated_data):
        """
        Handle user creation with proper password hashing
        """
        profile_image = validated_data.pop('user_profile_image', None)
        email = validated_data.get('email', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=email,
            password=validated_data['password'],
            name=validated_data.get('name', ''),
            is_staff=validated_data.get('is_staff', False),
            is_superuser=validated_data.get('is_superuser', False),
            user_type=validated_data.get('user_type', None),
            phone=validated_data.get('phone', None),
            phone2=validated_data.get('phone2', None),
            parent_phone=validated_data.get('parent_phone', None),
            year=validated_data.get('year', None),
            address=validated_data.get('address', None),
            government=validated_data.get('government', None),
            city=validated_data.get('city', None),
            user_profile_image=profile_image
        )
        return user
    
    def get_cart_items_count(self, obj):
        from products.models import PillItem
        return PillItem.objects.filter(user=obj, status__isnull=True).count()
    
    def get_last_cart_added(self, obj):
        from products.models import PillItem
        last_item = PillItem.objects.filter(
            user=obj, 
            status__isnull=True
        ).order_by('-date_added').first()
        return last_item.date_added if last_item else None
    
    def get_loved_count(self, obj):
        return obj.loved_products.count()
    
    def get_pill_stats(self, obj):
        status_counts = {status[0]: 0 for status in PILL_STATUS_CHOICES}
        for status, count in obj.pills.values_list('status').annotate(
            count=Count('id')
        ):
            status_counts[status] = count
        return {
            'total': sum(status_counts.values()),
            'by_status': status_counts
        }
    
    def get_financial_summary(self, obj):
        paid = 0
        pending = 0
        
        for pill in obj.pills.all():
            if pill.status == 'd':
                paid += pill.final_price()
            elif pill.status not in ['r', 'c']:
                pending += pill.final_price()
        
        return {
            'total_paid': paid,
            'total_pending': pending,
            'all_time_total': paid + pending
        }

class PasswordResetRequestSerializer(serializers.Serializer):
    phone = serializers.CharField()  # Changed from email to phone

class PasswordResetConfirmSerializer(serializers.Serializer):
    phone = serializers.CharField() 
    otp = serializers.CharField()
    new_password = serializers.CharField()

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)

class UserAddressSerializer(serializers.ModelSerializer):
    government_name = serializers.SerializerMethodField()

    class Meta:
        model = UserAddress
        fields = ['id', 'name', 'email', 'phone','phone2', 'address', 'government', 'government_name','is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_government_name(self, obj):
        return obj.get_government_display()

    def validate(self, data):
        # Ensure only one default address per user
        if data.get('is_default', False):
            UserAddress.objects.filter(user=self.context['request'].user, is_default=True).update(is_default=False)
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    addresses = UserAddressSerializer(many=True, read_only=True)
    pills = serializers.SerializerMethodField()
    loved_products = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    favorite_category = serializers.SerializerMethodField()
    user_profile_image = UserProfileImageSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'name', 'user_type', 'phone','phone2','parent_phone', 'year',
            'address', 'user_profile_image', 'addresses', 'pills',
            'loved_products', 'total_spent', 'favorite_category'
        ]

    def get_pills(self, obj):
        pills = Pill.objects.filter(user=obj).order_by('-date_added')[:10]
        # Pass context to nested serializer for full image URLs if Pills had images
        return PillDetailSerializer(pills, many=True, context=self.context).data

    def get_loved_products(self, obj):
        loved_products = LovedProduct.objects.filter(user=obj).order_by('-created_at')[:10]
        # Pass context to nested serializer for full image URLs if LovedProducts had images
        return LovedProductSerializer(loved_products, many=True, context=self.context).data

    def get_total_spent(self, obj):
        return Pill.objects.filter(
            user=obj,
            status='d'
        ).annotate(
            total_price=Sum(F('items__quantity') * F('items__product__price'))
        ).aggregate(total_spent=Sum('total_price'))['total_spent'] or 0

    def get_favorite_category(self, obj):
        favorite = Product.objects.filter(
            pill_items__pill__user=obj  
        ).values(
            'category__name'
        ).annotate(
            count=Count('category')
        ).order_by('-count').first()
        return favorite['category__name'] if favorite else None

class UserDetailSerializer(serializers.ModelSerializer):
    addresses = UserAddressSerializer(many=True, read_only=True)
    pill_stats = serializers.SerializerMethodField()
    loved_products = serializers.SerializerMethodField()
    financial_summary = serializers.SerializerMethodField()
    user_profile_image = UserProfileImageSerializer(read_only=True)
    cart_items = serializers.SerializerMethodField()
    last_cart_added = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'name', 'email', 'phone','phone2','parent_phone', 'user_type', 'year',
            'government', 'city', 'address', 'created_at', 'user_profile_image',
            'addresses', 'pill_stats', 'loved_products', 'financial_summary',
            'cart_items', 'last_cart_added' 
        ]

    
    def get_pill_stats(self, obj):
        status_counts = {status[0]: 0 for status in PILL_STATUS_CHOICES}
        for status, count in obj.pills.values_list('status').annotate(
            count=Count('id')
        ):
            status_counts[status] = count
        
        recent_pills = []
        for pill in obj.pills.order_by('-date_added')[:5]:
            recent_pills.append({
                'id': pill.id,
                'pill_number': pill.pill_number,
                'status': pill.status,
                'date_added': pill.date_added,
                'final_price': pill.final_price()
            })
        
        return {
            'total': sum(status_counts.values()),
            'by_status': status_counts,
            'recent_pills': recent_pills
        }
    
    def get_loved_products(self, obj):
        # You might need to adjust this if LovedProduct has an image,
        # but the request context is passed if needed.
        return obj.loved_products.order_by('-created_at')[:10].values(
            'id', 'product__name', 'created_at'
        )
    
    def get_financial_summary(self, obj):
        paid = 0
        pending = 0
        
        for pill in obj.pills.all():
            if pill.status == 'd':
                paid += pill.final_price()
            elif pill.status not in ['r', 'c']:
                pending += pill.final_price()
        
        return {
            'total_paid': paid,
            'total_pending': pending,
            'all_time_total': paid + pending
        }

    def get_cart_items(self, obj):
        from products.models import PillItem
        from products.serializers import PillItemSerializer
        
        cart_items = PillItem.objects.filter(
            user=obj,
            status__isnull=True
        ).select_related('product', 'color')
        
        # Pass context to nested serializer for full image URLs
        return PillItemSerializer(cart_items, many=True, context=self.context).data

    def get_last_cart_added(self, obj):
        from products.models import PillItem
        
        last_item = PillItem.objects.filter(
            user=obj,
            status__isnull=True
        ).order_by('-date_added').first()
        
        return last_item.date_added if last_item else None