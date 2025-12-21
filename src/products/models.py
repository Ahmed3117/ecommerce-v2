import random
import string
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum
from products.utils import send_whatsapp_message
from accounts.models import YEAR_CHOICES, User
from core import settings
from django.utils import timezone
from django.utils.html import format_html
import logging

logger = logging.getLogger(__name__)

GOVERNMENT_CHOICES = [
    ('1', 'Cairo'),
    ('2', 'Alexandria'),
    ('3', 'Kafr El Sheikh'),
    ('4', 'Dakahleya'),
    ('5', 'Sharkeya'),
    ('6', 'Gharbeya'),
    ('7', 'Monefeya'),
    ('8', 'Qalyubia'),
    ('9', 'Giza'),
    ('10', 'Bani-Sweif'),
    ('11', 'Fayoum'),
    ('12', 'Menya'),
    ('13', 'Assiut'),
    ('14', 'Sohag'),
    ('15', 'Qena'),
    ('16', 'Luxor'),
    ('17', 'Aswan'),
    ('18', 'Red Sea'),
    ('19', 'Behera'),
    ('20', 'Ismailia'),
    ('21', 'Suez'),
    ('22', 'Port-Said'),
    ('23', 'Damietta'),
    ('24', 'Marsa Matrouh'),
    ('25', 'Al-Wadi Al-Gadid'),
    ('26', 'North Sinai'),
    ('27', 'South Sinai'),
]

PILL_STATUS_CHOICES = [
    ('i', 'initiated'),
    ('w', 'Waiting'),
    ('p', 'Paid'),
    ('bp', 'Being Prepared'),
    ('re', 'ready for delivery'),
    ('u', 'Under Delivery'),
    ('d', 'Delivered'),
    ('r', 'Refused'),
    ('c', 'Canceled'),
]

SIZES_CHOICES = [
    ('s', 'S'),
    ('xs', 'XS'),
    ('m', 'M'),
    ('l', 'L'),
    ('xl', 'XL'),
    ('xxl', 'XXL'),
    ('xxxl', 'XXXL'),
    ('xxxxl', 'XXXXL'),
    ('xxxxxl', 'XXXXXL'),
]

PAYMENT_CHOICES = [
    ('c', 'cash'),
    ('v', 'visa'),
]

PAYMENT_GATEWAY_CHOICES = [
    ('shakeout', 'Shake-out'),
    ('easypay', 'EasyPay'),
    ('manual', 'Manual'),
]

def generate_pill_number():
    """Generate a unique 20-digit pill number."""
    while True:
        pill_number = ''.join(random.choices(string.digits, k=20))
        if not Pill.objects.filter(pill_number=pill_number).exists():
            return pill_number

def create_random_coupon():
    letters = string.ascii_lowercase
    nums = ['0', '2', '3', '4', '5', '6', '7', '8', '9']
    marks = ['@', '#', '$', '%', '&', '*']
    return '-'.join(random.choice(letters) + random.choice(nums) + random.choice(marks) for _ in range(5))

class Category(models.Model):
    product_type = [
        ('book', 'Book'),
        ('product', 'Product'),
    ]
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)  
    type = models.CharField(
        max_length=20,
        choices=product_type,
        default='product',
        help_text="Type of the product"
    )
    class Meta:
        ordering = ['-created_at']  

    def __str__(self):
        return self.name

class SubCategory(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    created_at = models.DateTimeField(default=timezone.now)  

    class Meta:
        ordering = ['-created_at']  
        verbose_name_plural = 'Sub Categories'

    def __str__(self):
        return f"{self.category.name} - {self.name}"

class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to='brands/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)  

    class Meta:
        ordering = ['-created_at']  

    def __str__(self):
        return self.name

class Subject(models.Model):
    name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name
    
class Teacher(models.Model):
    name = models.CharField(max_length=150)
    bio = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='teachers/', null=True, blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='teachers')
    facebook = models.CharField(max_length=200, null=True, blank=True)
    instagram = models.CharField(max_length=200, null=True, blank=True)
    twitter = models.CharField(max_length=200, null=True, blank=True)
    linkedin = models.CharField(max_length=200, null=True, blank=True)
    youtube = models.CharField(max_length=200, null=True, blank=True)
    whatsapp = models.CharField(max_length=200, null=True, blank=True)
    tiktok = models.CharField(max_length=200, null=True, blank=True)
    telegram = models.CharField(max_length=200, null=True, blank=True)
    website = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    product_number = models.CharField(max_length=20, null=True, blank=True)
    product_type = [
            ('book', 'Book'),
            ('product', 'Product'),
        ]
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='products')
    sub_category = models.ForeignKey(SubCategory, on_delete=models.CASCADE, null=True, blank=True, related_name='products')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True, related_name='products')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, null=True, blank=True, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, null=True, blank=True, related_name='products')
    price = models.FloatField(null=True, blank=True)
    threshold = models.PositiveIntegerField(
        default=10,
        help_text="Minimum quantity threshold for low stock alerts"
    )
    description = models.TextField(max_length=1000, null=True, blank=True)
    is_important = models.BooleanField(
        default=False,
        help_text="Mark if this product is important/special"
    )
    date_added = models.DateTimeField(auto_now_add=True)
    base_image = models.ImageField(
        upload_to='products/',
        null=True,
        blank=True,
        help_text="Main image for the product"
    )

    type = models.CharField(
        max_length=20,
        choices=product_type,
        default='product',
        help_text="Type of the product"
    )
    year = models.CharField(
        max_length=20,
        choices=YEAR_CHOICES,
        null=True,
        blank=True,
    )
    
    def get_current_discount(self):
        """Returns the best active discount (either product or category level)"""
        now = timezone.now()
        product_discount = self.discounts.filter(
            is_active=True,
            discount_start__lte=now,
            discount_end__gte=now
        ).order_by('-discount').first()

        category_discount = None
        if self.category:
            category_discount = self.category.discounts.filter(
                is_active=True,
                discount_start__lte=now,
                discount_end__gte=now
            ).order_by('-discount').first()

        if product_discount and category_discount:
            return max(product_discount, category_discount, key=lambda d: d.discount)
        return product_discount or category_discount

    def price_after_product_discount(self):
        last_product_discount = self.discounts.last()
        if last_product_discount:
            return self.price - ((last_product_discount.discount / 100) * self.price)
        return self.price

    def price_after_category_discount(self):
        if self.category:  
            last_category_discount = self.category.discounts.last()
            if last_category_discount:
                return self.price - ((last_category_discount.discount / 100) * self.price)
        return self.price

    def discounted_price(self):
        discount = self.get_current_discount()
        if discount:
            return self.price * (1 - discount.discount / 100)
        return self.price

    def has_discount(self):
        return self.get_current_discount() is not None

    def main_image(self):
        if self.base_image:
            return self.base_image  # This should return a FileField/ImageField object

        images = self.images.all()
        if images.exists():
            # Make sure this returns a FileField/ImageField object
            return random.choice(images).image

        return None  # Explicitly return None if no image is found

    def images(self):
        return self.images.all()

    def number_of_ratings(self):
        return self.ratings.count()

    def average_rating(self):
        ratings = self.ratings.all()
        if ratings.exists():
            return round(sum(rating.star_number for rating in ratings) / ratings.count(), 1)
        return 0.0

    def total_quantity(self):
        return self.availabilities.aggregate(total=Sum('quantity'))['total'] or 0

    def available_colors(self):
        """Returns a list of unique colors available for this product."""
        colors = Color.objects.filter(
            productavailability__product=self,
            productavailability__color__isnull=False
        ).distinct().values('id', 'name')
        return [{"color_id": color['id'], "color_name": color['name']} for color in colors]

    def available_sizes(self):
        return self.availabilities.filter(size__isnull=False).values_list('size', flat=True).distinct()

    def is_low_stock(self):
        return self.total_quantity() <= self.threshold
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Save first to get the ID if this is a new product
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        # Generate product_number after saving to ensure we have an ID
        if is_new and not self.product_number:
            self.product_number = f"{settings.ACTIVE_SITE_NAME}-{self.id}"
            # Update only the product_number field to avoid infinite recursion
            Product.objects.filter(pk=self.pk).update(product_number=self.product_number)

    class Meta:
        ordering = ['-date_added']
        
class SpecialProduct(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='special_products'
    )
    special_image = models.ImageField(
        upload_to='special_products/',
        null=True,
        blank=True
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Ordering priority (higher numbers come first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Show this special product"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order', '-created_at']
        verbose_name = 'Special Product'
        verbose_name_plural = 'Special Products'

    def __str__(self):
        return f"Special: {self.product.name}"
    
class BestProduct(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='best_products'
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Ordering priority (higher numbers come first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Show this product"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order', '-created_at']


    def __str__(self):
        return self.product.name

class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='product_images/')
    created_at = models.DateTimeField(default=timezone.now)  

    class Meta:
        ordering = ['-created_at']  

    def __str__(self):
        return f"Image for {self.product.name}"
class ProductDescription(models.Model):
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='descriptions'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Product Description'
        verbose_name_plural = 'Product Descriptions'

    def __str__(self):
        return f"{self.title} - {self.product.name}"

class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)
    degree = models.CharField(max_length=50)
    created_at = models.DateTimeField(default=timezone.now)  # Added

    class Meta:
        ordering = ['-created_at']  # Added

    def __str__(self):
        return self.name
class ProductAvailability(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    size = models.CharField(max_length=50, null=True, blank=True)
    color = models.ForeignKey(
        Color,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    quantity = models.PositiveIntegerField()
    native_price = models.FloatField(
        default=0.0,
        help_text="The original price the owner paid for this product batch"
    )
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['product', 'size', 'color']
        ordering = ['-date_added'] 

    def __str__(self):
        return f"{self.product.name} - {self.size} - {self.color.name if self.color else 'No Color'}"

# class ProductSales(models.Model):
#     product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
#     quantity = models.PositiveIntegerField()
#     size = models.CharField(max_length=50, null=True, blank=True)
#     color = models.ForeignKey(Color, on_delete=models.CASCADE, null=True, blank=True)
#     price_at_sale = models.FloatField()
#     date_sold = models.DateTimeField(auto_now_add=True)
#     pill = models.ForeignKey('Pill', on_delete=models.CASCADE, related_name='product_sales')

#     def __str__(self):
#         return f"{self.product.name} - {self.quantity} sold on {self.date_sold}"

class Shipping(models.Model):
    government = models.CharField(choices=GOVERNMENT_CHOICES, max_length=2)
    shipping_price = models.FloatField(default=0.0)
    

    def __str__(self):
        return f"{self.get_government_display()} - {self.shipping_price}"

    class Meta:
        ordering = ['government']  

class PillItem(models.Model):
    pill = models.ForeignKey('Pill', on_delete=models.CASCADE, null=True, blank=True, related_name='pill_items')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pill_items', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='pill_items')
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=10, choices=SIZES_CHOICES, null=True, blank=True)
    color = models.ForeignKey(Color, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(choices=PILL_STATUS_CHOICES, max_length=2, null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    # New fields for sales analysis
    native_price_at_sale = models.FloatField(null=True, blank=True)
    price_at_sale = models.FloatField(null=True, blank=True)
    date_sold = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-date_added']
        unique_together = ['user', 'product', 'size', 'color', 'status', 'pill']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['date_sold']),
            models.Index(fields=['product', 'status']),
        ]

    def save(self, *args, **kwargs):
        # Set date_sold when status changes to 'paid' or 'delivered'
        if self.status in ['p', 'd'] and not self.date_sold:
            self.date_sold = timezone.now()
            
        # Set prices if not already set
        if self.status in ['p', 'd'] and not self.price_at_sale:
            self.price_at_sale = self.product.discounted_price()
            
        if self.status in ['p', 'd'] and not self.native_price_at_sale:
            availability = self.product.availabilities.filter(
                size=self.size,
                color=self.color
            ).first()
            self.native_price_at_sale = availability.native_price if availability else 0
            
        super().save(*args, **kwargs)
     



class Pill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pills')
    items = models.ManyToManyField(PillItem, related_name='pills')
    status = models.CharField(choices=PILL_STATUS_CHOICES, max_length=2, default='i')
    date_added = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False)
    coupon = models.ForeignKey('CouponDiscount', on_delete=models.SET_NULL, null=True, blank=True, related_name='pills')
    coupon_discount = models.FloatField(default=0.0)  # Stores discount amount
    gift_discount = models.ForeignKey('PillGift', on_delete=models.SET_NULL, null=True, blank=True, related_name='pills')
    tracking_number = models.CharField(max_length=50, null=True, blank=True)
    pill_number = models.CharField(max_length=20, editable=False, unique=True, default=generate_pill_number)
    
    # Khazenly fields
    is_shipped = models.BooleanField(default=False)
    khazenly_data = models.JSONField(null=True, blank=True)
    khazenly_order_id = models.CharField(max_length=255, null=True, blank=True, help_text="Khazenly internal order ID")
    khazenly_sales_order_number = models.CharField(max_length=255, null=True, blank=True, help_text="Khazenly sales order number (KH-BOOKIFAY-xxxxx)")
    khazenly_order_number = models.CharField(max_length=255, null=True, blank=True, help_text="Order number sent to Khazenly")
    khazenly_created_at = models.DateTimeField(null=True, blank=True, help_text="When the Khazenly order was created")
    
    # Shake-out fields (replacing Fawaterak)
    shakeout_invoice_id = models.CharField(max_length=255, null=True, blank=True, help_text="Shake-out invoice ID")
    shakeout_invoice_ref = models.CharField(max_length=255, null=True, blank=True, help_text="Shake-out invoice reference")
    shakeout_data = models.JSONField(null=True, blank=True, help_text="Shake-out invoice response data")
    shakeout_created_at = models.DateTimeField(null=True, blank=True, help_text="When the Shake-out invoice was created")
    
    # EasyPay fields
    easypay_invoice_uid = models.CharField(max_length=255, null=True, blank=True, help_text="EasyPay invoice UID")
    easypay_invoice_sequence = models.CharField(max_length=255, null=True, blank=True, help_text="EasyPay invoice sequence")
    easypay_fawry_ref = models.CharField(max_length=255, null=True, blank=True, help_text="EasyPay Fawry reference")
    easypay_data = models.JSONField(null=True, blank=True, help_text="EasyPay invoice response data")
    easypay_created_at = models.DateTimeField(null=True, blank=True, help_text="When the EasyPay invoice was created")
    
    # Payment gateway tracking
    payment_gateway = models.CharField(
        max_length=20, 
        choices=PAYMENT_GATEWAY_CHOICES, 
        null=True, 
        blank=True, 
        help_text="Which payment gateway was used for this pill"
    )
    
    # Stock problem tracking fields
    has_stock_problem = models.BooleanField(
        default=False,
        help_text="Indicates if this pill has stock availability issues"
    )
    stock_problem_items = models.JSONField(
        null=True, 
        blank=True,
        help_text="Details of items with stock problems (product_id, required_qty, available_qty, etc.)"
    )
    is_resolved = models.BooleanField(
        default=False,
        help_text="Indicates if the stock problem has been resolved"
    )
    
    def save(self, *args, **kwargs):
        if not self.pill_number:
            self.pill_number = generate_pill_number()

        # Track if paid status is being changed to True
        is_newly_paid = False
        if self.pk:
            try:
                old_pill = Pill.objects.get(pk=self.pk)
                if not old_pill.paid and self.paid:
                    is_newly_paid = True
            except Pill.DoesNotExist:
                pass
        elif self.paid:
            is_newly_paid = True

        is_new = not self.pk
        old_status = None if is_new else Pill.objects.get(pk=self.pk).status

        super().save(*args, **kwargs)

        if is_new:
            PillStatusLog.objects.create(pill=self, status=self.status)
            for item in self.items.all():
                item.status = self.status
                if self.status in ['p', 'd']:
                    self._update_pill_item_prices(item)
                item.save()
            self.apply_gift_discount()
        else:
            if old_status != self.status:
                status_log, created = PillStatusLog.objects.get_or_create(
                    pill=self,
                    status=self.status
                )
                if not created:
                    status_log.changed_at = timezone.now()
                    status_log.save()

                if self.status in ['c', 'r'] and old_status == 'd':
                    self.restore_inventory()

                self.items.update(status=self.status)

                if self.status in ['p', 'd']:
                    for item in self.items.all():
                        self._update_pill_item_prices(item)
                        item.save()

                if self.status != 'd' and not self.paid:
                    self.apply_gift_discount()

                if old_status != 'd' and self.status == 'd':
                    self.process_delivery()

                if self.paid and self.status != 'p':
                    super().save(*args, **kwargs)
                    self.send_payment_notification()

        # Create Khazenly order if paid was just set to True
        if is_newly_paid:
            self._create_khazenly_order()
        
        # Check for stock problems if pill is paid and not already resolved
        if self.paid and not self.is_resolved:
            self._check_and_update_stock_problems()

    def _create_khazenly_order(self):
        """Create Khazenly order when paid becomes True"""
        try:
            # Check if order already sent to Khazenly - skip if it exists
            if self.has_khazenly_order:
                logger.info(f"Skipping Khazenly order creation for pill {self.pill_number} - order already exists")
                logger.info(f"  - Existing Khazenly Order ID: {self.khazenly_order_id}")
                logger.info(f"  - Existing Sales Order Number: {self.khazenly_sales_order_number}")
                return
            
            from services.khazenly_service import khazenly_service
            
            logger.info(f"Creating Khazenly order for pill {self.pill_number}")
            
            result = khazenly_service.create_order(self)
            
            if result['success']:
                data = result['data']
                
                # Store specific Khazenly order information and set is_shipped to True
                update_fields = {
                    'khazenly_data': data,
                    'khazenly_order_id': data.get('khazenly_order_id'),
                    'khazenly_sales_order_number': data.get('sales_order_number'),
                    'khazenly_created_at': timezone.now(),
                    'is_shipped': True  # Set is_shipped to True after successful order creation
                }
                
                # Update the model without triggering save again
                Pill.objects.filter(pk=self.pk).update(**update_fields)
                
                logger.info(f"✓ Successfully created Khazenly order for pill {self.pill_number}")
                logger.info(f"  - Khazenly Order ID: {data.get('khazenly_order_id')}")
                logger.info(f"  - Sales Order Number: {data.get('sales_order_number')}")
                logger.info(f"  - Order Number: {data.get('order_number')}")
                logger.info(f"  - is_shipped set to True")
                
            else:
                error_msg = result.get('error', 'Unknown error from Khazenly service')
                logger.error(f"✗ Failed to create Khazenly order for pill {self.pill_number}: {error_msg}")
                # Raise exception so it can be caught and displayed in admin
                raise Exception(f"Khazenly service error: {error_msg}")
                
        except Exception as e:
            logger.error(f"✗ Error creating Khazenly order for pill {self.pill_number}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Re-raise the exception so it can be caught by the admin view
            raise
    
    def _check_and_update_stock_problems(self):
        """Check for stock problems and update pill status accordingly"""
        try:
            logger.info(f"Checking stock problems for paid pill {self.pill_number}")
            
            # Use the existing check_all_items_availability method
            availability_check = self.check_all_items_availability()
            
            if not availability_check['all_available']:
                # Stock problems found
                logger.warning(f"Stock problems detected for paid pill {self.pill_number}: {availability_check['problem_items_count']} items")
                
                # Update stock problem fields without triggering save recursion
                update_fields = {
                    'has_stock_problem': True,
                    'stock_problem_items': availability_check['problem_items'],
                    'is_resolved': False
                }
                
                # Update the model without triggering save again
                Pill.objects.filter(pk=self.pk).update(**update_fields)
                
                logger.info(f"Updated pill {self.pill_number} with stock problem status")
                
            else:
                # No stock problems, ensure flags are cleared if they were set before
                if self.has_stock_problem:
                    logger.info(f"Stock problems resolved for pill {self.pill_number}")
                    
                    update_fields = {
                        'has_stock_problem': False,
                        'stock_problem_items': None,
                        'is_resolved': True
                    }
                    
                    # Update the model without triggering save again
                    Pill.objects.filter(pk=self.pk).update(**update_fields)
                    
                    logger.info(f"Cleared stock problem status for pill {self.pill_number}")
                    
        except Exception as e:
            logger.error(f"Error checking stock problems for pill {self.pill_number}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    

    @property
    def khazenly_order_number(self):
        """Get Khazenly order number from stored data"""
        if self.khazenly_data:
            return self.khazenly_data.get('orderNumber', self.pill_number)
        return None

    @property
    def has_khazenly_order(self):
        """Check if this pill has a Khazenly order"""
        return bool(self.khazenly_data)

    @property
    def khazenly_status(self):
        """Get Khazenly order status"""
        if self.has_khazenly_order:
            return "Created"
        elif self.is_shipped:
            return "Pending"
        else:
            return "Not Shipped"
    def create_fawry_payment(self):
        """Create Fawry payment invoice"""
        from services.fawaterak_service import FawaterakService
        service = FawaterakService()
        result, error = service.create_fawry_invoice(self)
        
        if result:
            self.fawaterak_invoice_key = result.get('invoice_key')
            self.fawaterak_data = result
            self.save()
            return result.get('invoice_url')
        
        logger.error(f"Failed to create Fawry payment: {error}")
        return None
    def create_fawaterak_invoice(self):
        """Create a Fawory Fawry invoice for this pill"""
        from services.fawaterak_service import FawaterakService
        
        fawaterak = FawaterakService()
        invoice_data, error = fawaterak.create_fawry_invoice(self)
        
        if invoice_data:
            self.fawaterak_invoice_key = invoice_data.get('invoice_key')
            self.fawaterak_data = invoice_data
            self.save(update_fields=['fawaterak_invoice_key', 'fawaterak_data'])
            return invoice_data.get('invoice_url')
        return None

    def check_fawaterak_payment(self):
        """Check payment status with Fawaterak"""
        if not self.fawaterak_invoice_key:
            return None, "No Fawaterak invoice associated"
            
        from services.fawaterak_service import FawaterakService
        
        fawaterak = FawaterakService()
        payment_data, error = fawaterak.check_payment_status(self.fawaterak_invoice_key)
        
        if payment_data:
            # Update payment status if needed
            if payment_data.get('payment_status') == 'paid' and not self.paid:
                self.paid = True
                self.status = 'p'  # Set to paid status
                self.save(update_fields=['paid', 'status'])
            return payment_data, None
        return None, error

    @property
    def fawaterak_payment_url(self):
        """Get Fawaterak payment URL if exists"""
        if self.fawaterak_invoice_key and self.fawaterak_data:
            return self.fawaterak_data.get('invoice_url')
        return None

    @property
    def fawaterak_payment_status(self):
        """Get Fawaterak payment status"""
        if not self.fawaterak_invoice_key:
            return "No invoice"
        if self.paid:
            return "Paid"
        return "Pending"

    def create_shakeout_invoice(self):
        """Create a Shake-out invoice for this pill"""
        from services.shakeout_service import shakeout_service
        
        result = shakeout_service.create_payment_invoice(self)
        
        if result['success']:
            data = result['data']
            self.shakeout_invoice_id = data.get('invoice_id')
            self.shakeout_invoice_ref = data.get('invoice_ref')
            self.shakeout_data = data
            self.shakeout_created_at = timezone.now()
            self.payment_gateway = 'shakeout'
            self.save(update_fields=['shakeout_invoice_id', 'shakeout_invoice_ref', 'shakeout_data', 'shakeout_created_at', 'payment_gateway'])
            # Fix: Use 'url' instead of 'payment_url' to match Shake-out API response
            return data.get('url')
        return None

    def create_easypay_invoice(self):
        """Create an EasyPay invoice for this pill"""
        from services.easypay_service import easypay_service
        
        result = easypay_service.create_payment_invoice(self)
        
        if result['success']:
            data = result['data']
            self.easypay_invoice_uid = data.get('invoice_uid')
            self.easypay_invoice_sequence = data.get('invoice_sequence')
            self.easypay_data = data
            self.easypay_created_at = timezone.now()
            self.payment_gateway = 'easypay'
            self.save(update_fields=['easypay_invoice_uid', 'easypay_invoice_sequence', 'easypay_data', 'easypay_created_at', 'payment_gateway'])
            return data.get('payment_url')
        return None

    def create_payment_invoice(self):
        """Create a payment invoice using the active payment gateway"""
        from django.conf import settings
        
        active_method = getattr(settings, 'ACTIVE_PAYMENT_METHOD', 'shakeout').lower()
        
        if active_method == 'easypay':
            return self.create_easypay_invoice()
        else:  # Default to shakeout
            return self.create_shakeout_invoice()

    def check_shakeout_payment(self):
        """Check payment status with Shake-out"""
        if not self.shakeout_invoice_id:
            return None, "No Shake-out invoice associated"
            
        from services.shakeout_service import shakeout_service
        
        payment_data = shakeout_service.check_payment_status(self.shakeout_invoice_id)
        
        if payment_data['success']:
            # Payment status updates will come via webhooks
            return payment_data, None
        return None, payment_data.get('error')

    def check_easypay_payment(self):
        """Check payment status with EasyPay"""
        if not self.easypay_invoice_uid or not self.easypay_invoice_sequence:
            return None, "No EasyPay invoice associated"
            
        from services.easypay_service import easypay_service
        
        payment_data = easypay_service.check_payment_status(self.easypay_invoice_uid, self.easypay_invoice_sequence)
        
        if payment_data['success']:
            # Update payment status if needed
            invoice_data = payment_data['data']['invoice_data']
            payment_status = invoice_data.get('payment_status', 'unknown')
            if payment_status.lower() == 'paid' and not self.paid:
                self.paid = True
                self.status = 'p'  # Set to paid status
                self.save(update_fields=['paid', 'status'])
            return payment_data, None
        return None, payment_data.get('error')

    def check_payment_status(self):
        """Check payment status using the appropriate gateway"""
        if self.payment_gateway == 'easypay':
            return self.check_easypay_payment()
        elif self.payment_gateway == 'shakeout':
            return self.check_shakeout_payment()
        else:
            # Try both if gateway is not set
            if self.easypay_invoice_uid:
                return self.check_easypay_payment()
            elif self.shakeout_invoice_id:
                return self.check_shakeout_payment()
            return None, "No payment invoice found"

    @property
    def shakeout_payment_url(self):
        """Get Shake-out payment URL if exists"""
        if self.shakeout_data:
            # Fix: Use 'url' instead of 'payment_url' to match Shake-out API response
            return self.shakeout_data.get('url')
        return None

    @property
    def shakeout_payment_status(self):
        """Get Shake-out payment status"""
        if not self.shakeout_invoice_id:
            return "No invoice"
        if self.paid:
            return "Paid"
        return "Pending"

    @property
    def easypay_payment_url(self):
        """Get EasyPay payment URL if exists"""
        if self.easypay_data:
            return self.easypay_data.get('payment_url')
        return None

    @property
    def easypay_payment_status(self):
        """Get EasyPay payment status"""
        if not self.easypay_invoice_uid:
            return "No invoice"
        if self.paid:
            return "Paid"
        return "Pending"

    @property
    def payment_url(self):
        """Get payment URL for the active gateway"""
        if self.payment_gateway == 'easypay':
            return self.easypay_payment_url
        elif self.payment_gateway == 'shakeout':
            return self.shakeout_payment_url
        else:
            # Try both if gateway is not set
            return self.easypay_payment_url or self.shakeout_payment_url

    @property
    def payment_status(self):
        """Get payment status for the active gateway"""
        if self.payment_gateway == 'easypay':
            return self.easypay_payment_status
        elif self.payment_gateway == 'shakeout':
            return self.shakeout_payment_status
        else:
            # Return generic status
            if self.paid:
                return "Paid"
            elif self.easypay_invoice_uid or self.shakeout_invoice_id:
                return "Pending"
            else:
                return "No invoice"

    def is_shakeout_invoice_expired(self):
        """
        Check if the current Shake-out invoice is expired or invalid
        """
        from datetime import timedelta
        
        if not self.shakeout_invoice_id or not self.shakeout_created_at:
            return True  # No invoice or creation date means we can create a new one
        
        # Check if invoice is older than 30 days (Shake-out default expiry)
        expiry_days = 30
        expiry_date = self.shakeout_created_at + timedelta(days=expiry_days)
        
        if timezone.now() > expiry_date:
            logger.info(f"Shake-out invoice {self.shakeout_invoice_id} for pill {self.pill_number} expired on {expiry_date}")
            return True
        
        # Check if invoice status indicates it's no longer valid
        if self.shakeout_data:
            # Check webhook history for failure/expiry status
            webhooks = self.shakeout_data.get('webhooks', [])
            for webhook in reversed(webhooks):  # Check most recent first
                webhook_status = webhook.get('invoice_status', '').lower()
                if webhook_status in ['expired', 'cancelled', 'failed']:
                    logger.info(f"Shake-out invoice {self.shakeout_invoice_id} for pill {self.pill_number} has status: {webhook_status}")
                    return True
        
        return False

    def is_easypay_invoice_expired(self):
        """
        Check if the current EasyPay invoice is expired or invalid
        """
        from datetime import timedelta
        
        if not self.easypay_invoice_uid or not self.easypay_created_at:
            return True  # No invoice or creation date means we can create a new one
        
        # Check if invoice is older than 2 days (default payment expiry from settings)
        from django.conf import settings
        expiry_ms = getattr(settings, 'EASYPAY_PAYMENT_EXPIRY', 172800000)  # 48 hours in milliseconds
        expiry_hours = expiry_ms / (1000 * 60 * 60)  # Convert to hours
        expiry_date = self.easypay_created_at + timedelta(hours=expiry_hours)
        
        if timezone.now() > expiry_date:
            logger.info(f"EasyPay invoice {self.easypay_invoice_uid} for pill {self.pill_number} expired on {expiry_date}")
            return True
        
        # Check if invoice status indicates it's no longer valid
        if self.easypay_data and 'invoice_details' in self.easypay_data:
            payment_status = self.easypay_data['invoice_details'].get('payment_status', '').lower()
            if payment_status in ['expired', 'cancelled', 'failed']:
                logger.info(f"EasyPay invoice {self.easypay_invoice_uid} for pill {self.pill_number} has status: {payment_status}")
                return True
        
        return False

    def is_payment_invoice_expired(self):
        """Check if the current payment invoice is expired"""
        if self.payment_gateway == 'easypay':
            return self.is_easypay_invoice_expired()
        elif self.payment_gateway == 'shakeout':
            return self.is_shakeout_invoice_expired()
        else:
            # Check both if gateway is not set
            return (self.is_easypay_invoice_expired() if self.easypay_invoice_uid 
                   else True) and (self.is_shakeout_invoice_expired() if self.shakeout_invoice_id 
                   else True)

    def _update_pill_item_prices(self, item):
        """Helper method to update prices and sale date on a pill item"""
        if item.status in ['p', 'd']:
            if not item.date_sold:
                item.date_sold = timezone.now()

            if not item.price_at_sale:
                item.price_at_sale = item.product.discounted_price()

            if not item.native_price_at_sale:
                availability = item.product.availabilities.filter(
                    size=item.size,
                    color=item.color
                ).first()
                item.native_price_at_sale = availability.native_price if availability else 0

    def restore_inventory(self):
        """Restore inventory quantities for all items in the pill"""
        with transaction.atomic():
            for item in self.items.all():
                try:
                    availability = ProductAvailability.objects.select_for_update().get(
                        product=item.product,
                        size=item.size,
                        color=item.color
                    )
                    availability.quantity += item.quantity
                    availability.save()
                except ProductAvailability.DoesNotExist:
                    continue

    def process_delivery(self):
        """Process items when pill is marked as delivered"""
        with transaction.atomic():
            for item in self.items.all():
                try:
                    color = item.color if item.color else None
                    availability = ProductAvailability.objects.select_for_update().get(
                        product=item.product,
                        size=item.size,
                        color=color
                    )
                    if availability.quantity < item.quantity:
                        raise ValidationError(
                            f"Not enough inventory for {item.product.name} "
                            f"(Size: {item.size}, Color: {item.color.name if item.color else 'N/A'}). "
                            f"Required: {item.quantity}, Available: {availability.quantity}"
                        )
                    availability.quantity -= item.quantity
                    availability.save()
                    self._update_pill_item_prices(item)
                    item.save()
                except ProductAvailability.DoesNotExist:
                    raise ValidationError(
                        f"Inventory record for {item.product.name} "
                        f"(Size: {item.size}, Color: {item.color.name if item.color else 'N/A'}) not found."
                    )

    def send_payment_notification(self):
        """Send payment confirmation if phone exists"""
        if hasattr(self, 'pilladdress') and self.pilladdress.phone:
            prepare_whatsapp_message(self.pilladdress.phone, self)

    def price_without_coupons_or_gifts(self):
        return sum(item.product.discounted_price() * item.quantity for item in self.items.all())

    def calculate_coupon_discount(self):
        if self.coupon:
            now = timezone.now()
            if self.coupon.coupon_start <= now <= self.coupon.coupon_end:
                return self.price_without_coupons_or_gifts() * (self.coupon.discount_value / 100)
        return 0.0

    def calculate_gift_discount(self):
        if self.gift_discount and self.gift_discount.is_available(self.price_without_coupons_or_gifts()):
            return self.price_without_coupons_or_gifts() * (self.gift_discount.discount_value / 100)
        return 0.0

    def has_free_shipping_offer(self):
        """Check if any items in this pill qualify for free shipping offers."""
        # Get all active free shipping offers
        active_offers = FreeShippingOffer.get_active_offers()
        
        if not active_offers.exists():
            return False
        
        # Check if any item in the pill qualifies for any active offer
        for pill_item in self.items.all():
            product = pill_item.product
            for offer in active_offers:
                if offer.applies_to_product(product):
                    return True
        
        return False

    def get_applicable_free_shipping_offers(self):
        """Get all free shipping offers that apply to items in this pill."""
        active_offers = FreeShippingOffer.get_active_offers()
        applicable_offers = []
        
        for pill_item in self.items.all():
            product = pill_item.product
            for offer in active_offers:
                if offer.applies_to_product(product) and offer not in applicable_offers:
                    applicable_offers.append(offer)
        
        return applicable_offers

    def shipping_price(self):
        # Check if free shipping applies
        if self.has_free_shipping_offer():
            # Still add over tax amount even with free shipping
            return self.calculate_over_tax_price()
        
        if hasattr(self, 'pilladdress'):
            try:
                shipping = Shipping.objects.filter(government=self.pilladdress.government).first()
                base_shipping = shipping.shipping_price if shipping else 0.0
                # Add over tax amount to shipping
                return base_shipping + self.calculate_over_tax_price()
            except:
                return 0.0
        return 0.0

    def calculate_over_tax_price(self):
        """
        Calculate the over-tax amount for items exceeding the maximum threshold.
        Returns the total tax amount to be added to shipping.
        """
        # Get the active tax configuration
        tax_config = OverTaxConfig.get_active_config()
        if not tax_config:
            return 0.0
        
        # Count total quantity of items in the pill
        # total_quantity = sum(item.quantity for item in self.items.all())
        total_quantity = self.items.count()
        
        # Calculate items that exceed the threshold
        items_over_threshold = max(0, total_quantity - tax_config.max_products_without_tax)
        
        # Calculate tax amount
        tax_amount = items_over_threshold * float(tax_config.tax_amount_per_item)
        
        return tax_amount

    def final_price(self):
        base_price = self.price_without_coupons_or_gifts()
        gift_discount = self.calculate_gift_discount()
        coupon_discount = self.calculate_coupon_discount()
        return max(0, base_price - gift_discount - coupon_discount) + self.shipping_price()

    def apply_gift_discount(self):
        """Apply the best active PillGift discount based on total price."""
        if self.paid or self.status == 'd':
            self.gift_discount = None
            self.save()
            return None

        total = self.price_without_coupons_or_gifts()
        if total <= 0:
            self.gift_discount = None
            self.save()
            return None

        applicable_gifts = PillGift.objects.filter(
            is_active=True,
            min_order_value__lte=total
        ).filter(
            models.Q(max_order_value__isnull=True) | models.Q(max_order_value__gte=total)
        ).filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=timezone.now())
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now())
        ).order_by('-discount_value', '-id')

        if self.gift_discount and not self.gift_discount.is_available(total):
            self.gift_discount = None

        gift = applicable_gifts.first()
        if gift:
            self.gift_discount = gift
            self.save()
            return gift
        if not self.gift_discount:
            self.save()
        return None

    def check_item_availability(self, pill_item):
        """
        Check if a specific pill item is available in stock
        Returns: dict with availability info
        """
        try:
            availability = pill_item.product.availabilities.filter(
                size=pill_item.size,
                color=pill_item.color
            ).first()
            
            if not availability:
                return {
                    'available': False,
                    'reason': 'no_availability_record',
                    'available_quantity': 0,
                    'required_quantity': pill_item.quantity
                }
            
            if availability.quantity <= 0:
                return {
                    'available': False,
                    'reason': 'out_of_stock',
                    'available_quantity': 0,
                    'required_quantity': pill_item.quantity
                }
            
            if availability.quantity < pill_item.quantity:
                return {
                    'available': False,
                    'reason': 'insufficient_quantity',
                    'available_quantity': availability.quantity,
                    'required_quantity': pill_item.quantity
                }
            
            return {
                'available': True,
                'available_quantity': availability.quantity,
                'required_quantity': pill_item.quantity
            }
            
        except Exception as e:
            return {
                'available': False,
                'reason': 'error',
                'error': str(e),
                'available_quantity': 0,
                'required_quantity': pill_item.quantity
            }

    def check_all_items_availability(self):
        """
        Check availability for all items in this pill
        Returns: dict with overall status and problem items details
        """
        problem_items = []
        all_available = True
        
        for pill_item in self.items.all():
            availability_check = self.check_item_availability(pill_item)
            
            if not availability_check['available']:
                all_available = False
                problem_items.append({
                    'pill_item_id': pill_item.id,
                    'product_id': pill_item.product.id,
                    'product_name': pill_item.product.name,
                    'size': pill_item.size,
                    'color': pill_item.color.name if pill_item.color else None,
                    'required_quantity': availability_check['required_quantity'],
                    'available_quantity': availability_check['available_quantity'],
                    'reason': availability_check['reason'],
                    'error': availability_check.get('error')
                })
        
        return {
            'all_available': all_available,
            'problem_items': problem_items,
            'total_items': self.items.count(),
            'problem_items_count': len(problem_items)
        }

    def update_stock_problem_status(self):
        """
        Update the stock problem status based on current availability
        """
        availability_check = self.check_all_items_availability()
        
        if not availability_check['all_available']:
            self.has_stock_problem = True
            self.stock_problem_items = availability_check['problem_items']
            self.is_resolved = False
        else:
            # If previously had problems but now all items are available
            if self.has_stock_problem:
                self.has_stock_problem = False
                self.stock_problem_items = None
                self.is_resolved = True
        
        # Save without triggering the full save method to avoid recursion
        Pill.objects.filter(pk=self.pk).update(
            has_stock_problem=self.has_stock_problem,
            stock_problem_items=self.stock_problem_items,
            is_resolved=self.is_resolved
        )
        
        return availability_check

    class Meta:
        verbose_name_plural = 'Bills'
        ordering = ['-date_added']
        indexes = [
            # Essential indexes for your API performance
            models.Index(fields=['-date_added']),  # Primary ordering
            models.Index(fields=['status']),       # Status filtering
            models.Index(fields=['paid']),         # Payment status
            models.Index(fields=['pill_number']),  # Unique lookups
            models.Index(fields=['user_id']),      # User filtering
            models.Index(fields=['date_added', 'status']),  # Composite for common filters
            models.Index(fields=['date_added', 'paid']),    # Date + payment status
        ]

    def __str__(self):
        return f"Pill ID: {self.id} - Status: {self.get_status_display()} - Date: {self.date_added}"

class PillAddress(models.Model):
    pill = models.OneToOneField(Pill, on_delete=models.CASCADE, related_name='pilladdress')
    name = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    government = models.CharField(choices=GOVERNMENT_CHOICES, max_length=2, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    pay_method = models.CharField(choices=PAYMENT_CHOICES, max_length=2, default="c")
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.address}"

class PillStatusLog(models.Model):
    pill = models.ForeignKey(Pill, on_delete=models.CASCADE, related_name='status_logs')
    status = models.CharField(choices=PILL_STATUS_CHOICES, max_length=2)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at'] 

    def __str__(self):
        return f"{self.pill.id} - {self.get_status_display()} at {self.changed_at}"
    
class CouponDiscount(models.Model):
    coupon = models.CharField(max_length=100, blank=True, null=True, editable=False)
    discount_value = models.FloatField(null=True, blank=True)
    coupon_start = models.DateTimeField(null=True, blank=True)
    coupon_end = models.DateTimeField(null=True, blank=True)
    available_use_times = models.PositiveIntegerField(default=1)
    is_wheel_coupon = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    min_order_value = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.coupon:
            self.coupon = create_random_coupon()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.coupon

    class Meta:
        ordering = ['-created_at']

class Rating(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    star_number = models.IntegerField()
    review = models.CharField(max_length=300, default="No review comment")
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.star_number} stars for {self.product.name} by {self.user.username}"

    def star_ranges(self):
        return range(int(self.star_number)), range(5 - int(self.star_number))

    class Meta:
        ordering = ['-date_added'] 

class Discount(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='discounts')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='discounts')
    discount = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    discount_start = models.DateTimeField()
    discount_end = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        target = f"Product: {self.product.name}" if self.product else f"Category: {self.category.name}"
        return f"{self.discount}% discount on {target}"

    def clean(self):
        if not self.product and not self.category:
            raise ValidationError("Either product or category must be set")
        if self.product and self.category:
            raise ValidationError("Cannot set both product and category")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_currently_active(self):
        now = timezone.now()
        return self.is_active and self.discount_start <= now <= self.discount_end

class PayRequest(models.Model):
    pill = models.ForeignKey('Pill', on_delete=models.CASCADE, related_name='pay_requests')
    image = models.ImageField(upload_to='pay_requests/')
    date = models.DateTimeField(auto_now_add=True)
    is_applied = models.BooleanField(default=False)

    def __str__(self):
        return f"PayRequest for Pill {self.pill.id} - Applied: {self.is_applied}"
    class Meta:
        ordering = ['-date'] 

class LovedProduct(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loved_products',
        null=True,
        blank=True
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'product']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} loved by {self.user.username if self.user else 'anonymous'}"
























class StockAlert(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_notified = models.BooleanField(default=False)

    class Meta:
        unique_together = [
            ['product', 'user'],
            ['product', 'email']
        ]
        ordering = ['-created_at']

class PriceDropAlert(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    last_price = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_notified = models.BooleanField(default=False)

    class Meta:
        unique_together = [
            ['product', 'user'],
            ['product', 'email']
        ]
        ordering = ['-created_at'] 

class SpinWheelDiscount(models.Model):
    name = models.CharField(max_length=100)
    discount_value = models.FloatField(
        default=0.0,
        help_text="Discount value for the coupon created upon winning"
    )
    probability = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Probability of winning (0 to 1)"
    )
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    min_order_value = models.FloatField(
        default=0,
        help_text="Minimum order value to claim the prize"
    )
    max_winners = models.PositiveIntegerField(
        default=100,
        help_text="Maximum number of users who can win this discount"
    )
    created_at = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return f"{self.name} (Winners: {self.winner_count()}/{self.max_winners})"

    class Meta:
        ordering = ['-created_at']
    def is_available(self):
        now = timezone.now()
        return (
            self.is_active and
            self.start_date <= now <= self.end_date and
            self.winner_count() < self.max_winners
        )

    def winner_count(self):
        return SpinWheelResult.objects.filter(spin_wheel=self, coupon__isnull=False).count()

class SpinWheelResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    spin_wheel = models.ForeignKey(SpinWheelDiscount, on_delete=models.CASCADE)
    coupon = models.ForeignKey(CouponDiscount, null=True, blank=True, on_delete=models.SET_NULL)
    spin_date_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'spin_wheel', 'spin_date_time']
        ordering = ['-spin_date_time']

    def __str__(self):
        return f"{self.user.username} spun {self.spin_wheel.name} on {self.spin_date_time}"

class SpinWheelSettings(models.Model):
    daily_spin_limit = models.PositiveIntegerField(
        default=1,
        help_text="Maximum spins per user per day"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Spin Wheel Settings"
        verbose_name_plural = "Spin Wheel Settings"

    def __str__(self):
        return f"Daily Spin Limit: {self.daily_spin_limit}"

    @classmethod
    def get_settings(cls):
        return cls.objects.first() or cls.objects.create()


class CartSettings(models.Model):
    max_items_in_cart = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Maximum number of different products that can be added to cart"
    )
    max_quantity_per_item = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Maximum quantity allowed for a single item in the cart"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart Settings"
        verbose_name_plural = "Cart Settings"

    def __str__(self):
        return f"Max Cart Items: {self.max_items_in_cart}, Max Qty Per Item: {self.max_quantity_per_item}"

    @classmethod
    def get_settings(cls):
        return cls.objects.first() or cls.objects.create()


class PillGift(models.Model):
    discount_value = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Discount percentage (0-100)"
    )
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start date the gift becomes available (null means always available until end_date)"
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date of the gift (null means available indefinitely from start_date)"
    )
    is_active = models.BooleanField(default=True)
    min_order_value = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Minimum order value to apply the gift"
    )
    max_order_value = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Maximum order value to apply the gift (optional)"
    )
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        verbose_name = "Pill Gift"
        verbose_name_plural = "Pill Gifts"
        ordering = ['-created_at']

    def __str__(self):
        start_str = self.start_date.strftime("%Y-%m-%d") if self.start_date else "Any"
        end_str = self.end_date.strftime("%Y-%m-%d") if self.end_date else "Forever"
        return f"{self.discount_value}% Gift ({start_str} to {end_str})"

    def is_available(self, order_value):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        if order_value < self.min_order_value:
            return False
        if self.max_order_value and order_value > self.max_order_value:
            return False
        return True


class KhazenlyWebhookLog(models.Model):
    """
    Model to store all incoming requests to Khazenly webhook endpoints
    All fields are nullable to prevent errors during logging
    """
    # Request metadata
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    method = models.CharField(max_length=10, null=True, blank=True)
    url_path = models.TextField(null=True, blank=True)
    query_params = models.TextField(null=True, blank=True)
    
    # Request source information
    remote_addr = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    referer = models.TextField(null=True, blank=True)
    x_forwarded_for = models.TextField(null=True, blank=True)
    x_real_ip = models.TextField(null=True, blank=True)
    
    # Request content
    headers = models.JSONField(null=True, blank=True, default=dict)
    body = models.TextField(null=True, blank=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    content_length = models.IntegerField(null=True, blank=True)
    
    # Response information
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(null=True, blank=True)
    response_headers = models.JSONField(null=True, blank=True, default=dict)
    processing_time_ms = models.IntegerField(null=True, blank=True)
    
    # Processing details
    pill_found = models.BooleanField(null=True, blank=True)
    pill_number = models.CharField(max_length=100, null=True, blank=True)
    status_updated = models.BooleanField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    hmac_verified = models.BooleanField(null=True, blank=True)
    
    # Webhook payload fields for quick access
    webhook_status = models.CharField(max_length=100, null=True, blank=True)
    order_reference = models.CharField(max_length=100, null=True, blank=True)
    merchant_reference = models.CharField(max_length=100, null=True, blank=True)
    order_supplier_id = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        verbose_name = "Khazenly Webhook Log"
        verbose_name_plural = "Khazenly Webhook Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['response_status']),
            models.Index(fields=['pill_number']),
            models.Index(fields=['order_reference']),
            models.Index(fields=['merchant_reference']),
            models.Index(fields=['remote_addr']),
        ]

    def __str__(self):
        status = f"HTTP {self.response_status}" if self.response_status else "Unknown"
        method = self.method or "Unknown"
        timestamp = self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "Unknown"
        return f"{method} {status} - {timestamp}"

    def save(self, *args, **kwargs):
        """Override save to handle any potential errors gracefully"""
        try:
            super().save(*args, **kwargs)
        except Exception as e:
            # Log the error but don't raise it to prevent webhook failures
            logger.error(f"Failed to save KhazenlyWebhookLog: {e}")

    @property
    def is_successful(self):
        """Returns True if the response was successful (2xx status)"""
        return self.response_status and 200 <= self.response_status < 300

    @property
    def duration_display(self):
        """Returns human-readable processing time"""
        if self.processing_time_ms is None:
            return "Unknown"
        if self.processing_time_ms < 1000:
            return f"{self.processing_time_ms}ms"
        else:
            return f"{self.processing_time_ms / 1000:.2f}s"

    @classmethod
    def log_request(cls, request, response_data=None, processing_time_ms=None, **extra_data):
        """
        Utility method to safely log webhook requests
        All parameters are optional to prevent errors
        """
        try:
            # Extract headers safely
            headers = {}
            try:
                headers = dict(request.headers)
            except Exception:
                headers = {}

            # Extract body safely
            body = None
            try:
                if hasattr(request, 'body'):
                    body = request.body.decode('utf-8') if request.body else None
            except Exception:
                body = str(request.body) if hasattr(request, 'body') else None

            # Extract IP address safely
            remote_addr = None
            try:
                remote_addr = request.META.get('REMOTE_ADDR')
            except Exception:
                pass

            # Extract other metadata safely
            user_agent = None
            try:
                user_agent = request.META.get('HTTP_USER_AGENT')
            except Exception:
                pass

            x_forwarded_for = None
            try:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            except Exception:
                pass

            x_real_ip = None
            try:
                x_real_ip = request.META.get('HTTP_X_REAL_IP')
            except Exception:
                pass

            # Create log entry with all nullable fields
            log_entry = cls(
                method=getattr(request, 'method', None),
                url_path=getattr(request, 'path', None),
                query_params=getattr(request, 'META', {}).get('QUERY_STRING', None),
                remote_addr=remote_addr,
                user_agent=user_agent,
                x_forwarded_for=x_forwarded_for,
                x_real_ip=x_real_ip,
                headers=headers,
                body=body,
                content_type=request.META.get('CONTENT_TYPE', None) if hasattr(request, 'META') else None,
                processing_time_ms=processing_time_ms,
                **extra_data
            )

            # Add response data if provided
            if response_data:
                if hasattr(response_data, 'status_code'):
                    log_entry.response_status = response_data.status_code
                if hasattr(response_data, 'content'):
                    try:
                        log_entry.response_body = response_data.content.decode('utf-8')
                    except Exception:
                        log_entry.response_body = str(response_data.content)

            log_entry.save()
            return log_entry

        except Exception as e:
            # Log the error but don't raise it
            logger.error(f"Failed to create KhazenlyWebhookLog: {e}")
            return None


class OverTaxConfig(models.Model):
    """
    Configuration model for over-tax calculation.
    Defines the tax amount and maximum number of products before tax applies.
    """
    max_products_without_tax = models.PositiveIntegerField(
        default=0,
        help_text="Maximum number of products that won't be taxed. Tax applies to products beyond this number."
    )
    tax_amount_per_item = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Tax amount to apply per item that exceeds the maximum threshold."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this tax configuration is currently active."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Over Tax Configuration"
        verbose_name_plural = "Over Tax Configurations"
        ordering = ['-created_at']

    def __str__(self):
        return f"Tax {self.tax_amount_per_item} EGP per item after {self.max_products_without_tax} products"

    @classmethod
    def get_active_config(cls):
        """Get the currently active tax configuration."""
        return cls.objects.filter(is_active=True).first()

    def save(self, *args, **kwargs):
        # Ensure only one active configuration exists
        if self.is_active:
            OverTaxConfig.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)


class FreeShippingOffer(models.Model):
    """
    Model for managing free shipping offers on products based on category, subcategory, brand, subject, or teacher.
    """
    TARGET_TYPE_CHOICES = [
        ('category', 'Category'),
        ('subcategory', 'SubCategory'),
        ('brand', 'Brand'),
        ('subject', 'Subject'),
        ('teacher', 'Teacher'),
    ]
    
    description = models.CharField(
        max_length=500,
        help_text="Description of the free shipping offer"
    )
    target_type = models.CharField(
        max_length=20,
        choices=TARGET_TYPE_CHOICES,
        help_text="Type of target for the free shipping offer"
    )
    
    # Foreign key fields for different target types
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='free_shipping_offers',
        help_text="Category to apply free shipping to"
    )
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='free_shipping_offers',
        help_text="SubCategory to apply free shipping to"
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='free_shipping_offers',
        help_text="Brand to apply free shipping to"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='free_shipping_offers',
        help_text="Subject to apply free shipping to"
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='free_shipping_offers',
        help_text="Teacher to apply free shipping to"
    )
    
    start_date = models.DateTimeField(
        help_text="Start date and time for the free shipping offer"
    )
    end_date = models.DateTimeField(
        help_text="End date and time for the free shipping offer"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this free shipping offer is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Free Shipping Offer"
        verbose_name_plural = "Free Shipping Offers"
        ordering = ['-created_at']

    def __str__(self):
        target_name = self.get_target_name()
        return f"Free Shipping: {self.description} ({self.target_type}: {target_name})"

    def clean(self):
        """Validate that exactly one target field is set based on target_type."""
        from django.core.exceptions import ValidationError
        
        # Check that the correct field is set based on target_type
        target_fields = {
            'category': self.category,
            'subcategory': self.subcategory,
            'brand': self.brand,
            'subject': self.subject,
            'teacher': self.teacher,
        }
        
        # Ensure the selected target type has a corresponding value
        if not target_fields.get(self.target_type):
            raise ValidationError(f"You must select a {self.target_type} for this offer.")
        
        # Ensure other target fields are None
        for field_name, field_value in target_fields.items():
            if field_name != self.target_type and field_value is not None:
                raise ValidationError(f"Only {self.target_type} should be selected, but {field_name} is also set.")
        
        # Validate date range
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_target_name(self):
        """Get the name of the target object."""
        if self.target_type == 'category' and self.category:
            return self.category.name
        elif self.target_type == 'subcategory' and self.subcategory:
            return self.subcategory.name
        elif self.target_type == 'brand' and self.brand:
            return self.brand.name
        elif self.target_type == 'subject' and self.subject:
            return self.subject.name
        elif self.target_type == 'teacher' and self.teacher:
            return self.teacher.name
        return "Unknown"

    @property
    def is_currently_active(self):
        """Check if the offer is currently active based on dates and active status."""
        if not self.is_active:
            return False
        
        now = timezone.now()
        return self.start_date <= now <= self.end_date

    def applies_to_product(self, product):
        """Check if this free shipping offer applies to a given product."""
        if not self.is_currently_active:
            return False
        
        if self.target_type == 'category':
            return product.category == self.category
        elif self.target_type == 'subcategory':
            return product.sub_category == self.subcategory
        elif self.target_type == 'brand':
            return product.brand == self.brand
        elif self.target_type == 'subject':
            return product.subject == self.subject
        elif self.target_type == 'teacher':
            return product.teacher == self.teacher
        
        return False

    @classmethod
    def get_active_offers(cls):
        """Get all currently active free shipping offers."""
        now = timezone.now()
        return cls.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        )


def prepare_whatsapp_message(phone_number, pill):
    print(f"Preparing WhatsApp message for phone number: {phone_number}")
    message = (
        f"مرحباً {pill.user.username}،\n\n"
        f"تم استلام طلبك بنجاح.\n\n"
        f"رقم الطلب: {pill.pill_number}\n"
    )
    send_whatsapp_message(
        phone_number=phone_number,
        message=message
    )