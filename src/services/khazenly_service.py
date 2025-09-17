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
        Validate order data against Khazenly requirements
        """
        try:
            issues = []
            order = order_data.get('Order', {})
            
            # Check city field length (max 80 characters)
            city = order.get('city', '')
            if city and len(city) > 80:
                issues.append(f"City field too long: {len(city)} chars (max 80)")
            
            # Check customer name length (Khazenly typically has limits)
            customer_name = order.get('customerName', '')
            if customer_name and len(customer_name) > 100:
                issues.append(f"Customer name too long: {len(customer_name)} chars (max 100)")
            
            # Check phone number format
            primary_tel = order.get('primaryTel', '')
            if primary_tel and (len(primary_tel) < 10 or len(primary_tel) > 15):
                issues.append(f"Primary phone number invalid length: {len(primary_tel)} chars")
            
            # Check line items - NOTE: lineItems is at root level, not inside Order
            line_items = order_data.get('lineItems', [])  # Changed from order.get to order_data.get
            if not line_items:
                issues.append("No line items found")
            else:
                for i, item in enumerate(line_items):
                    item_name = item.get('itemName', '')
                    if item_name and len(item_name) > 200:
                        issues.append(f"Line item {i+1} name too long: {len(item_name)} chars (max 200)")
            
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
                    "itemName": item_description,  # Use detailed product description with color/size
                    "price": discounted_price,  # Use discounted price
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
                
                # Remove special characters that might cause issues
                import re
                # Keep Arabic, English letters, numbers, spaces, and basic punctuation
                sanitized = re.sub(r'[^\w\s\-.,()[\]]+', '', str(text))
                
                # Limit length
                if len(sanitized) > max_length:
                    logger.warning(f"Truncating {field_name} from {len(sanitized)} to {max_length} characters")
                    sanitized = sanitized[:max_length].strip()
                
                return sanitized
            
            def validate_phone(phone):
                """Validate and sanitize phone number"""
                if not phone:
                    return ""
                
                # Remove non-digit characters
                import re
                digits_only = re.sub(r'\D', '', str(phone))
                
                # Egyptian phone validation - should be 10 or 11 digits
                if len(digits_only) < 10 or len(digits_only) > 11:
                    logger.warning(f"Invalid phone number length: {phone} -> {digits_only} ({len(digits_only)} digits)")
                    if len(digits_only) > 11:
                        # If too long, take the last 11 digits
                        digits_only = digits_only[-11:]
                    elif len(digits_only) < 10:
                        # If too short, pad with zeros (not ideal but prevents API error)
                        digits_only = digits_only.ljust(10, '0')
                
                # Ensure it starts with Egyptian country codes
                if digits_only and not (digits_only.startswith('01') or digits_only.startswith('201')):
                    # Add Egyptian mobile prefix if missing
                    if len(digits_only) == 9:
                        digits_only = '01' + digits_only
                
                return digits_only
            
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
                        f"{address.address or 'Address not provided'}, {address.city or 'City not provided'}", 
                        100, "address1"
                    ),  # Merged address and city for complete address info
                    "Address2": "",  # Fixed: Capital A for Address2
                    "Address3": "",  # Fixed: Capital A for Address3
                    "City": government_name,  
                    "Country": "Egypt",  # Fixed: Capital C for Country
                    "customerId": f"USER-{pill.user.id}"  # Use prefixed customer ID format
                },
                "lineItems": line_items
            }
            
            # Validate customer data before sending
            customer_data = order_data.get('Customer', {})
            logger.info(f"🔍 Customer data validation:")
            logger.info(f"  - customerName: '{customer_data.get('customerName')}' (len: {len(customer_data.get('customerName', ''))})")
            logger.info(f"  - Tel: '{customer_data.get('Tel')}' (len: {len(customer_data.get('Tel', ''))})")
            logger.info(f"  - SecondaryTel: '{customer_data.get('SecondaryTel')}' (len: {len(customer_data.get('SecondaryTel', ''))})")
            logger.info(f"  - Address1: '{customer_data.get('Address1')}' (len: {len(customer_data.get('Address1', ''))})")
            logger.info(f"  - City: '{customer_data.get('City')}' (len: {len(customer_data.get('City', ''))})")
            logger.info(f"  - Country: '{customer_data.get('Country')}' (len: {len(customer_data.get('Country', ''))})")
            logger.info(f"  - customerId: '{customer_data.get('customerId')}')")
            
            # Validate required fields
            validation_errors = []
            if not customer_data.get('customerName'):
                validation_errors.append("customerName is empty")
            if not customer_data.get('Tel'):
                validation_errors.append("Tel is empty")
            if not customer_data.get('Address1'):
                validation_errors.append("Address1 is empty")
            if not customer_data.get('City'):
                validation_errors.append("City is empty")
            if not customer_data.get('customerId'):
                validation_errors.append("customerId is empty")
                
            if validation_errors:
                error_msg = f"Customer data validation failed: {', '.join(validation_errors)}"
                logger.error(error_msg)
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
                        logger.error(f"  - tel: '{customer.get('tel')}' (type: {type(customer.get('tel'))}, len: {len(str(customer.get('tel', '')))})")
                        logger.error(f"  - secondaryTel: '{customer.get('secondaryTel')}' (type: {type(customer.get('secondaryTel'))}, len: {len(str(customer.get('secondaryTel', '')))})")
                        logger.error(f"  - address1: '{customer.get('address1')}' (type: {type(customer.get('address1'))}, len: {len(str(customer.get('address1', '')))})")
                        logger.error(f"  - city: '{customer.get('city')}' (type: {type(customer.get('city'))}, len: {len(str(customer.get('city', '')))})")
                        logger.error(f"  - customerId: '{customer.get('customerId')}' (type: {type(customer.get('customerId'))})")
                        
                        return {
                            'success': False, 
                            'error': f'Corrupted customer data detected. Pill ID: {pill.id}, User ID: {pill.user.id}. Please check customer address information for invalid characters or formatting issues. Details: {error_msg}'
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




