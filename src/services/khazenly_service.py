import requests
import json
import logging
import re
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

class KhazenlyService:
    def __init__(self):
        # Updated configuration based on Khazenly feedback
        self.base_url = settings.KHAZENLY_BASE_URL
        self.client_id = settings.KHAZENLY_CLIENT_ID
        self.client_secret = settings.KHAZENLY_CLIENT_SECRET
        self.store_name = settings.KHAZENLY_STORE_NAME
        self.order_user_email = settings.KHAZENLY_ORDER_USER_EMAIL
        self.refresh_token = settings.KHAZENLY_REFRESH_TOKEN
        
        # Cache keys
        self.access_token_cache_key = 'khazenly_access_token'
        self.token_expiry_cache_key = 'khazenly_token_expiry'

    def get_access_token(self):
        """
        Get valid access token, refresh if needed
        """
        try:
            # Check if we have a cached valid token
            cached_token = cache.get(self.access_token_cache_key)
            token_expiry = cache.get(self.token_expiry_cache_key)
            
            if cached_token and token_expiry:
                if datetime.now() < token_expiry:
                    return cached_token
            
            # Token expired or doesn't exist, refresh it
            logger.info("Refreshing Khazenly access token...")
            
            # FIXED: Use correct refresh token endpoint with /selfservice prefix from Postman collection
            token_url = f"{self.base_url}/selfservice/services/oauth2/token"
            
            token_data = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            logger.info(f"Making token request to: {token_url}")
            
            response = requests.post(token_url, data=token_data, headers=headers, timeout=30)
            
            logger.info(f"Token response status: {response.status_code}")
            logger.info(f"Token response: {response.text}")
            
            if response.status_code == 200:
                token_response = response.json()
                access_token = token_response.get('access_token')
                
                if access_token:
                    # Cache the token (expires in 2 hours by default)
                    expiry_time = datetime.now() + timedelta(hours=1, minutes=50)  # 10 min buffer
                    
                    cache.set(self.access_token_cache_key, access_token, timeout=6600)  # 1h 50m
                    cache.set(self.token_expiry_cache_key, expiry_time, timeout=6600)
                    
                    logger.info("✓ Access token refreshed and cached successfully")
                    return access_token
                else:
                    logger.error("No access_token in response")
                    return None
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Exception getting access token: {e}")
            return None
        
    def sanitize_for_khazenly(self, text, max_length=None):
        """
        Sanitize text for Khazenly API requirements
        """
        if not text:
            return ""
        
        # Remove any problematic characters that might cause API issues
        sanitized = str(text).strip()
        
        # Remove control characters and other potentially problematic chars
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in '\n\r\t')
        
        # Truncate if max_length is specified
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length].strip()
            logger.info(f"Text truncated to {max_length} characters for Khazenly")
        
        return sanitized
        
    def validate_order_data(self, order_data):
        """
        Comprehensive validation of order data against Khazenly requirements
        to prevent "corrupted customer data" and "wrong code" errors
        Enhanced with detailed error messages for Django admin visibility
        """
        try:
            issues = []
            order = order_data.get('Order', {})
            customer = order_data.get('Customer', {})
            
            # Check required order fields with detailed feedback
            required_order_fields = ['orderId', 'orderNumber', 'storeName', 'totalAmount']
            for field in required_order_fields:
                if not order.get(field):
                    issues.append(f"❌ Missing required order field: {field}")
            
            # Check required customer fields with detailed feedback
            required_customer_fields = ['customerName', 'Tel', 'Address1', 'City']  # NOTE: customerId removed - Khazenly auto-generates it
            for field in required_customer_fields:
                if not customer.get(field):
                    issues.append(f"❌ Missing required customer field: {field}")
            
            # Check city field length (max 80 characters) with current value
            city = customer.get('City', '')
            if city and len(city) > 80:
                issues.append(f"❌ City field too long: '{city}' ({len(city)}/80 chars)")
            
            # Check customer name length with current value
            customer_name = customer.get('customerName', '')
            if customer_name and len(customer_name) > 100:
                issues.append(f"❌ Customer name too long: '{customer_name}' ({len(customer_name)}/100 chars)")
            
            # Check phone number format and length with detailed feedback
            primary_tel = customer.get('Tel', '')
            if primary_tel:
                if len(primary_tel) > 20:
                    issues.append(f"❌ Primary phone too long: '{primary_tel}' ({len(primary_tel)}/20 chars)")
                # Only check if phone starts with valid Egyptian mobile prefixes
                if not (primary_tel.startswith('010') or primary_tel.startswith('011') or 
                       primary_tel.startswith('012') or primary_tel.startswith('015')):
                    issues.append(f"❌ Primary phone invalid format: '{primary_tel}' (must start with 010, 011, 012, or 015)")
            
            # REVERTED: Use 'SecondaryTel' (uppercase 'S') - lowercase doesn't work with Khazenly
            secondary_tel = customer.get('SecondaryTel', '')
            if secondary_tel and secondary_tel != '':
                if len(secondary_tel) > 20:
                    issues.append(f"❌ Secondary phone too long: '{secondary_tel}' ({len(secondary_tel)}/20 chars)")
                # Only check if phone starts with valid Egyptian mobile prefixes
                if not (secondary_tel.startswith('010') or secondary_tel.startswith('011') or 
                       secondary_tel.startswith('012') or secondary_tel.startswith('015')):
                    issues.append(f"❌ Secondary phone invalid format: '{secondary_tel}' (must start with 010, 011, 012, or 015)")
            
            # Check address field length with current value
            address1 = customer.get('Address1', '')
            if address1 and len(address1) > 255:
                issues.append(f"❌ Address too long: '{address1[:50]}...' ({len(address1)}/255 chars)")
            
            # Check line items with detailed feedback
            line_items = order_data.get('lineItems', [])
            if not line_items:
                issues.append("❌ No products found in order")
            else:
                for i, item in enumerate(line_items):
                    item_num = i + 1
                    # FIXED: Use correct field name 'ItemName' (PascalCase) instead of 'itemName'
                    item_name = item.get('ItemName', '')
                    
                    if item_name and len(item_name) > 200:
                        issues.append(f"❌ Product {item_num} name too long: '{item_name[:30]}...' ({len(item_name)}/200 chars)")
                    
                    # FIXED: Check for correct Khazenly field names (PascalCase)
                    # Required fields: SKU, ItemName, Price, Quantity, ItemId
                    if not item.get('SKU'):
                        issues.append(f"❌ Product {item_num} missing SKU ({item_name[:30] if item_name else 'Unknown Product'})")
                    if not item.get('Quantity'):
                        issues.append(f"❌ Product {item_num} missing quantity ({item_name[:30] if item_name else 'Unknown Product'})")
                    if not item.get('Price'):
                        issues.append(f"❌ Product {item_num} missing price ({item_name[:30] if item_name else 'Unknown Product'})")
            
            # Khazenly city validation using their actual supported cities
            if city:
                # Khazenly's officially supported cities from their documentation
                khazenly_supported_cities = [
                    'Alexandria', 'Assiut', 'Aswan', 'Bani-Sweif', 'Behera', 'Cairo', 
                    'Dakahleya', 'Damietta', 'Fayoum', 'Giza', 'Hurghada', 'Ismailia', 
                    'Luxor', 'Mahalla', 'Mansoura', 'Marsa Matrouh', 'Menya', 'Monefeya', 
                    'North Coast', 'Port-Said', 'Qalyubia', 'Qena', 'Red Sea', 'Sharkeya', 
                    'Sohag', 'Suez', 'Tanta', 'Zagazig', 'Gharbeya', 'Kafr El Sheikh', 
                    'Al-Wadi Al-Gadid', 'Sharm El Sheikh', 'North Sinai', 'South Sinai'
                ]
                
                # Check if city matches any Khazenly supported city
                city_found = False
                matched_city = None
                
                # First, try exact match
                if city in khazenly_supported_cities:
                    city_found = True
                    matched_city = city
                    logger.info(f"✅ Exact match found: '{city}' is supported by Khazenly")
                else:
                    # Try flexible matching for common variations
                    city_normalized = city.lower().replace('-', ' ').replace('_', ' ').strip()
                    
                    for supported_city in khazenly_supported_cities:
                        supported_normalized = supported_city.lower().replace('-', ' ').replace('_', ' ').strip()
                        
                        # Check if normalized versions match
                        if city_normalized == supported_normalized:
                            city_found = True
                            matched_city = supported_city
                            logger.info(f"✅ Khazenly city '{supported_city}' matched with flexible matching for input '{city}'")
                            break
                        
                        # Also check if the input contains the supported city name
                        if supported_normalized in city_normalized or city_normalized in supported_normalized:
                            city_found = True
                            matched_city = supported_city
                            logger.info(f"✅ Khazenly city '{supported_city}' found within input '{city}'")
                            break
                
                if not city_found:
                    # Provide helpful error message with Khazenly's supported cities
                    available_cities = ', '.join(khazenly_supported_cities[:8]) + '...'
                    issues.append(f"❌ City/Government '{city}' is not a valid Khazenly supported city. Supported cities: {available_cities}")
                    logger.warning(f"City '{city}' is not supported by Khazenly. Available cities: {available_cities}")
                    
                    # Log the normalized comparison for debugging
                    logger.debug(f"Normalized input: '{city_normalized}' vs Khazenly cities: {[c.lower().replace('-', ' ').replace('_', ' ').strip() for c in khazenly_supported_cities[:5]]}...")
                else:
                    logger.info(f"✅ City validation passed: '{city}' → '{matched_city}'")
            
            if issues:
                error_summary = f"Validation failed with {len(issues)} issues: " + "; ".join(issues[:3])
                if len(issues) > 3:
                    error_summary += f" ... and {len(issues) - 3} more issues"
                
                logger.warning(f"⚠️ Order data validation issues found: {', '.join(issues)}")
                return {'valid': False, 'issues': issues, 'summary': error_summary}
            else:
                customer_name_short = customer_name[:20] if customer_name else 'Unknown'
                item_count = len(line_items)
                success_msg = f"✅ Validation passed: {item_count} items for {customer_name_short}"
                
                logger.info("✅ Order data validation passed")
                return {'valid': True, 'issues': [], 'summary': success_msg}
                
        except Exception as e:
            logger.error(f"❌ Error validating order data: {str(e)}")
            return {'valid': False, 'issues': [f'Validation error: {str(e)}']}

    def create_order(self, pill):
        """
        Create order in Khazenly with corrected configuration based on working Postman collection
        """
        try:
            logger.info(f"Creating Khazenly order for pill {pill.pill_number}")
            
            # Get valid access token
            access_token = self.get_access_token()
            if not access_token:
                return {'success': False, 'error': 'Failed to get access token'}
            
            # Validate pill has required data
            if not hasattr(pill, 'pilladdress'):
                return {'success': False, 'error': 'Pill address information missing'}
            
            address = pill.pilladdress
            
            # FIXED: Create unique order ID to avoid conflicts
            timestamp_suffix = int(timezone.now().timestamp())
            unique_order_id = f"{pill.pill_number}-{timestamp_suffix}"
            
            # Prepare line items with logical product data including color and size
            line_items = []
            total_product_price = 0
            
            # Debug: Check if pill has items
            pill_items = pill.items.all()
            logger.info(f"🔍 Processing pill {pill.pill_number}: Found {len(pill_items)} items")
            
            # Helper function for sanitizing item names (moved outside loop for efficiency)
            import re
            def sanitize_item_name(text):
                """Remove emojis and special characters from product name for Khazenly API"""
                if not text:
                    return ""
                sanitized = str(text).strip()
                # Keep Arabic characters, English letters, numbers, spaces, and basic safe punctuation
                sanitized = re.sub(r'[^\w\s\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF.,\-()]+', ' ', sanitized)
                # Clean up multiple spaces
                sanitized = re.sub(r'\s+', ' ', sanitized).strip()
                return sanitized

            for item in pill_items:
                product = item.product
                original_price = float(product.price) if product.price else 0
                discounted_price = float(product.discounted_price())
                item_discount = original_price - discounted_price
                
                total_product_price += discounted_price * item.quantity
                
                # Build detailed item description with color and size
                # FIXED: Sanitize product name to remove emojis and special characters that cause Khazenly errors
                item_description = sanitize_item_name(product.name)
                description_parts = []
                
                # Add size if available
                if item.size:
                    description_parts.append(f"Size: {item.size}")
                
                # Add color if available
                if item.color:
                    description_parts.append(f"Color: {sanitize_item_name(item.color.name)}")
                
                # Combine description parts
                if description_parts:
                    item_description += f" ({', '.join(description_parts)})"
                
                # Ensure description doesn't exceed reasonable length (Khazenly might have limits)
                item_description = item_description[:150]  # Limit to 150 characters
                
                # Use logical product data for line items - FIXED: Match Khazenly's exact field names
                line_items.append({
                    "SKU": product.product_number if product.product_number else f"PROD-{product.id}",  # FIXED: Uppercase SKU
                    "ItemName": item_description,  # FIXED: PascalCase ItemName
                    "Price": discounted_price,  # FIXED: PascalCase Price
                    "Quantity": item.quantity,  # FIXED: PascalCase Quantity
                    "DiscountAmount": item_discount if item_discount > 0 else None,  # FIXED: PascalCase, null if 0
                    "ItemId": str(item.id)  # FIXED: PascalCase ItemId, convert to string
                })
            
            logger.info(f"🔍 Created {len(line_items)} line items for pill {pill.pill_number}")
            if not line_items:
                logger.warning(f"⚠️ No line items created for pill {pill.pill_number}. Pill items count: {len(pill_items)}")
            
            # Calculate amounts with proper gift and coupon discounts
            shipping_fees = float(pill.shipping_price())
            gift_discount = float(pill.calculate_gift_discount())
            coupon_discount = float(pill.coupon_discount) if pill.coupon_discount else 0
            total_discount = gift_discount + coupon_discount
            total_amount = total_product_price + shipping_fees - total_discount
            
            # FIXED: Customer data format based on Khazenly requirements
            # Phone handling logic according to requirements:
            # - tel should be the phone from the pilladdress
            # - secondaryTel should be user.phone if exists, if not user.phone2 if exists, if not user.parent_phone
            
            # Primary tel is always from pilladdress
            primary_tel = address.phone if address.phone else ""
            logger.info(f"🔍 Phone processing debug:")
            logger.info(f"  - address.phone: '{getattr(address, 'phone', 'NOT_FOUND')}'")
            logger.info(f"  - primary_tel: '{primary_tel}'")
            
            # Secondary tel priority: user.phone -> user.phone2 -> user.parent_phone
            secondary_tel = ""
            logger.info(f"  - user.phone: '{getattr(pill.user, 'phone', 'NOT_FOUND')}'")
            logger.info(f"  - user.phone2: '{getattr(pill.user, 'phone2', 'NOT_FOUND')}'")
            logger.info(f"  - user.parent_phone: '{getattr(pill.user, 'parent_phone', 'NOT_FOUND')}'")
            
            if hasattr(pill.user, 'phone') and pill.user.phone:
                secondary_tel = pill.user.phone
                logger.info(f"✅ Using user.phone as secondary: '{secondary_tel}'")
            elif hasattr(pill.user, 'phone2') and pill.user.phone2:
                secondary_tel = pill.user.phone2
                logger.info(f"✅ Using user.phone2 as secondary: '{secondary_tel}'")
            elif hasattr(pill.user, 'parent_phone') and pill.user.parent_phone:
                secondary_tel = pill.user.parent_phone
                logger.info(f"✅ Using user.parent_phone as secondary: '{secondary_tel}'")
            else:
                logger.info("❌ No secondary phone found")
            
            # Validate and sanitize customer data
            def sanitize_text(text, max_length, field_name="field"):
                """
                Relaxed text sanitization for Khazenly API
                Mainly removes control characters and ensures UTF-8
                """
                if not text:
                    return ""
                
                # Convert to string and strip whitespace
                sanitized = str(text).strip()
                
                # Remove control characters (except basic whitespace) and null bytes
                # Keep everything else as the user requested "allow everything normally"
                sanitized = "".join(ch for ch in sanitized if ord(ch) >= 32 or ch in "\n\r\t")
                
                # Ensure proper UTF-8 encoding
                try:
                    sanitized = sanitized.encode('utf-8').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    sanitized = sanitized.encode('utf-8', 'ignore').decode('utf-8')
                    logger.warning(f"⚠️ Encoding issues in {field_name}, removed problematic characters")
                
                # Limit length (be careful with UTF-8 byte length for Arabic)
                if len(sanitized) > max_length:
                    logger.warning(f"⚠️ Truncating {field_name} from {len(sanitized)} to {max_length} characters")
                    sanitized = sanitized[:max_length].strip()
                    # Avoid breaking words - find last space
                    if not sanitized.endswith(' '):
                        last_space = sanitized.rfind(' ')
                        if last_space > max_length * 0.8:
                            sanitized = sanitized[:last_space].strip()
                
                return sanitized
            
            def validate_phone(phone):
                """
                Enhanced phone validation for Khazenly API
                - Removes +2/2 country code prefix
                - Validates Egyptian mobile format (11 digits, starts with 010/011/012/015)
                - Returns empty string if invalid
                """
                if not phone:
                    return ""
                
                # Convert to string and strip whitespace
                phone_str = str(phone).strip()
                
                # Remove any non-digit characters except + at the beginning
                import re
                phone_str = re.sub(r'[^\d+]', '', phone_str)
                
                # Remove +2 or 2 prefix (Egyptian country code)
                if phone_str.startswith('+2'):
                    phone_str = phone_str[2:]
                elif phone_str.startswith('2') and len(phone_str) > 11:
                    phone_str = phone_str[1:]
                
                # Validate Egyptian mobile number format (11 digits, starts with 010/011/012/015)
                if phone_str:
                    if len(phone_str) != 11:
                        logger.warning(f"⚠️ Phone '{phone}' is not 11 digits (got {len(phone_str)})")
                    
                    if not (phone_str.startswith('010') or phone_str.startswith('011') or 
                           phone_str.startswith('012') or phone_str.startswith('015')):
                        logger.warning(f"⚠️ Phone '{phone}' doesn't start with valid prefix (010/011/012/015)")
                    
                    # Ensure exactly 11 digits
                    if len(phone_str) > 11:
                        phone_str = phone_str[:11]
                        logger.warning(f"⚠️ Truncated phone to 11 digits: '{phone_str}'")
                
                logger.info(f"✅ Validated phone: '{phone}' -> '{phone_str}'")
                return phone_str
            
            # Get city and government separately for proper field mapping
            # CRITICAL: Khazenly expects ONLY the government name in the City field
            # The government name must match their exact list (Alexandria, Cairo, Giza, etc.)
            khazenly_city = ""
            
            # Map our government choices to Khazenly's expected city values
            # FIXED: Use numeric string keys matching GOVERNMENT_CHOICES in products/models.py
            # GOVERNMENT_CHOICES uses: ('1', 'Cairo'), ('2', 'Alexandria'), etc.
            GOVERNMENT_TO_KHAZENLY_CITY = {
                '1': 'Cairo',
                '2': 'Alexandria',
                '3': 'Kafr El Sheikh',
                '4': 'Dakahleya',
                '5': 'Sharkeya',
                '6': 'Gharbeya',
                '7': 'Monefeya',
                '8': 'Qalyubia',
                '9': 'Giza',
                '10': 'Bani-Sweif',
                '11': 'Fayoum',
                '12': 'Menya',
                '13': 'Assiut',
                '14': 'Sohag',
                '15': 'Qena',
                '16': 'Luxor',
                '17': 'Aswan',
                '18': 'Red Sea',
                '19': 'Behera',
                '20': 'Ismailia',
                '21': 'Suez',
                '22': 'Port-Said',
                '23': 'Damietta',
                '24': 'Marsa Matrouh',
                '25': 'Al-Wadi Al-Gadid',
                '26': 'North Sinai',
                '27': 'South Sinai',
            }
            
            # Get city from pilladdress
            logger.info(f"🔍 City processing debug:")
            logger.info(f"  - address.city: '{getattr(address, 'city', 'NOT_FOUND')}'")
            logger.info(f"  - address.government: '{getattr(address, 'government', 'NOT_FOUND')}'")
            
            # Map government code to Khazenly city
            if hasattr(address, 'government') and address.government:
                from products.models import GOVERNMENT_CHOICES
                khazenly_city = GOVERNMENT_TO_KHAZENLY_CITY.get(address.government, '')
                if not khazenly_city:
                    # If government code not in mapping, try to get display name from choices
                    gov_dict = dict(GOVERNMENT_CHOICES)
                    khazenly_city = gov_dict.get(address.government, 'Cairo')
                logger.info(f"✅ Mapped government '{address.government}' to Khazenly city: '{khazenly_city}'")
            else:
                khazenly_city = "Cairo"  # Default fallback
                logger.warning("⚠️ No government found, using 'Cairo' as default")
            
            # Validate khazenly_city is in the supported list
            KHAZENLY_SUPPORTED_CITIES = [
                'Alexandria', 'Assiut', 'Aswan', 'Bani-Sweif', 'Behera', 'Cairo', 
                'Dakahleya', 'Damietta', 'Fayoum', 'Giza', 'Hurghada', 'Ismailia', 
                'Luxor', 'Mahalla', 'Mansoura', 'Marsa Matrouh', 'Menya', 'Monefeya', 
                'North Coast', 'Port-Said', 'Qalyubia', 'Qena', 'Red Sea', 'Sharkeya', 
                'Sohag', 'Suez', 'Tanta', 'Zagazig', 'Gharbeya', 'Kafr El Sheikh', 
                'Al-Wadi Al-Gadid', 'Sharm El Sheikh', 'North Sinai', 'South Sinai'
            ]
            
            if khazenly_city not in KHAZENLY_SUPPORTED_CITIES:
                logger.warning(f"⚠️ City '{khazenly_city}' not in Khazenly's supported list. Using 'Cairo' as fallback.")
                khazenly_city = "Cairo"
            
            logger.info(f"🎯 Final Khazenly City field: '{khazenly_city}'")
            
            
            # Build order data
            order_data = {
                "Order": {
                    "orderId": unique_order_id,
                    "orderNumber": pill.pill_number,
                    "storeName": self.store_name,
                    "totalAmount": total_amount,
                    "shippingFees": shipping_fees,
                    "discountAmount": total_discount,
                    "taxAmount": 0,
                    "invoiceTotalAmount": total_amount,
                    "codAmount": 0,  # FIXED: Set COD amount to 0 for prepaid orders
                    "weight": 0,
                    "noOfBoxes": 1,
                    "paymentMethod": "Prepaid",  # FIXED: Changed from "Cash-on-Delivery" to "Prepaid"
                    "paymentStatus": "paid",     # FIXED: Changed from "pending" to "paid"
                    "storeCurrency": "EGP",
                    "isPickedByMerchant": False,
                    "merchantAWB": "",
                    "merchantCourier": "",
                    "merchantAwbDocument": "",
                    "additionalNotes": f"Prepaid order for pill {pill.pill_number} - {len(line_items)} items - Payment completed via Shake-out"
                },
                "Customer": {
                    "customerName": sanitize_text(address.name or f"Customer {pill.user.username}", 50, "customerName"),
                    "Tel": validate_phone(primary_tel),
                    "SecondaryTel": validate_phone(secondary_tel),  # REVERTED: Capital S works with Khazenly
                    "Address1": sanitize_text(
                        address.address or 'Address not provided', 
                        100, "address1"
                    ),
                    "Address2": "",
                    "Address3": "",
                    "City": khazenly_city,  # FIXED: Use mapped Khazenly city from government code
                    "Country": "Egypt",
                    # FIXED: Use unique customerId per order to bypass Khazenly's duplicate customer detection
                    # This allows the same customer (same phone) to place multiple orders
                    "customerId": f"PILL-{pill.pill_number}"
                },
                "lineItems": line_items
            }
            
            # Enhanced customer data validation to prevent "corrupted customer data" errors
            customer_data = order_data.get('Customer', {})
            
            # Log the complete customer data being sent to Khazenly
            logger.info("=" * 80)
            logger.info("📋 CUSTOMER DATA BEING SENT TO KHAZENLY:")
            logger.info(f"  • Customer Name: '{customer_data.get('customerName')}' ({len(customer_data.get('customerName', ''))} chars, {len(customer_data.get('customerName', '').encode('utf-8'))} bytes)")
            logger.info(f"  • Primary Tel: '{customer_data.get('Tel')}' ({len(customer_data.get('Tel', ''))} digits)")
            logger.info(f"  • Secondary Tel: '{customer_data.get('SecondaryTel')}' ({len(customer_data.get('SecondaryTel', ''))} digits)")
            logger.info(f"  • Address1: '{customer_data.get('Address1')}' ({len(customer_data.get('Address1', ''))} chars, {len(customer_data.get('Address1', '').encode('utf-8'))} bytes)")
            logger.info(f"  • City: '{customer_data.get('City')}' ({len(customer_data.get('City', ''))} chars)")
            logger.info(f"  • Country: '{customer_data.get('Country')}'")
            logger.info(f"  • Customer ID: '{customer_data.get('customerId')}'")
            logger.info("=" * 80)
            
            # Additional validation for problematic data patterns
            validation_issues = []
            
            # Check customer name for problematic characters
            customer_name = customer_data.get('customerName', '')
            if customer_name:
                # Check for null bytes or control characters
                if '\x00' in customer_name or any(ord(c) < 32 and c not in ' \t\n\r' for c in customer_name):
                    validation_issues.append(f"Customer name contains invalid control characters")
                
                # Check byte length
                if len(customer_name.encode('utf-8')) > 100:
                    validation_issues.append(f"Customer name too long: {len(customer_name.encode('utf-8'))} bytes (max 100)")
            
            # Check phone numbers
            primary_tel = customer_data.get('Tel', '')
            secondary_tel = customer_data.get('SecondaryTel', '')
            
            if primary_tel:
                if not primary_tel.isdigit():
                    validation_issues.append(f"Primary phone contains non-digit characters")
                if len(primary_tel) != 11:
                    validation_issues.append(f"Primary phone must be 11 digits, got {len(primary_tel)}")
            
            if secondary_tel and secondary_tel != '':
                if not secondary_tel.isdigit():
                    validation_issues.append(f"Secondary phone contains non-digit characters")
                if len(secondary_tel) != 11:
                    validation_issues.append(f"Secondary phone must be 11 digits, got {len(secondary_tel)}")
            
            # Check address for problematic characters
            address1 = customer_data.get('Address1', '')
            if address1:
                if '\x00' in address1 or any(ord(c) < 32 and c not in ' \t\n\r' for c in address1):
                    validation_issues.append(f"Address contains invalid control characters")
                if len(address1.encode('utf-8')) > 255:
                    validation_issues.append(f"Address too long: {len(address1.encode('utf-8'))} bytes (max 255)")
            
            # Check city
            city = customer_data.get('City', '')
            if city:
                if '\x00' in city or any(ord(c) < 32 and c not in ' \t\n\r' for c in city):
                    validation_issues.append(f"City contains invalid control characters")
                if len(city.encode('utf-8')) > 80:
                    validation_issues.append(f"City too long: {len(city.encode('utf-8'))} bytes (max 80)")
            
            # If validation issues found, fail early with detailed error
            if validation_issues:
                error_msg = "; ".join(validation_issues)
                logger.error(f"❌ Customer data validation failed for pill {pill.pill_number}: {error_msg}")
                return {
                    'success': False,
                    'error': f'Customer data validation failed: {error_msg}'
                }
            
            logger.info(f"✅ Customer data validation passed for pill {pill.pill_number}")
            
            # Debug logging for order structure
            logger.info(f"🔍 Order data structure created:")
            logger.info(f"  - Root keys: {list(order_data.keys())}")
            logger.info(f"  - Order keys: {list(order_data.get('Order', {}).keys())}")
            logger.info(f"  - Line items count: {len(order_data.get('lineItems', []))}")
            
            
            # FIXED: Use correct API endpoint from Postman collection
            api_url = f"{self.base_url}/services/apexrest/api/CreateOrder"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            logger.info(f"Making order request to: {api_url}")
            logger.info(f"Order data: {json.dumps(order_data, indent=2)}")
            
            # Validate order data before sending with enhanced error messages
            validation_result = self.validate_order_data(order_data)
            if not validation_result['valid']:
                # Use the detailed error summary for better visibility in Django admin
                error_summary = validation_result.get('summary', 'Order validation failed')
                detailed_issues = validation_result.get('issues', [])
                
                # Create a comprehensive error message for Django admin
                admin_error_msg = f"🚫 KHAZENLY VALIDATION FAILED\n\n{error_summary}\n\nDetailed Issues:\n" + "\n".join([f"• {issue}" for issue in detailed_issues[:10]])
                if len(detailed_issues) > 10:
                    admin_error_msg += f"\n... and {len(detailed_issues) - 10} more validation issues"
                
                admin_error_msg += f"\n\n📋 Order Info: Pill #{pill.pill_number}, Customer: {order_data.get('Customer', {}).get('customerName', 'Unknown')}"
                
                logger.error(f"❌ {error_summary}")
                logger.error(f"❌ Full validation issues: {detailed_issues}")
                return {'success': False, 'error': admin_error_msg}
            
            # Make the API request to Khazenly with better error handling
            logger.info(f"🚀 Sending order to Khazenly API: {api_url}")
            logger.info(f"📦 Order data preview: OrderID={order_data['Order']['orderId']}, Customer={order_data['Order'].get('customerName', 'N/A')}")
            
            try:
                response = requests.post(api_url, json=order_data, headers=headers, timeout=60)
                logger.info(f"📡 Khazenly API response status: {response.status_code}")
                logger.info(f"📡 Khazenly API response: {response.text}")
            except requests.exceptions.Timeout:
                logger.error("⏰ Khazenly API request timed out after 60 seconds")
                return {'success': False, 'error': 'Khazenly API request timed out. Please try again later.'}
            except requests.exceptions.ConnectionError as e:
                logger.error(f"🔌 Connection error to Khazenly API: {str(e)}")
                return {'success': False, 'error': 'Could not connect to Khazenly API. Please check network connection.'}
            except requests.exceptions.RequestException as e:
                logger.error(f"🌐 Request error to Khazenly API: {str(e)}")
                return {'success': False, 'error': f'Network error: {str(e)}'}
            
            logger.info(f"Khazenly order response status: {response.status_code}")
            logger.info(f"Khazenly order response: {response.text}")
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON response from Khazenly: {str(e)}")
                    logger.error(f"Raw response: {response.text}")
                    return {'success': False, 'error': 'Invalid JSON response from Khazenly API'}
                
                # Check for success
                if response_data.get('resultCode') == 0:
                    order_info = response_data.get('order', {})
                    
                    logger.info(f"✓ Khazenly order created successfully: {order_info.get('salesOrderNumber')}")
                    
                    return {
                        'success': True,
                        'data': {
                            'khazenly_order_id': order_info.get('id'),
                            'sales_order_number': order_info.get('salesOrderNumber'),
                            'order_number': order_info.get('orderNumber'),
                            'line_items': response_data.get('lineItems', []),
                            'customer': response_data.get('customer', {}),
                            'raw_response': response_data
                        }
                    }
                else:
                    # Extract detailed error information
                    result_code = response_data.get('resultCode', 'Unknown')
                    error_msg = response_data.get('result', response_data.get('message', 'Unknown error from Khazenly'))
                    
                    logger.error(f"❌ Khazenly order creation failed - ResultCode: {result_code}")
                    logger.error(f"❌ Error details: {error_msg}")
                    logger.error(f"❌ Full response: {response_data}")
                    
                    # Provide more specific error messages for common issues
                    error_msg_lower = error_msg.lower()
                    if "STRING_TOO_LONG" in error_msg:
                        if "City" in error_msg:
                            return {'success': False, 'error': 'Address city field is too long. Please use a shorter address.'}
                        else:
                            return {'success': False, 'error': 'One of the address fields is too long. Please shorten your address details.'}
                    elif "REQUIRED_FIELD_MISSING" in error_msg:
                        return {'success': False, 'error': 'Required field missing. Please ensure all address information is complete.'}
                    elif "corrupted customer data" in error_msg_lower or "wrong code" in error_msg_lower:
                        # Log detailed customer data for debugging
                        customer = order_data.get('Customer', {})
                        logger.error(f"🚨 CORRUPTED CUSTOMER DATA DETAILS:")
                        logger.error(f"  - customerName: '{customer.get('customerName')}' (type: {type(customer.get('customerName'))}, len: {len(str(customer.get('customerName', '')))})")
                        
                        # RETRY STRATEGY: 
                        # If "wrong code" or "corrupted data", it often means:
                        # 1. The customerId format (we send USER-XXX) is rejected, they might want just XXX
                        # 2. Or there are special characters in the address that passed relaxed sanitization but Khazenly dislikes
                        
                        # Only retry if we haven't retried already (check for retry flag in pill)
                        if not getattr(pill, '_khazenly_retry_attempted', False):
                            logger.info(f"🔄 Retrying with simplified data for pill {pill.pill_number}...")
                            pill._khazenly_retry_attempted = True
                            
                            # 1. Use simple numeric ID
                            retry_customer_id = str(pill.user.id)
                            
                            # 2. Use stricter sanitization for address/name just in case
                            import re
                            def strict_sanitize(text):
                                if not text: return ""
                                s = str(text).strip()
                                # Only alphanumeric, spaces, and safe punctuation
                                s = re.sub(r'[^\w\s\u0600-\u06FF.,\-]+', ' ', s)
                                s = re.sub(r'\s+', ' ', s).strip()
                                return s
                            
                            # Update order data for retry
                            order_data['Customer']['customerId'] = retry_customer_id
                            order_data['Customer']['customerName'] = strict_sanitize(order_data['Customer']['customerName'])
                            order_data['Customer']['Address1'] = strict_sanitize(order_data['Customer']['Address1'])
                            
                            logger.info(f"🔄 Retry Customer ID: '{retry_customer_id}'")
                            logger.info(f"🔄 Retry Address: '{order_data['Customer']['Address1']}'")
                            
                            # Recursive call or just resend request?
                            # Resending request to avoid deep recursion loop issues
                            try:
                                logger.info(f"🚀 (RETRY) Sending order to Khazenly API: {api_url}")
                                retry_response = requests.post(api_url, json=order_data, headers=headers, timeout=60)
                                logger.info(f"📡 (RETRY) Khazenly API response status: {retry_response.status_code}")
                                logger.info(f"📡 (RETRY) Khazenly API response: {retry_response.text}")
                                
                                if retry_response.status_code == 200:
                                    retry_data = retry_response.json()
                                    if retry_data.get('resultCode') == 0:
                                        order_info = retry_data.get('order', {})
                                        logger.info(f"✓ (RETRY) Khazenly order created successfully!")
                                        return {
                                            'success': True,
                                            'data': {
                                                'khazenly_order_id': order_info.get('id'),
                                                'sales_order_number': order_info.get('salesOrderNumber'),
                                                'order_number': order_info.get('orderNumber'),
                                                'line_items': retry_data.get('lineItems', []),
                                                'customer': retry_data.get('customer', {}),
                                                'raw_response': retry_data
                                            }
                                        }
                            except Exception as retry_e:
                                logger.error(f"❌ Retry failed: {retry_e}")
                        
                        return {
                            'success': False, 
                            'error': f'Corrupted customer data detected. Pill ID: {pill.id}, User ID: {pill.user.id}. Please check customer address information for invalid characters or formatting issues. Khazenly error: {error_msg}'
                        }
                    else:
                        return {'success': False, 'error': f'Khazenly API error (Code {result_code}): {error_msg}'}
            else:
                logger.error(f"❌ HTTP error creating Khazenly order: {response.status_code}")
                logger.error(f"❌ Response headers: {dict(response.headers)}")
                logger.error(f"❌ Response text: {response.text}")
                
                # Try to parse error response
                try:
                    error_data = response.json()
                    error_msg = error_data.get('result', error_data.get('message', error_data.get('error', f'HTTP {response.status_code}')))
                    
                    # Handle DUPLICATES_DETECTED - customer/order already exists
                    if "DUPLICATES_DETECTED" in error_msg or "Consignee Code already exists" in error_msg:
                        logger.warning(f"⚠️ Duplicate detected in Khazenly for pill {pill.pill_number}")
                        # This order may have already been created in a previous attempt
                        # Check if this specific order exists
                        existing_order = self.check_order_exists(pill.pill_number)
                        if existing_order and existing_order.get('salesOrderNumber'):
                            logger.info(f"✅ Order already exists in Khazenly: {existing_order.get('salesOrderNumber')}")
                            return {
                                'success': True,
                                'data': {
                                    'khazenly_order_id': existing_order.get('id'),
                                    'sales_order_number': existing_order.get('salesOrderNumber'),
                                    'order_number': existing_order.get('orderNumber'),
                                    'already_exists': True,
                                    'message': 'Order was already processed in a previous attempt'
                                }
                            }
                        else:
                            # Order doesn't exist but customer does - could be from another order
                            return {
                                'success': False, 
                                'error': f'Customer already exists in Khazenly (from a previous order). This may indicate the order was partially processed. Please check Khazenly dashboard for order {pill.pill_number} or contact support. Details: {error_msg}'
                            }
                except:
                    error_msg = f'HTTP {response.status_code}: {response.text[:200]}...' if len(response.text) > 200 else response.text
                
                return {'success': False, 'error': f'Khazenly API error: {error_msg}'}
                
        except Exception as e:
            logger.error(f"Exception creating Khazenly order: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}

    def check_order_exists(self, order_number):
        """
        Check if an order already exists in Khazenly by orderNumber (pill_number).
        Returns the existing order info if found, None otherwise.
        """
        try:
            access_token = self.get_access_token()
            if not access_token:
                logger.warning("Could not get token to check order existence")
                return None
            
            # Try to query for the order by orderNumber using the API
            # Note: This endpoint may not exist - we'll handle failure gracefully
            query_url = f"{self.base_url}/services/apexrest/api/GetOrder"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Try with orderNumber parameter
            params = {'orderNumber': order_number}
            
            logger.info(f"🔍 Checking if order {order_number} exists in Khazenly...")
            
            response = requests.get(query_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('resultCode') == 0 and data.get('order', {}).get('id'):
                    logger.info(f"✅ Order {order_number} already exists in Khazenly")
                    return data.get('order')
            
            # Order doesn't exist or endpoint not available
            return None
            
        except Exception as e:
            logger.warning(f"Could not check order existence: {e}")
            return None

    def get_order_status(self, sales_order_number):
        """
        Get order status from Khazenly
        """
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {'success': False, 'error': 'Failed to get access token'}
            
            # Construct status check URL
            status_url = f"{self.base_url}/services/apexrest/ExternalIntegrationWebService/orders/{sales_order_number}"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            logger.info(f"Checking order status: {status_url}")
            
            response = requests.get(status_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
                
        except Exception as e:
            logger.error(f"Exception getting order status: {e}")
            return {'success': False, 'error': str(e)}

    def diagnose_customer_data(self, pill):
        """
        Diagnose customer data issues that might cause Khazenly API errors
        """
        try:
            logger.info(f"🔍 DIAGNOSING CUSTOMER DATA for Pill {pill.pill_number}:")
            
            if not hasattr(pill, 'pilladdress'):
                return {
                    'issues': ['Missing address information'],
                    'details': 'Pill has no associated address (pilladdress)'
                }
            
            address = pill.pilladdress
            issues = []
            details = {}
            
            # Check customer name
            customer_name = address.name or f"Customer {pill.user.username}"
            details['customerName'] = {
                'value': customer_name,
                'length': len(customer_name),
                'contains_special_chars': bool(re.search(r'[^\w\s\-.,()[\]]+', customer_name))
            }
            if len(customer_name) > 50:
                issues.append(f'Customer name too long ({len(customer_name)} chars, max 50)')
            
            # Check phone numbers
            import re
            phone_numbers = []
            if address.phone:
                phone_numbers.append(('primary', address.phone))
            if hasattr(pill.user, 'phone') and pill.user.phone:
                phone_numbers.append(('user_phone', pill.user.phone))
            if hasattr(pill.user, 'phone2') and pill.user.phone2:
                phone_numbers.append(('user_phone2', pill.user.phone2))
            
            for phone_type, phone in phone_numbers:
                digits_only = re.sub(r'\D', '', str(phone)) if phone else ''
                details[f'{phone_type}_phone'] = {
                    'original': phone,
                    'digits_only': digits_only,
                    'length': len(digits_only),
                    'valid_egyptian': len(digits_only) >= 10 and len(digits_only) <= 11 and (digits_only.startswith('01') or digits_only.startswith('201'))
                }
                if phone and len(digits_only) < 10:
                    issues.append(f'{phone_type} phone too short ({digits_only})')
                elif phone and len(digits_only) > 11:
                    issues.append(f'{phone_type} phone too long ({digits_only})')
            
            # Check address
            address_text = address.address or "Address not provided"
            details['address'] = {
                'value': address_text,
                'length': len(address_text),
                'contains_special_chars': bool(re.search(r'[^\w\s\-.,()[\]]+', address_text))
            }
            if len(address_text) > 100:
                issues.append(f'Address too long ({len(address_text)} chars, max 100)')
            
            # Check city/government
            city_info = {}
            if address.government:
                from products.models import GOVERNMENT_CHOICES
                gov_dict = dict(GOVERNMENT_CHOICES)
                government_name = gov_dict.get(address.government, "Unknown")
                city_info['government'] = government_name
                
            if address.city:
                city_info['city'] = address.city
                
            full_city = f"{city_info.get('government', '')} - {city_info.get('city', '')}" if city_info.get('government') and city_info.get('city') else city_info.get('government', city_info.get('city', 'Cairo'))
            
            details['city'] = {
                'government': city_info.get('government', ''),
                'city_part': city_info.get('city', ''),
                'full_city': full_city,
                'length': len(full_city),
                'contains_special_chars': bool(re.search(r'[^\w\s\-.,()[\]]+', full_city))
            }
            
            if len(full_city) > 80:
                issues.append(f'City field too long ({len(full_city)} chars, max 80)')
            
            # Check customer ID
            customer_id = f"USER-{pill.user.id}"
            details['customerId'] = {
                'value': customer_id,
                'user_id': pill.user.id,
                'length': len(customer_id)
            }
            
            logger.info(f"📊 DIAGNOSIS RESULTS:")
            logger.info(f"  - Issues found: {len(issues)}")
            for issue in issues:
                logger.warning(f"    ⚠️ {issue}")
            
            logger.info(f"  - Customer details: {json.dumps(details, indent=2, default=str)}")
            
            return {
                'success': True,
                'has_issues': len(issues) > 0,
                'issues': issues,
                'details': details
            }
            
        except Exception as e:
            logger.error(f"Error diagnosing customer data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

# Global instance
khazenly_service = KhazenlyService()




