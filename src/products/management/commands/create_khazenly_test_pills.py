"""
Management command to create test pills for Khazenly integration testing.
These pills use the same product data from failed orders but with test user info.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User
from products.models import (
    Pill, PillItem, PillAddress, Product, Color, 
    GOVERNMENT_CHOICES
)


class Command(BaseCommand):
    help = 'Create test pills for Khazenly integration testing with sanitized test user data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be created without actually creating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Test data based on the failed pills - using same addresses/governments
        # These test different government codes that were causing "wrong code" errors
        test_orders = [
            {
                'government': '8',  # Qalyubia
                'city': 'العبور',
                'address': 'الحى التاني شارع الشعراوي فيلا 81',
                'quantity': 1,
            },
            {
                'government': '4',  # Dakahleya
                'city': 'المنزلة',
                'address': 'مكتبة هانى الفروسات وسط البلد',
                'quantity': 1,
            },
            {
                'government': '19',  # Behera
                'city': 'بدر',
                'address': 'البحيره مركز بدر النجاح',
                'quantity': 1,
            },
            {
                'government': '20',  # Ismailia
                'city': 'الإسماعيلية',
                'address': 'الاسماعيليه مدينه المستقبل مساكن التعاونيات بجوار مطعم ابو هانى',
                'quantity': 1,
            },
            {
                'government': '19',  # Behera (again with different city)
                'city': 'أبو المطامير',
                'address': 'الثامنه بذور (محطه ٢)، خلف مدرسه الثامنه بذور الثانويه المشتركه',
                'quantity': 5,
            },
            {
                'government': '3',  # Kafr El Sheikh
                'city': 'الحامول',
                'address': 'محافظه كفر الشيخ مركز الحامول شركه الدلتا للسكر بجوار بنزينه مصنع السكر',
                'quantity': 1,
            },
            {
                'government': '15',  # Qena
                'city': 'نقادة',
                'address': 'قنا نقادة قريةكوم بلال بجوار محطة بنزين كوم بلال',
                'quantity': 7,
            },
            {
                'government': '2',  # Alexandria
                'city': 'العطارين',
                'address': '4_شارع صلاح الدين _العطارين فوق مطعم الصعيدي الدور التاسع الباب الحديد',
                'quantity': 1,
            },
            {
                'government': '7',  # Monefeya
                'city': 'منوف',
                'address': 'قريه منشأة سلطان',
                'quantity': 1,
            },
        ]

        self.stdout.write(self.style.NOTICE(f"\n{'='*60}"))
        self.stdout.write(self.style.NOTICE("Creating Test Pills for Khazenly Integration"))
        self.stdout.write(self.style.NOTICE(f"{'='*60}\n"))

        # Get or create a test user
        test_user, user_created = User.objects.get_or_create(
            username='khazenly_test_user',
            defaults={
                'name': 'test test test',
                'phone': '01000000000',
                'phone2': '01000000001',
                'parent_phone': '01000000002',
                'email': 'test@test.com',
                'government': '1',  # Cairo
                'city': 'Test City',
                'address': 'Test Address',
            }
        )
        
        if user_created:
            test_user.set_password('testpassword123')
            test_user.save()
            self.stdout.write(self.style.SUCCESS(f"✅ Created test user: {test_user.username} (ID: {test_user.id})"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Using existing test user: {test_user.username} (ID: {test_user.id})"))

        # Find ANY available product to use for testing
        product = Product.objects.first()
        if not product:
            self.stdout.write(self.style.ERROR("\n❌ No products found in database! Cannot create test pills."))
            return
        
        self.stdout.write(self.style.SUCCESS(f"✅ Using product: {product.name} (ID: {product.id}, SKU: {product.product_number})"))

        created_pills = []
        
        for i, order_data in enumerate(test_orders, 1):
            # Get government display name for logging
            gov_dict = dict(GOVERNMENT_CHOICES)
            gov_name = gov_dict.get(order_data['government'], order_data['government'])
            
            self.stdout.write(f"\n📦 Test Order {i}:")
            self.stdout.write(f"   - Government: {gov_name} (code: {order_data['government']})")
            self.stdout.write(f"   - City: {order_data['city']}")
            self.stdout.write(f"   - Address: {order_data['address'][:50]}...")
            self.stdout.write(f"   - Product: {product.name[:40]} x{order_data['quantity']}")
            
            if dry_run:
                self.stdout.write(self.style.WARNING("   [DRY RUN - Not creating]"))
                continue
            
            try:
                # Create PillItem first
                pill_item = PillItem.objects.create(
                    user=test_user,
                    product=product,
                    quantity=order_data['quantity'],
                    size=None,  # No size for books
                    color=None,  # No color for books
                    status='i',  # Initiated
                )
                
                # Create Pill
                pill = Pill.objects.create(
                    user=test_user,
                    status='i',  # Initiated - you'll mark as paid in admin
                    paid=False,
                )
                
                # Add item to pill
                pill.items.add(pill_item)
                
                # Create PillAddress with TEST data
                pill_address = PillAddress.objects.create(
                    pill=pill,
                    name='test test test',  # Test name as requested
                    email='test@test.com',
                    phone='01000000000',  # Random test phone as requested
                    address=order_data['address'],
                    government=order_data['government'],
                    city=order_data['city'],
                    pay_method='v',  # Visa/Prepaid
                )
                
                created_pills.append({
                    'pill': pill,
                    'address': pill_address,
                    'government': gov_name,
                })
                
                self.stdout.write(self.style.SUCCESS(
                    f"   ✅ Created Pill ID: {pill.id}, Number: {pill.pill_number}"
                ))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Error creating pill: {str(e)}"))

        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(f"✅ Created {len(created_pills)} test pills"))
        self.stdout.write(f"{'='*60}\n")
        
        if created_pills:
            self.stdout.write("📋 Pills created (ready to be marked as Paid in Django Admin):\n")
            for item in created_pills:
                pill = item['pill']
                self.stdout.write(f"   • Pill #{pill.pill_number} (ID: {pill.id}) - {item['government']}")
            
            self.stdout.write("\n📝 Next Steps:")
            self.stdout.write("   1. Go to Django Admin → Products → Pills")
            self.stdout.write("   2. Filter by user 'khazenly_test_user' or search by pill number")
            self.stdout.write("   3. Select the test pills and mark them as 'Paid'")
            self.stdout.write("   4. Use the 'Send to Khazenly' action to test the integration")
            self.stdout.write("")
