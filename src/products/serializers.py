from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from collections import defaultdict
from urllib.parse import urljoin
from django.utils import timezone
from django.db.models import Sum
from django.db import transaction
from accounts.models import User
from .models import (
    BestProduct, Category, CartSettings, CouponDiscount, Discount, LovedProduct, PayRequest, PillAddress, PillGift,
    PillItem, PillStatusLog, PriceDropAlert, ProductDescription, Shipping,
    SpecialProduct, SpinWheelDiscount, SpinWheelResult, SpinWheelSettings, StockAlert,
    SubCategory, Brand, Product, ProductImage, ProductAvailability, Rating, Color, Pill, Subject, Teacher
)

class SubCategorySerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'category', 'category_name']

    def get_category_name(self, obj):
        return obj.category.name
    
class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'image', 'subcategories','type']

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__'

class TeacherSerializer(serializers.ModelSerializer):
    subject_name = serializers.SerializerMethodField()
    class Meta:
        model = Teacher
        fields = ['id', 'name', 'bio','image','subject','subject_name' , 'facebook', 'instagram', 'twitter', 'youtube', 'linkedin', 'telegram', 'website','tiktok', 'whatsapp']

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None

class ProductDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductDescription
        fields = ['id', 'title', 'description', 'order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ProductDescriptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductDescription
        fields = ['product', 'title', 'description', 'order']
    
    def to_internal_value(self, data):
        if isinstance(data, list):
            return [super().to_internal_value(item) for item in data]
        return super().to_internal_value(data)

class BulkProductDescriptionSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        descriptions = [ProductDescription(**item) for item in validated_data]
        return ProductDescription.objects.bulk_create(descriptions)

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = '__all__'

class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = '__all__'

class ProductAvailabilitySerializer(serializers.ModelSerializer):
    color = serializers.PrimaryKeyRelatedField(
        queryset=Color.objects.all(),
        allow_null=True,
        required=False
    )
    size = serializers.CharField(
        allow_null=True,
        required=False
    )
    product_name = serializers.SerializerMethodField()
    native_price = serializers.FloatField()

    class Meta:
        model = ProductAvailability
        fields = ['id', 'product', 'product_name', 'size', 'color', 'quantity', 'native_price', 'date_added']
        read_only_fields = ['date_added']

    def get_product_name(self, obj):
        return obj.product.name

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.color:
            representation['color'] = ColorSerializer(instance.color).data
        else:
            representation['color'] = None
        return representation

class ProductAvailabilityBreifedSerializer(serializers.Serializer):
    size = serializers.CharField()
    color = serializers.CharField()
    quantity = serializers.IntegerField()
    is_low_stock = serializers.SerializerMethodField()

    def get_is_low_stock(self, obj):
        return obj.product.is_low_stock()
    

class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'product', 'user', 'star_number', 'review', 'date_added']
        read_only_fields = ['date_added', 'user']

    def validate(self, data):
        if data.get('star_number') < 1 or data.get('star_number') > 5:
            raise serializers.ValidationError("Star number must be between 1 and 5.")
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class ProductImageBulkUploadSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    images = serializers.ListField(
        child=serializers.ImageField(),
        allow_empty=False
    )

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    availabilities = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()
    number_of_ratings = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()
    available_colors = serializers.SerializerMethodField()
    available_sizes = serializers.SerializerMethodField()
    current_discount = serializers.SerializerMethodField()
    discount_expiry = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    descriptions = ProductDescriptionSerializer(many=True, read_only=True)
    category_id = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    subject_id = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    teacher_id = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    teacher_image = serializers.SerializerMethodField()
    sub_category_id = serializers.SerializerMethodField()
    sub_category_name = serializers.SerializerMethodField()
    brand_id = serializers.SerializerMethodField()
    brand_name = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'product_number','name','type','year','category','sub_category','brand','subject' ,'teacher' , 'category_id', 'category_name', 'subject_id' ,'subject_name' , 'teacher_id' ,'teacher_name','teacher_image', 'sub_category_id', 'sub_category_name',
            'brand_id', 'brand_name', 'price', 'description', 'date_added', 'discounted_price',
            'has_discount', 'current_discount', 'discount_expiry', 'main_image', 'images', 'number_of_ratings',
            'average_rating', 'total_quantity', 'available_colors', 'available_sizes', 'availabilities',
            'descriptions', 'threshold', 'is_low_stock', 'is_important','base_image'
        ]
        read_only_fields = [
            'product_number'
        ]

    def get_category_id(self, obj):
        return obj.category.id if obj.category else None

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_sub_category_id(self, obj):
        return obj.sub_category.id if obj.sub_category else None

    def get_sub_category_name(self, obj):
        return obj.sub_category.name if obj.sub_category else None

    def get_subject_id(self, obj):
        return obj.subject.id if obj.subject else None
    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None
    def get_teacher_id(self, obj):
        return obj.teacher.id if obj.teacher else None
    def get_teacher_name(self, obj):
        return obj.teacher.name if obj.teacher else None
    def get_teacher_image(self, obj):
        if obj.teacher and obj.teacher.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.teacher.image.url)
            return obj.teacher.image.url
        return None
    def get_brand_id(self, obj):
        return obj.brand.id if obj.brand else None

    def get_brand_name(self, obj):
        return obj.brand.name if obj.brand else None

    def get_availabilities(self, obj):
        grouped_availabilities = defaultdict(int)
        for availability in obj.availabilities.all():
            key = (availability.size, availability.color.id if availability.color else None, availability.color.name if availability.color else None)
            grouped_availabilities[key] += availability.quantity
        result = [
            {
                "size": size,
                "color_id": color_id,
                "color": color_name,
                "quantity": quantity
            }
            for (size, color_id, color_name), quantity in grouped_availabilities.items()
        ]
        return result

    def get_discounted_price(self, obj):
        return obj.discounted_price()

    def get_current_discount(self, obj):
        now = timezone.now()
        product_discount = obj.discounts.filter(
            is_active=True,
            discount_start__lte=now,
            discount_end__gte=now
        ).order_by('-discount').first()
        category_discount = None
        if obj.category:
            category_discount = obj.category.discounts.filter(
                is_active=True,
                discount_start__lte=now,
                discount_end__gte=now
            ).order_by('-discount').first()
        if product_discount and category_discount:
            return max(product_discount.discount, category_discount.discount)
        elif product_discount:
            return product_discount.discount
        elif category_discount:
            return category_discount.discount
        return None

    def get_discount_expiry(self, obj):
        now = timezone.now()
        discount = obj.discounts.filter(
            is_active=True,
            discount_start__lte=now,
            discount_end__gte=now
        ).order_by('-discount_end').first()
        if not discount and obj.category:
            discount = obj.category.discounts.filter(
                is_active=True,
                discount_start__lte=now,
                discount_end__gte=now
            ).order_by('-discount_end').first()
        return discount.discount_end if discount else None
    
    def get_has_discount(self, obj):
        return obj.has_discount()

    def get_main_image(self, obj):
        main_image = obj.main_image()
        print(f"Main image type: {type(main_image)}")  # Debug output
        if main_image and hasattr(main_image, 'url'):
            print(f"Main image URL: {main_image.url}")  # Debug output
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(main_image.url)
            return main_image.url
        return None

    def get_number_of_ratings(self, obj):
        return obj.number_of_ratings()

    def get_average_rating(self, obj):
        return obj.average_rating()

    def get_total_quantity(self, obj):
        return obj.total_quantity()

    def get_available_colors(self, obj):
        return obj.available_colors()

    def get_available_sizes(self, obj):
        return obj.available_sizes()

    def get_is_low_stock(self, obj):
        return obj.is_low_stock()

class ProductBreifedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name','type']

class CouponCodeField(serializers.Field):
    def to_internal_value(self, data):
        try:
            return CouponDiscount.objects.get(coupon=data)
        except CouponDiscount.DoesNotExist:
            raise serializers.ValidationError("Coupon does not exist.")

    def to_representation(self, value):
        return value.coupon

class SpecialProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = SpecialProduct
        fields = [
            'id', 'product', 'product_id', 'special_image',
            'order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class BestProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = BestProduct
        fields = [
            'id', 'product', 'product_id',
            'order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class UserCartSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    color = ColorSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()
    # ADDED: Field for maximum available quantity
    max_quantity = serializers.SerializerMethodField(
        read_only=True,
        help_text="Maximum quantity available for this specific item variant (size/color)"
    )

    class Meta:
        model = PillItem
        # UPDATED: Added 'max_quantity' to fields
        fields = [
            'id', 
            'product', 
            'quantity', 
            'size', 
            'color', 
            'total_price', 
            'max_quantity', # Added here
            'date_added'
        ]

    def get_total_price(self, obj):
        """Calculates the total price for the item based on its quantity and discounted price."""
        if obj.product:
            # Assuming product.discounted_price() method exists and returns the correct price
            return obj.product.discounted_price() * obj.quantity
        return 0

    def _get_max_quantity(self, product, size, color):
        if not product:
            return 0

        filters = {
            'product': product,
            'size': size,
        }
        
        if color:
            filters['color'] = color
        else:
            filters['color__isnull'] = True

        availabilities = ProductAvailability.objects.filter(**filters)
        total_available = availabilities.aggregate(total=Sum('quantity'))['total'] or 0
        return total_available

    # ADDED: Method to calculate the maximum available quantity
    def get_max_quantity(self, obj):
        return self._get_max_quantity(obj.product, obj.size, obj.color)


class PillCouponApplySerializer(serializers.ModelSerializer):
    coupon = CouponCodeField()
    discount_percentage = serializers.SerializerMethodField()
    price_after_coupon_discount = serializers.SerializerMethodField()

    class Meta:
        model = Pill
        fields = [
            'id', 'coupon',
            'price_without_coupons_or_gifts', 'coupon_discount',
            'price_after_coupon_discount', 'final_price',
            'discount_percentage'
        ]
        read_only_fields = [
            'id', 'price_without_coupons_or_gifts',
            'coupon_discount', 'price_after_coupon_discount',
            'final_price', 'discount_percentage'
        ]

    def validate_coupon(self, value):
        pill = self.instance
        now = timezone.now()
        # Check if coupon is valid
        if not (value.coupon_start <= now <= value.coupon_end):
            raise serializers.ValidationError(
                {"message": "This coupon has expired."}
            )
        # Check if coupon is already applied
        if pill.coupon:
            raise serializers.ValidationError(
                {"message": "A coupon is already applied to this order."}
            )
        # Check coupon usage limits
        if value.available_use_times <= 0:
            raise serializers.ValidationError(
                {"message": "This coupon has no remaining uses."}
            )
        # Check if coupon is tied to user for wheel coupons
        if value.is_wheel_coupon and value.user != self.context['request'].user:
            raise serializers.ValidationError(
                {"message": "This coupon is not valid for your account."}
            )
        # Check minimum order value
        if value.min_order_value and pill.price_without_coupons_or_gifts() < value.min_order_value:
            raise serializers.ValidationError({
                "message": f"Order must be at least {value.min_order_value} to use this coupon."
            })
        return value

    def get_discount_percentage(self, obj):
        base_price = obj.price_without_coupons_or_gifts()
        if obj.coupon and base_price > 0:
            return round((obj.calculate_coupon_discount() / base_price) * 100)
        return 0

    def get_price_after_coupon_discount(self, obj):
        base_price = obj.price_without_coupons_or_gifts()
        coupon_discount = obj.calculate_coupon_discount()
        return max(0, base_price - coupon_discount)

    def update(self, instance, validated_data):
        coupon = validated_data.get('coupon')
        instance.coupon = coupon
        instance.coupon_discount = (coupon.discount_value / 100) * instance.price_without_coupons_or_gifts()
        instance.save()
        # Update coupon usage
        coupon.available_use_times -= 1
        coupon.save()
        return instance



class PillAddressSerializer(serializers.ModelSerializer):
    government = serializers.SerializerMethodField()

    class Meta:
        model = PillAddress
        fields = ['name', 'email', 'phone', 'address', 'government','city', 'pay_method']

    def get_government(self, obj):
        return obj.get_government_display()

class PillItemCreateUpdateSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    color = serializers.PrimaryKeyRelatedField(
        queryset=Color.objects.all(), 
        required=False, 
        allow_null=True
    )
    max_quantity = serializers.SerializerMethodField(
        read_only=True,
        help_text="Maximum quantity available for this item"
    )

    class Meta:
        model = PillItem
        fields = ['id', 'product', 'quantity', 'size', 'color', 'max_quantity']  # Added 'id'
        extra_kwargs = {
            'max_quantity': {'read_only': True}
        }

    def _get_max_quantity(self, product, size, color):
        if not product:
            return 0

        filters = {'product': product}
        
        # Handle size (can be None)
        if size is not None:
            filters['size'] = size
        else:
            filters['size__isnull'] = True
        
        # Handle color (can be None)
        if color is not None:
            filters['color'] = color
        else:
            filters['color__isnull'] = True
        
        availabilities = ProductAvailability.objects.filter(**filters)
        total_available = availabilities.aggregate(total=Sum('quantity'))['total'] or 0
        return total_available

    def get_max_quantity(self, obj):
        if isinstance(obj, PillItem):
            return self._get_max_quantity(obj.product, obj.size, obj.color)
        else:
            product = self.validated_data.get('product')
            size = self.validated_data.get('size')
            color = self.validated_data.get('color')
            return self._get_max_quantity(product, size, color)
        
    def to_internal_value(self, data):
        # Handle case where frontend might send full objects instead of just IDs
        if isinstance(data.get('product'), dict):
            data['product'] = data['product'].get('id')
        if isinstance(data.get('color'), dict):
            data['color'] = data['color'].get('id')
        return super().to_internal_value(data)

    def validate(self, data):
        instance = getattr(self, 'instance', None)
        product = data.get('product', getattr(instance, 'product', None))
        size = data.get('size', getattr(instance, 'size', None))
        color = data.get('color', getattr(instance, 'color', None))
        quantity = data.get('quantity', getattr(instance, 'quantity', 1))

        self._validate_stock(product, size, color, quantity)
        return data

    def _validate_stock(self, product, size, color, quantity):
        if quantity <= 0:
            raise serializers.ValidationError({
                'quantity': 'Quantity must be greater than 0.'
            })

        availabilities = ProductAvailability.objects.filter(
            product=product,
            size=size,
            color=color
        )

        if not availabilities.exists():
            color_name = color.name if color else 'N/A'
            raise serializers.ValidationError({
                'non_field_errors': [
                    f"The selected variant (Size: {size or 'N/A'}, Color: {color_name}) "
                    f"is not available for {product.name}."
                ]
            })

        total_available = availabilities.aggregate(total=Sum('quantity'))['total'] or 0

        if total_available < quantity:
            color_name = color.name if color else 'N/A'
            raise serializers.ValidationError({
                'quantity': [
                    f"Not enough stock for {product.name} "
                    f"(Size: {size or 'N/A'}, Color: {color_name}). "
                    f"Available: {total_available}, Requested: {quantity}."
                ]
            })


class PillItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    color = ColorSerializer(read_only=True)
    max_quantity = serializers.SerializerMethodField(
        read_only=True,
        help_text="Maximum quantity available for this item"
    )

    class Meta:
        model = PillItem
        fields = ['id', 'product', 'quantity', 'size', 'color', 'status', 'date_added', 'max_quantity']

    def _get_max_quantity(self, product, size, color):
        if not product:
            return 0

        filters = {
            'product': product,
            'size': size,
        }
        
        if color:
            filters['color'] = color
        else:
            filters['color__isnull'] = True

        availabilities = ProductAvailability.objects.filter(**filters)
        total_available = availabilities.aggregate(total=Sum('quantity'))['total'] or 0
        return total_available

    def get_max_quantity(self, obj):
        return self._get_max_quantity(obj.product, obj.size, obj.color)


class PillItemCreateSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    color = serializers.PrimaryKeyRelatedField(queryset=Color.objects.all(), required=False, allow_null=True)
    status = serializers.CharField(read_only=True)
    max_quantity = serializers.SerializerMethodField(
        read_only=True,
        help_text="Maximum quantity available for this item"
    )

    class Meta:
        model = PillItem
        fields = ['id', 'product', 'quantity', 'size', 'color', 'status','max_quantity']

    def get_max_quantity(self, obj):
        # For existing instances
        if isinstance(obj, PillItem):
            product = obj.product
            size = obj.size
            color = obj.color
        # For new instances, get from validated data
        else:
            product = self.validated_data.get('product')
            size = self.validated_data.get('size')
            color = self.validated_data.get('color')

        if not product:
            return 0

        availabilities = ProductAvailability.objects.filter(
            product=product,
            size=size,
            color=color
        )
        
        total_available = availabilities.aggregate(total=Sum('quantity'))['total'] or 0
        return total_available

class AdminPillItemSerializer(PillItemCreateUpdateSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    user_details = serializers.SerializerMethodField()
    product_details = serializers.SerializerMethodField()
    color_details = serializers.SerializerMethodField()
    pill_details = serializers.SerializerMethodField()

    class Meta(PillItemCreateUpdateSerializer.Meta):
        fields = [
            'id', 'user', 'user_details', 'product', 'product_details', 
            'quantity', 'size', 'color', 'color_details', 'max_quantity',
            'status', 'date_added', 'pill', 'pill_details'
        ]
        read_only_fields = ['date_added', 'max_quantity']

    # Implement all required get_*_details methods
    def get_user_details(self, obj):
        user = obj.user
        if not user:
            return None
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'phone': user.phone
        }

    def get_product_details(self, obj):
        product = obj.product
        request = self.context.get('request')

        # Get the image object (either FileField or ImageField)
        image = product.main_image()

        # Handle the image URL properly
        if image:
            if hasattr(image, 'url'):
                # If it's a FileField/ImageField, get its URL
                image_url = image.url
                if request is not None:
                    # If we have a request, make it an absolute URI
                    image_url = request.build_absolute_uri(image_url)
            else:
                # If it's already a URL string, use it directly
                image_url = image
        else:
            image_url = None

        return {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'image': image_url
        }



    def get_color_details(self, obj):
        if not obj.color:
            return None
        return {
            'id': obj.color.id,
            'name': obj.color.name,
            'degree': obj.color.degree
        }

    def get_pill_details(self, obj):
        if not obj.pill:
            return None
        return {
            'id': obj.pill.id,
            'pill_number': obj.pill.pill_number,
            'status': obj.pill.status,
            'date_added': obj.pill.date_added
        }

    # Inherited from PillItemCreateUpdateSerializer
    # def get_max_quantity(self, obj):
    #     return self._get_max_quantity(obj.product, obj.size, obj.color)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure max_quantity is always included
        if 'max_quantity' not in ret:
            ret['max_quantity'] = self.get_max_quantity(instance)
        return ret

    def validate(self, data):
        data = super().validate(data)
        
        # Admin-specific validations
        if 'status' in data and data['status'] == 'd' and 'pill' not in data:
            raise serializers.ValidationError({
                'pill': 'Pill must be specified for delivered items'
            })
        
        return data

    def create(self, validated_data):
        # Set default user if not provided
        if 'user' not in validated_data and hasattr(self.context.get('request'), 'user'):
            validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class AdminLovedProductSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all()
    )
    user_details = serializers.SerializerMethodField()
    product_details = serializers.SerializerMethodField()

    class Meta:
        model = LovedProduct
        fields = [
            'id', 'user', 'user_details', 'product', 'product_details', 
            'created_at'
        ]
        read_only_fields = ['created_at']

    def get_user_details(self, obj):
        return {
            'id': obj.user.id if obj.user else None,
            'name': obj.user.name if obj.user else None,
            'email': obj.user.email if obj.user else None
        }

    def get_product_details(self, obj):
        product = obj.product
        request = self.context.get('request')
        
        main_image = None
        if product.main_image():
            if request:
                main_image = request.build_absolute_uri(product.main_image())
            else:
                main_image = product.main_image()
        
        return {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'image': main_image
        }

    def validate(self, data):
        # Check for duplicates
        if self.instance is None and LovedProduct.objects.filter(
            user=data.get('user', self.context.get('request').user),
            product=data['product']
        ).exists():
            raise serializers.ValidationError({
                'product': 'This product is already in the user\'s loved items'
            })
        return data

    def create(self, validated_data):
        # Set default user if not provided
        if 'user' not in validated_data and hasattr(self.context.get('request'), 'user'):
            validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class PillCreateSerializer(serializers.ModelSerializer):
    items = PillItemCreateSerializer(many=True, required=False)
    user_name = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_parent_phone = serializers.SerializerMethodField()
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Pill
        fields = ['id', 'user', 'user_name', 'user_username','user_phone', 'user_parent_phone','items', 'status', 'date_added', 'paid']
        read_only_fields = ['id', 'status', 'date_added', 'paid']
    def get_user_name(self, obj):
        return obj.user.name

    def get_user_username(self, obj):
        return obj.user.username
    def get_user_phone(self, obj):
        return obj.user.phone if obj.user else None
    def get_user_parent_phone(self, obj):
        return obj.user.parent_phone if obj.user else None

    def create(self, validated_data):
        user = validated_data['user']
        items_data = validated_data.pop('items', None)
        
        with transaction.atomic():
            # Create the pill first
            pill = Pill.objects.create(**validated_data)
            
            if items_data:
                # Create new items specifically for this pill
                pill_items = []
                for item_data in items_data:
                    item = PillItem.objects.create(
                        user=user,
                        product=item_data['product'],
                        quantity=item_data['quantity'],
                        size=item_data.get('size'),
                        color=item_data.get('color'),
                        status=pill.status,
                        pill=pill  # Link directly to the pill
                    )
                    pill_items.append(item)
                pill.items.set(pill_items)
            else:
                # Move cart items (status=None) to this pill
                cart_items = PillItem.objects.filter(user=user, status__isnull=True)
                if not cart_items.exists():
                    raise ValidationError("No items provided in request and no items in cart to create a pill.")
                
                # Update cart items to belong to this pill
                for item in cart_items:
                    item.status = pill.status
                    item.pill = pill
                    item.save()
                pill.items.set(cart_items)
            
            return pill

class PillStatusLogSerializer(serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = PillStatusLog
        fields = ['status', 'status_display', 'changed_at']

    def get_status_display(self, obj):
        return obj.get_status_display()

class PayRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayRequest
        fields = ['id', 'pill', 'image', 'date', 'is_applied']
        read_only_fields = ['id', 'date']

class ShippingSerializer(serializers.ModelSerializer):
    government_name = serializers.SerializerMethodField()

    class Meta:
        model = Shipping
        fields = ['id', 'government', 'government_name', 'shipping_price']

    def get_government_name(self, obj):
        return obj.get_government_display()

class PillAddressCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PillAddress
        fields = ['id', 'pill', 'name', 'email', 'phone', 'address', 'government','city', 'pay_method']
        read_only_fields = ['id', 'pill']

    def validate_government(self, value):
        """Validate that government is provided"""
        if not value:
            raise serializers.ValidationError("Government field is required.")
        return value

    def validate(self, data):
        """Additional validation for the entire object"""
        if not data.get('government'):
            raise serializers.ValidationError({
                'government': 'Government field is required when creating a pill address.'
            })
        return data

class CouponDiscountSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = CouponDiscount
        fields = ['id', 'coupon', 'discount_value', 'coupon_start', 'coupon_end', 'available_use_times', 'is_wheel_coupon', 'user', 'min_order_value', 'is_active', 'is_available']

    def get_is_active(self, obj):
        now = timezone.now()
        return obj.coupon_start <= now <= obj.coupon_end

    def get_is_available(self, obj):
        return obj.available_use_times > 0 and self.get_is_active(obj)

class PillGiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = PillGift
        fields = ['id', 'discount_value', 'start_date', 'end_date', 'is_active', 'min_order_value', 'max_order_value']
        read_only_fields = ['id']

    def validate(self, data):
        # Both dates can't be null
        if data.get('start_date') is None and data.get('end_date') is None:
            raise serializers.ValidationError("At least one of start_date or end_date must be provided.")
            
        # If both dates are provided, end must be after start
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("End date must be after start date.")
                
        if data['discount_value'] < 0 or data['discount_value'] > 100:
            raise serializers.ValidationError("Discount value must be between 0 and 100.")
            
        if data['min_order_value'] < 0:
            raise serializers.ValidationError("Minimum order value cannot be negative.")
            
        if data.get('max_order_value') and data['max_order_value'] < data['min_order_value']:
            raise serializers.ValidationError("Maximum order value cannot be less than minimum order value.")
            
        return data

class PillDetailSerializer(serializers.ModelSerializer):
    items = PillItemSerializer(many=True, read_only=True)
    coupon = CouponDiscountSerializer(read_only=True)
    pilladdress = PillAddressSerializer(read_only=True)
    gift_discount = PillGiftSerializer(read_only=True)
    shipping_price = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_parent_phone = serializers.SerializerMethodField()
    status_logs = PillStatusLogSerializer(many=True, read_only=True)
    pay_requests = PayRequestSerializer(many=True, read_only=True)
    price_without_coupons_or_gifts = serializers.SerializerMethodField()
    coupon_discount = serializers.SerializerMethodField()
    gift_discount = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    shakeout_invoice_url = serializers.SerializerMethodField()
    easypay_invoice_url = serializers.SerializerMethodField()
    payment_url = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()


    class Meta:
        model = Pill
        fields = [
            'id','pill_number','tracking_number', 'user_name', 'user_username', 'user_phone','user_parent_phone' ,'items', 'status', 'status_display', 'date_added', 'paid', 'coupon', 'pilladdress', 'gift_discount',
            'price_without_coupons_or_gifts', 'coupon_discount', 'gift_discount', 'shipping_price', 'final_price', 'status_logs', 'pay_requests','shakeout_invoice_id', 'shakeout_invoice_url',
            'easypay_invoice_uid','easypay_fawry_ref', 'easypay_invoice_sequence', 'easypay_invoice_url', 'payment_gateway', 'payment_url', 'payment_status'
        ]
        read_only_fields = [
            'id','pill_number', 'tracking_number','user_name', 'user_username', 'items', 'status', 'status_display', 'date_added', 'paid', 'coupon', 'pilladdress', 'gift_discount',
            'price_without_coupons_or_gifts', 'coupon_discount', 'gift_discount', 'shipping_price', 'final_price', 'status_logs', 'pay_requests','shakeout_invoice_id', 'shakeout_invoice_url',
            'easypay_invoice_uid','easypay_fawry_ref', 'easypay_invoice_sequence', 'easypay_invoice_url', 'payment_gateway', 'payment_url', 'payment_status'
        ]

    def get_user_name(self, obj):
        return obj.user.name

    def get_user_username(self, obj):
        return obj.user.username
    
    def get_user_phone(self, obj):
        return obj.user.phone if obj.user else None
    
    def get_user_parent_phone(self, obj):
        return obj.user.parent_phone if obj.user else None
    
    def get_shipping_price(self, obj):
        return obj.shipping_price()

    def get_status_display(self, obj):
        return obj.get_status_display()
    
    def get_price_without_coupons_or_gifts(self, obj):
        return obj.price_without_coupons_or_gifts()

    def get_coupon_discount(self, obj):
        return obj.calculate_coupon_discount()

    def get_gift_discount(self, obj):
        return obj.calculate_gift_discount()

    def get_final_price(self, obj):
        return obj.final_price()
    
    def get_shakeout_invoice_url(self, obj):
        if obj.shakeout_invoice_id and obj.shakeout_invoice_ref:
            return f"https://dash.shake-out.com/invoice/{obj.shakeout_invoice_id}/{obj.shakeout_invoice_ref}"
        return None
    
    def get_easypay_invoice_url(self, obj):
        if obj.easypay_invoice_uid and obj.easypay_invoice_sequence:
            return f"https://stu.easy-adds.com/invoice/{obj.easypay_invoice_uid}/{obj.easypay_invoice_sequence}"
        return None
    
    def get_payment_url(self, obj):
        return obj.payment_url
    
    def get_payment_status(self, obj):
        return obj.payment_status
    

class PillSerializer(serializers.ModelSerializer):
    coupon = CouponDiscountSerializer(read_only=True)
    gift_discount = PillGiftSerializer(read_only=True)
    shipping_price = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_parent_phone = serializers.SerializerMethodField()
    price_without_coupons_or_gifts = serializers.SerializerMethodField()
    coupon_discount = serializers.SerializerMethodField()
    gift_discount = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()  # Keep this as SerializerMethodField
    
    # Flattened pilladdress fields
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    government = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    pay_method = serializers.SerializerMethodField()
    shakeout_invoice_url = serializers.SerializerMethodField()
    easypay_invoice_url = serializers.SerializerMethodField()
    payment_url = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()


    class Meta:
        model = Pill
        fields = [
            'id', 'pill_number', 'tracking_number', 'user_name', 'user_username', 
            'user_phone', 'user_parent_phone', 'items', 'items_count', 'status', 
            'status_display', 'date_added', 'paid', 'coupon', 'name', 'email', 
            'phone', 'address', 'government', 'city', 'pay_method', 'gift_discount',
            'price_without_coupons_or_gifts', 'coupon_discount', 'shipping_price', 
            'final_price', 'shakeout_invoice_id', 'shakeout_invoice_url',
            'easypay_invoice_uid', 'easypay_invoice_sequence', 'easypay_invoice_url',
            'payment_gateway', 'payment_url', 'payment_status'
        ]
        read_only_fields = [
            'id', 'pill_number', 'tracking_number', 'user_name', 'user_username', 
            'status', 'status_display', 'date_added', 'paid', 'coupon', 'name', 
            'email', 'phone', 'address', 'government', 'city', 'pay_method',
            'gift_discount', 'price_without_coupons_or_gifts', 'coupon_discount', 
            'shipping_price', 'final_price', 'items_count','shakeout_invoice_id', 'shakeout_invoice_url',
            'easypay_invoice_uid', 'easypay_invoice_sequence', 'easypay_invoice_url',
            'payment_gateway', 'payment_url', 'payment_status'
        ]

    def get_user_name(self, obj):
        return obj.user.name if obj.user else None

    def get_user_username(self, obj):
        return obj.user.username if obj.user else None

    def get_user_phone(self, obj):
        return obj.user.phone if obj.user else None

    def get_user_parent_phone(self, obj):
        return obj.user.parent_phone if obj.user else None

    def get_shipping_price(self, obj):
        return obj.shipping_price()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_price_without_coupons_or_gifts(self, obj):
        return obj.price_without_coupons_or_gifts()

    def get_coupon_discount(self, obj):
        return obj.calculate_coupon_discount()

    def get_gift_discount(self, obj):
        return obj.calculate_gift_discount()

    def get_final_price(self, obj):
        return obj.final_price()

    def get_items_count(self, obj):
        # Use the annotation if available, otherwise fallback to count()
        return getattr(obj, 'items_count', obj.items.count())

    # Flattened pilladdress field methods
    def get_name(self, obj):
        return obj.pilladdress.name if hasattr(obj, 'pilladdress') and obj.pilladdress else None

    def get_email(self, obj):
        return obj.pilladdress.email if hasattr(obj, 'pilladdress') and obj.pilladdress else None

    def get_phone(self, obj):
        return obj.pilladdress.phone if hasattr(obj, 'pilladdress') and obj.pilladdress else None

    def get_address(self, obj):
        return obj.pilladdress.address if hasattr(obj, 'pilladdress') and obj.pilladdress else None

    def get_government(self, obj):
        if hasattr(obj, 'pilladdress') and obj.pilladdress:
            return obj.pilladdress.get_government_display()
        return None

    def get_city(self, obj):
        return obj.pilladdress.city if hasattr(obj, 'pilladdress') and obj.pilladdress else None

    def get_pay_method(self, obj):
        return obj.pilladdress.pay_method if hasattr(obj, 'pilladdress') and obj.pilladdress else None
    
    def get_shakeout_invoice_url(self, obj):
        if obj.shakeout_invoice_id and obj.shakeout_invoice_ref:
            return f"https://dash.shake-out.com/invoice/{obj.shakeout_invoice_id}/{obj.shakeout_invoice_ref}"
        return None
    
    def get_easypay_invoice_url(self, obj):
        if obj.easypay_invoice_uid and obj.easypay_invoice_sequence:
            return f"https://stu.easy-adds.com/invoice/{obj.easypay_invoice_uid}/{obj.easypay_invoice_sequence}"
        return None
    
    def get_payment_url(self, obj):
        return obj.payment_url
    
    def get_payment_status(self, obj):
        return obj.payment_status
    


class DiscountSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = [
            'id', 'product', 'product_name', 'category', 'category_name',
            'discount', 'discount_start', 'discount_end', 'is_active'
        ]
        read_only_fields = ['is_active']

    def get_product_name(self, obj):
        return obj.product.name if obj.product else None

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_is_active(self, obj):
        return obj.is_currently_active

    def validate(self, data):
        if not data.get('product') and not data.get('category'):
            raise serializers.ValidationError("Either product or category must be set")
        if data.get('product') and data.get('category'):
            raise serializers.ValidationError("Cannot set both product and category")
        return data

class LovedProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = LovedProduct
        fields = ['id', 'product', 'product_id', 'created_at']
        read_only_fields = ['id', 'created_at']









class StockAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockAlert
        fields = ['id', 'product', 'email', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'email': {'required': False}
        }

class PriceDropAlertSerializer(serializers.ModelSerializer):
    last_price = serializers.FloatField(required=False)
    
    class Meta:
        model = PriceDropAlert
        fields = ['id', 'product', 'email', 'last_price', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'email': {'required': False}
        }

    def validate_last_price(self, value):
        if value and value <= 0:
            raise serializers.ValidationError("Price must be positive")
        return value

class SpinWheelDiscountSerializer(serializers.ModelSerializer):
    winner_count = serializers.SerializerMethodField()

    class Meta:
        model = SpinWheelDiscount
        fields = ['id', 'name', 'discount_value', 'probability', 'min_order_value', 'max_winners', 'winner_count', 'start_date', 'end_date', 'is_active']
        read_only_fields = ['id', 'winner_count']

    def validate(self, data):
        # Provide default for max_winners if not in data
        max_winners = data.get('max_winners', 100)  # Matches model default
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        probability = data.get('probability', 0.1)  # Matches model default
        min_order_value = data.get('min_order_value', 0)  # Matches model default

        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("End date must be after start date.")
        if probability < 0 or probability > 1:
            raise serializers.ValidationError("Probability must be between 0 and 1.")
        if min_order_value < 0:
            raise serializers.ValidationError("Minimum order value cannot be negative.")
        if max_winners <= 0:
            raise serializers.ValidationError("Maximum winners must be positive.")

        return data

    def get_winner_count(self, obj):
        return obj.winner_count()

class SpinWheelResultSerializer(serializers.ModelSerializer):
    coupon = CouponDiscountSerializer(read_only=True)

    class Meta:
        model = SpinWheelResult
        fields = ['id', 'user', 'spin_wheel', 'coupon', 'spin_date_time']
        read_only_fields = ['id', 'user', 'spin_date_time', 'coupon']


class SpinWheelSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpinWheelSettings
        fields = ['daily_spin_limit', 'updated_at']
        read_only_fields = ['updated_at']

    def validate_daily_spin_limit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Daily spin limit must be positive.")
        return value


class CartSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartSettings
        fields = ['max_items_in_cart', 'updated_at']
        read_only_fields = ['updated_at']

    def validate_max_items_in_cart(self, value):
        if value <= 0:
            raise serializers.ValidationError("Maximum cart items must be positive.")
        if value > 50:
            raise serializers.ValidationError("Maximum cart items cannot exceed 50.")
        return value



