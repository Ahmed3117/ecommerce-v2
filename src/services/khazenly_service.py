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
        """
        try:
            issues = []
            order = order_data.get('Order', {})
            customer = order_data.get('Customer', {})
            
            # Check required order fields
            required_order_fields = ['orderId', 'orderNumber', 'storeName', 'totalAmount']
            for field in required_order_fields:
                if not order.get(field):
                    issues.append(f"Missing required order field: {field}")
            
            # Check required customer fields
            required_customer_fields = ['customerName', 'Tel', 'Address1', 'City', 'customerId']
            for field in required_customer_fields:
                if not customer.get(field):
                    issues.append(f"Missing required customer field: {field}")
            
            # Check city field length (max 80 characters)
            city = customer.get('City', '')
            if city and len(city) > 80:
                issues.append(f"City field too long: {len(city)} chars (max 80)")
            
            # Check customer name length
            customer_name = customer.get('customerName', '')
            if customer_name and len(customer_name) > 100:
                issues.append(f"Customer name too long: {len(customer_name)} chars (max 100)")
            
            # Check phone number format and length
            primary_tel = customer.get('Tel', '')
            if primary_tel:
                if len(primary_tel) > 20:
                    issues.append(f"Primary phone number too long: {len(primary_tel)} chars (max 20)")
                # Only check if phone starts with valid Egyptian mobile prefixes
                if not (primary_tel.startswith('010') or primary_tel.startswith('011') or 
                       primary_tel.startswith('012') or primary_tel.startswith('015')):
                    issues.append(f"Primary phone must start with 010, 011, 012, or 015. Got: {primary_tel}")
            
            secondary_tel = customer.get('SecondaryTel', '')
            if secondary_tel and secondary_tel != '':
                if len(secondary_tel) > 20:
                    issues.append(f"Secondary phone number too long: {len(secondary_tel)} chars (max 20)")
                # Only check if phone starts with valid Egyptian mobile prefixes
                if not (secondary_tel.startswith('010') or secondary_tel.startswith('011') or 
                       secondary_tel.startswith('012') or secondary_tel.startswith('015')):
                    issues.append(f"Secondary phone must start with 010, 011, 012, or 015. Got: {secondary_tel}")
            
            # Check address field length
            address1 = customer.get('Address1', '')
            if address1 and len(address1) > 255:
                issues.append(f"Address line 1 too long: {len(address1)} chars (max 255)")
            
            # Check line items
            line_items = order_data.get('lineItems', [])
            if not line_items:
                issues.append("No line items found")
            else:
                for i, item in enumerate(line_items):
                    item_name = item.get('itemName', '')
                    if item_name and len(item_name) > 200:
                        issues.append(f"Line item {i+1} name too long: {len(item_name)} chars (max 200)")
                    
                    # Check required line item fields
                    if not item.get('itemNumber'):
                        issues.append(f"Line item {i+1} missing itemNumber")
                    if not item.get('quantity'):
                        issues.append(f"Line item {i+1} missing quantity")
                    if not item.get('unitPrice'):
                        issues.append(f"Line item {i+1} missing unitPrice")
            
            # Government name validation
            if city:
                from products.models import GOVERNMENT_CHOICES
                valid_governments = [gov[1] for gov in GOVERNMENT_CHOICES]
                if city not in valid_governments:
                    issues.append(f"City/Government '{city}' is not a valid Egyptian government")
            
            if issues:
                logger.warning(f"⚠️ Order data validation issues found: {', '.join(issues)}")
                return {'valid': False, 'issues': issues}
            else:
                logger.info("✅ Order data validation passed")
                return {'valid': True, 'issues': []}
                
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
            
            for item in pill_items:
                product = item.product
                original_price = float(product.price) if product.price else 0
                discounted_price = float(product.discounted_price())
                item_discount = original_price - discounted_price
                
                total_product_price += discounted_price * item.quantity
                
                # Build detailed item description with color and size
                item_description = product.name
                description_parts = []
                
                # Add size if available
                if item.size:
                    description_parts.append(f"Size: {item.size}")
                
                # Add color if available
                if item.color:
                    description_parts.append(f"Color: {item.color.name}")
                
                # Combine description parts
                if description_parts:
                    item_description += f" ({', '.join(description_parts)})"
                
                # Ensure description doesn't exceed reasonable length (Khazenly might have limits)
                item_description = item_description[:150]  # Limit to 150 characters
                
                # Use logical product data for line items
                line_items.append({
                    "sku": product.product_number if product.product_number else f"PROD-{product.id}",  # Use product number as SKU
                    "itemNumber": product.product_number if product.product_number else f"PROD-{product.id}",  # Required: Item number
                    "itemName": item_description,  # Use detailed product description with color/size
                    "price": discounted_price,  # Use discounted price
                    "unitPrice": discounted_price,  # Required: Unit price (same as price)
                    "quantity": item.quantity,  # Item quantity
                    "discountAmount": item_discount,  # Actual discount on the product
                    "itemId": item.id  # Pill item ID
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
                """Sanitize text by removing invalid characters and limiting length"""
                if not text:
                    return ""
                
                # Remove special characters that might cause issues with Khazenly API
                import re
                # Keep Arabic characters, English letters, numbers, spaces, and basic punctuation
                # Arabic Unicode range: \u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF
                sanitized = re.sub(r'[^\w\s\-.,()\[\]\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+', '', str(text))
                
                # Remove any remaining control characters
                sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in '\n\r\t')
                
                # Ensure proper encoding for Khazenly API
                try:
                    sanitized = sanitized.encode('utf-8').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    # If encoding fails, fallback to ASCII with replacement
                    sanitized = sanitized.encode('ascii', 'replace').decode('ascii')
                    logger.warning(f"Encoding issues in {field_name}, using ASCII replacement")
                
                # Limit length
                if len(sanitized) > max_length:
                    logger.warning(f"Truncating {field_name} from {len(sanitized)} to {max_length} characters")
                    sanitized = sanitized[:max_length].strip()
                
                return sanitized
            
            def validate_phone(phone):
                """Process phone number for Khazenly API - remove +2/2 prefix if present"""
                if not phone:
                    return ""
                
                # Convert to string and strip whitespace
                phone_str = str(phone).strip()
                
                # Remove +2 or 2 prefix if present (Egyptian country code)
                if phone_str.startswith('+2'):
                    phone_str = phone_str[2:]  # Remove '+2'
                elif phone_str.startswith('2'):
                    phone_str = phone_str[1:]   # Remove '2'
                
                # Return the phone as-is after prefix removal
                # Khazenly expects Egyptian mobile numbers starting with 010, 011, 012, 015
                return phone_str
            
            # Get city and government separately for proper field mapping
            # City should be the actual city from pilladdress, government should be the government name
            city_name = ""
            government_name = ""
            
            # Get city from pilladdress
            logger.info(f"🔍 City processing debug:")
            logger.info(f"  - address.city: '{getattr(address, 'city', 'NOT_FOUND')}' (type: {type(getattr(address, 'city', None))})")
            logger.info(f"  - address.government: '{getattr(address, 'government', 'NOT_FOUND')}' (type: {type(getattr(address, 'government', None))})")
            
            if address.city:
                city_name = address.city[:80] if len(address.city) > 80 else address.city
                logger.info(f"✅ Using city from address: '{city_name}'")
                if len(address.city) > 80:
                    logger.warning(f"City field truncated from '{address.city}' to '{city_name}' for Khazenly")
            
            # Get government name from government choices
            if hasattr(address, 'government') and address.government:
                from products.models import GOVERNMENT_CHOICES
                gov_dict = dict(GOVERNMENT_CHOICES)
                government_name = gov_dict.get(address.government, "")
                logger.info(f"✅ Government found: '{government_name}' (code: {address.government})")
            else:
                logger.info("❌ No government found in address")
            
            # Fallback logic: if no city but has government, use government as city
            if not city_name and government_name:
                city_name = government_name
                logger.info(f"🔄 Using government '{government_name}' as city since no city specified")
            elif not city_name:
                city_name = "Cairo"  # Default fallback
                logger.warning("⚠️ No city or government found, using 'Cairo' as default")
            
            # Sanitize city and government names
            original_city = city_name
            city_name = sanitize_text(city_name, 80, "city")
            government_name = sanitize_text(government_name, 80, "government")
            
            logger.info(f"🔍 City sanitization:")
            logger.info(f"  - Original city: '{original_city}'")
            logger.info(f"  - Sanitized city: '{city_name}' (length: {len(city_name)})")
            logger.info(f"  - City bytes: {city_name.encode('utf-8') if city_name else 'None'}")
            logger.info(f"Final government for Khazenly: '{government_name}' (length: {len(government_name)})")
            
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
                    "Tel": validate_phone(primary_tel),  # Fixed: Capital T for Tel
                    "SecondaryTel": validate_phone(secondary_tel),  # Fixed: Capital S for SecondaryTel
                    "Address1": sanitize_text(
                        address.address or 'Address not provided', 
                        100, "address1"
                    ),  # Only address, city is sent separately in City field
                    "Address2": "",  # Fixed: Capital A for Address2
                    "Address3": "",  # Fixed: Capital A for Address3
                    "City": government_name,  # Khazenly expects government name in City field
                    "Country": "Egypt",  # Fixed: Capital C for Country
                    "customerId": f"USER-{pill.user.id}"  # Use prefixed customer ID format
                },
                "lineItems": line_items
            }
            
            # Enhanced customer data validation to prevent "corrupted customer data" errors
            customer_data = order_data.get('Customer', {})
            logger.info(f"🔍 Customer data validation:")
            logger.info(f"  - customerName: '{customer_data.get('customerName')}' (len: {len(customer_data.get('customerName', ''))})")
            logger.info(f"  - Tel: '{customer_data.get('Tel')}' (len: {len(customer_data.get('Tel', ''))})")
            logger.info(f"  - SecondaryTel: '{customer_data.get('SecondaryTel')}' (len: {len(customer_data.get('SecondaryTel', ''))})")
            logger.info(f"  - Address1: '{customer_data.get('Address1')}' (len: {len(customer_data.get('Address1', ''))})")
            logger.info(f"  - City: '{customer_data.get('City')}' (len: {len(customer_data.get('City', ''))})")
            logger.info(f"  - Country: '{customer_data.get('Country')}' (len: {len(customer_data.get('Country', ''))})")
            logger.info(f"  - customerId: '{customer_data.get('customerId')}')")
            
            # Comprehensive validation to prevent "corrupted customer data" and "wrong code" errors
            validation_errors = []
            
            # Required field checks
            required_fields = [
                ('customerName', "Customer name"),
                ('Tel', "Primary phone number"),
                ('Address1', "Address line 1"),
                ('City', "City/Government"),
                ('customerId', "Customer ID")
            ]
            
            for field, field_name in required_fields:
                value = customer_data.get(field, '')
                if not value or str(value).strip() == '':
                    validation_errors.append(f"{field_name} is empty")
            
            # Phone number format validation
            tel = customer_data.get('Tel', '')
            if tel and not (tel.startswith('010') or tel.startswith('011') or 
                           tel.startswith('012') or tel.startswith('015')):
                validation_errors.append(f"Primary phone must start with 010, 011, 012, or 015. Got: {tel}")
            
            secondary_tel = customer_data.get('SecondaryTel', '')
            if secondary_tel and secondary_tel != '':
                if not (secondary_tel.startswith('010') or secondary_tel.startswith('011') or 
                       secondary_tel.startswith('012') or secondary_tel.startswith('015')):
                    validation_errors.append(f"Secondary phone must start with 010, 011, 012, or 015. Got: {secondary_tel}")
            
            # Field length validation (based on Khazenly API limits)
            field_length_limits = [
                ('customerName', 100, "Customer name"),
                ('Tel', 20, "Primary phone"),
                ('SecondaryTel', 20, "Secondary phone"),
                ('Address1', 255, "Address line 1"),
                ('City', 80, "City/Government"),
                ('Country', 50, "Country")
            ]
            
            for field, max_length, field_name in field_length_limits:
                value = customer_data.get(field, '')
                if value and len(str(value)) > max_length:
                    validation_errors.append(f"{field_name} exceeds {max_length} characters (got {len(str(value))})")
            
            # Note: Removed special character validation - let Khazenly API handle character validation
            # This allows any address format that Khazenly accepts
            
            # Government name validation (must match Khazenly expected values)
            city = customer_data.get('City', '')
            if city:
                from products.models import GOVERNMENT_CHOICES
                valid_governments = [gov[1] for gov in GOVERNMENT_CHOICES]
                if city not in valid_governments:
                    validation_errors.append(f"City/Government '{city}' is not a valid Egyptian government")
            
            if validation_errors:
                error_msg = f"Customer data validation failed: {', '.join(validation_errors)}"
                logger.error(f"❌ {error_msg}")
                
                # Log detailed customer data for debugging corrupted data issues
                logger.error(f"🚨 CORRUPTED CUSTOMER DATA PREVENTION - Detailed dump:")
                for field, value in customer_data.items():
                    logger.error(f"  {field}: '{value}' (type: {type(value)}, len: {len(str(value)) if value else 0})")
                
                return {
                    'success': False,
                    'error': error_msg
                }
            
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
            
            # Validate order data before sending
            validation_result = self.validate_order_data(order_data)
            if not validation_result['valid']:
                error_msg = f"Order validation failed: {', '.join(validation_result['issues'])}"
                logger.error(f"❌ {error_msg}")
                logger.error(f"❌ Order data structure: Order keys={list(order_data.get('Order', {}).keys())}, Root keys={list(order_data.keys())}")
                return {'success': False, 'error': error_msg}
            
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
                        logger.error(f"  - Tel: '{customer.get('Tel')}' (type: {type(customer.get('Tel'))}, len: {len(str(customer.get('Tel', '')))})")
                        logger.error(f"  - SecondaryTel: '{customer.get('SecondaryTel')}' (type: {type(customer.get('SecondaryTel'))}, len: {len(str(customer.get('SecondaryTel', '')))})")
                        logger.error(f"  - Address1: '{customer.get('Address1')}' (type: {type(customer.get('Address1'))}, len: {len(str(customer.get('Address1', '')))})")
                        logger.error(f"  - City: '{customer.get('City')}' (type: {type(customer.get('City'))}, len: {len(str(customer.get('City', '')))})")
                        logger.error(f"  - Country: '{customer.get('Country')}' (type: {type(customer.get('Country'))}, len: {len(str(customer.get('Country', '')))})")
                        logger.error(f"  - customerId: '{customer.get('customerId')}' (type: {type(customer.get('customerId'))})")
                        
                        # Log the actual JSON that was sent to Khazenly for debugging
                        try:
                            customer_json = json.dumps(customer, ensure_ascii=False, indent=2)
                            logger.error(f"🚨 CUSTOMER JSON SENT TO KHAZENLY:")
                            logger.error(customer_json)
                        except Exception as json_error:
                            logger.error(f"Failed to serialize customer data: {json_error}")
                        
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
                    error_msg = error_data.get('message', error_data.get('error', f'HTTP {response.status_code}'))
                except:
                    error_msg = f'HTTP {response.status_code}: {response.text[:200]}...' if len(response.text) > 200 else response.text
                
                return {'success': False, 'error': f'Khazenly API error: {error_msg}'}
                
        except Exception as e:
            logger.error(f"Exception creating Khazenly order: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}

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




