"""
Management command to test Khazenly API with a specific pill.
Usage: python manage.py test_khazenly_direct <pill_number>
"""
import requests
import json
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import Pill
from services.khazenly_service import KhazenlyService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test Khazenly API directly with a specific pill'

    def add_arguments(self, parser):
        parser.add_argument('pill_number', type=str, help='The pill number to test')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only show what would be sent without actually sending',
        )

    def handle(self, *args, **options):
        pill_number = options['pill_number']
        dry_run = options['dry_run']

        self.stdout.write(self.style.NOTICE(f"🔍 Looking for pill: {pill_number}"))

        try:
            pill = Pill.objects.get(pill_number=pill_number)
        except Pill.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Pill {pill_number} not found"))
            return

        self.stdout.write(self.style.SUCCESS(f"✅ Found pill: {pill.pill_number}"))
        self.stdout.write(f"   User: {pill.user.username} (ID: {pill.user.id})")
        self.stdout.write(f"   Paid: {pill.paid}")
        self.stdout.write(f"   Status: {pill.status}")

        # Check address
        try:
            address = pill.pilladdress
            self.stdout.write(self.style.SUCCESS(f"✅ Address found:"))
            self.stdout.write(f"   Name: {address.name}")
            self.stdout.write(f"   Phone: {address.phone}")
            self.stdout.write(f"   Address: {address.address}")
            self.stdout.write(f"   City: {address.city}")
            self.stdout.write(f"   Government: {address.government}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ No address found: {e}"))
            return

        # Check items
        items = pill.items.all()
        self.stdout.write(f"\n📦 Items ({len(items)}):")
        for item in items:
            self.stdout.write(f"   - {item.product.name} x{item.quantity}")

        # Initialize Khazenly service
        khazenly = KhazenlyService()

        # Get access token
        self.stdout.write(self.style.NOTICE("\n🔑 Getting access token..."))
        access_token = khazenly.get_access_token()
        if not access_token:
            self.stdout.write(self.style.ERROR("❌ Failed to get access token"))
            return
        self.stdout.write(self.style.SUCCESS(f"✅ Token obtained: {access_token[:20]}..."))

        # Build order data manually to inspect
        self.stdout.write(self.style.NOTICE("\n📋 Building order data..."))

        # Use the same logic as the service
        from django.utils import timezone
        import re

        timestamp_suffix = int(timezone.now().timestamp())
        unique_order_id = f"{pill.pill_number}-{timestamp_suffix}"

        # Helper function for sanitizing item names
        def sanitize_item_name(text):
            if not text:
                return ""
            sanitized = str(text).strip()
            sanitized = re.sub(r'[^\w\s\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF.,\-()]+', ' ', sanitized)
            sanitized = re.sub(r'\s+', ' ', sanitized).strip()
            return sanitized

        # Build line items
        line_items = []
        total_product_price = 0

        for item in items:
            product = item.product
            original_price = float(product.price) if product.price else 0
            discounted_price = float(product.discounted_price())
            item_discount = original_price - discounted_price
            total_product_price += discounted_price * item.quantity

            item_description = sanitize_item_name(product.name)
            if item.size:
                item_description += f" (Size: {item.size})"
            if item.color:
                item_description += f" (Color: {sanitize_item_name(item.color.name)})"
            item_description = item_description[:150]

            line_items.append({
                "SKU": product.product_number if product.product_number else f"PROD-{product.id}",
                "ItemName": item_description,
                "Price": discounted_price,
                "Quantity": item.quantity,
                "DiscountAmount": item_discount if item_discount > 0 else None,
                "ItemId": str(item.id)
            })

        # Calculate amounts
        shipping_fees = float(pill.shipping_price())
        gift_discount = float(pill.calculate_gift_discount())
        coupon_discount = float(pill.coupon_discount) if pill.coupon_discount else 0
        total_discount = gift_discount + coupon_discount
        total_amount = total_product_price + shipping_fees - total_discount

        # Get phone numbers
        primary_tel = address.phone if address.phone else ""
        secondary_tel = ""
        if hasattr(pill.user, 'phone') and pill.user.phone:
            secondary_tel = pill.user.phone
        elif hasattr(pill.user, 'phone2') and pill.user.phone2:
            secondary_tel = pill.user.phone2
        elif hasattr(pill.user, 'parent_phone') and pill.user.parent_phone:
            secondary_tel = pill.user.parent_phone

        # Clean phone numbers
        def clean_phone(phone):
            if not phone:
                return ""
            phone = re.sub(r'[^\d]', '', str(phone))
            if phone.startswith('2') and len(phone) > 11:
                phone = phone[1:]
            return phone[:11] if len(phone) > 11 else phone

        primary_tel = clean_phone(primary_tel)
        secondary_tel = clean_phone(secondary_tel)

        # Get Khazenly city
        from products.models import GOVERNMENT_CHOICES
        GOVERNMENT_TO_KHAZENLY_CITY = {
            '1': 'Cairo', '2': 'Alexandria', '3': 'Kafr El Sheikh', '4': 'Dakahleya',
            '5': 'Sharkeya', '6': 'Gharbeya', '7': 'Monefeya', '8': 'Qalyubia',
            '9': 'Giza', '10': 'Bani-Sweif', '11': 'Fayoum', '12': 'Menya',
            '13': 'Assiut', '14': 'Sohag', '15': 'Qena', '16': 'Luxor',
            '17': 'Aswan', '18': 'Red Sea', '19': 'Behera', '20': 'Ismailia',
            '21': 'Suez', '22': 'Port-Said', '23': 'Damietta', '24': 'Marsa Matrouh',
            '25': 'Al-Wadi Al-Gadid', '26': 'North Sinai', '27': 'South Sinai',
        }
        khazenly_city = GOVERNMENT_TO_KHAZENLY_CITY.get(address.government, 'Cairo')

        # Sanitize text fields
        def sanitize_text(text, max_length):
            if not text:
                return ""
            sanitized = str(text).strip()
            sanitized = "".join(ch for ch in sanitized if ord(ch) >= 32 or ch in "\n\r\t")
            if len(sanitized) > max_length:
                sanitized = sanitized[:max_length].strip()
            return sanitized

        customer_name = sanitize_text(address.name or f"Customer {pill.user.username}", 50)
        address1 = sanitize_text(address.address or 'Address not provided', 100)

        # Build order data
        order_data = {
            "Order": {
                "orderId": unique_order_id,
                "orderNumber": pill.pill_number,
                "storeName": settings.KHAZENLY_STORE_NAME,
                "totalAmount": total_amount,
                "shippingFees": shipping_fees,
                "discountAmount": total_discount,
                "taxAmount": 0,
                "invoiceTotalAmount": total_amount,
                "codAmount": 0,
                "weight": 0,
                "noOfBoxes": 1,
                "paymentMethod": "Prepaid",
                "paymentStatus": "paid",
                "storeCurrency": "EGP",
                "isPickedByMerchant": False,
                "merchantAWB": "",
                "merchantCourier": "",
                "merchantAwbDocument": "",
                "additionalNotes": f"Prepaid order for pill {pill.pill_number}"
            },
            "Customer": {
                "customerName": customer_name,
                "Tel": primary_tel,
                "SecondaryTel": secondary_tel,
                "Address1": address1,
                "Address2": "",
                "Address3": "",
                "City": khazenly_city,
                "Country": "Egypt",
                "customerId": str(pill.user.id)  # Using numeric ID only
            },
            "lineItems": line_items
        }

        # Print the order data
        self.stdout.write(self.style.WARNING("\n" + "=" * 80))
        self.stdout.write(self.style.WARNING("📤 ORDER DATA TO BE SENT:"))
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(json.dumps(order_data, indent=2, ensure_ascii=False))
        self.stdout.write(self.style.WARNING("=" * 80))

        if dry_run:
            self.stdout.write(self.style.NOTICE("\n🔒 DRY RUN - Not sending to Khazenly"))
            return

        # Send to Khazenly
        self.stdout.write(self.style.NOTICE("\n🚀 Sending to Khazenly..."))

        api_url = f"{settings.KHAZENLY_BASE_URL}/services/apexrest/api/CreateOrder"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        self.stdout.write(f"   URL: {api_url}")

        try:
            response = requests.post(api_url, json=order_data, headers=headers, timeout=60)

            self.stdout.write(f"\n📡 Response Status: {response.status_code}")
            self.stdout.write(self.style.WARNING("\n" + "=" * 80))
            self.stdout.write(self.style.WARNING("📥 KHAZENLY RESPONSE:"))
            self.stdout.write(self.style.WARNING("=" * 80))

            try:
                response_data = response.json()
                self.stdout.write(json.dumps(response_data, indent=2, ensure_ascii=False))

                if response_data.get('resultCode') == 0:
                    self.stdout.write(self.style.SUCCESS("\n✅ SUCCESS! Order created."))
                    order_info = response_data.get('order', {})
                    self.stdout.write(f"   Sales Order Number: {order_info.get('salesOrderNumber')}")
                else:
                    self.stdout.write(self.style.ERROR(f"\n❌ FAILED! Result: {response_data.get('result')}"))
            except json.JSONDecodeError:
                self.stdout.write(response.text)
                self.stdout.write(self.style.ERROR("\n❌ Invalid JSON response"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Request failed: {e}"))
