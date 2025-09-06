import requests
import json
import logging
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
            # Collect all available phone numbers without duplicates
            phone_numbers = []
            
            # Collect phone numbers from different sources
            if address.phone:
                phone_numbers.append(address.phone)
            if hasattr(pill.user, 'phone') and pill.user.phone:
                phone_numbers.append(pill.user.phone)
            if hasattr(pill.user, 'phone2') and pill.user.phone2:
                phone_numbers.append(pill.user.phone2)
            
            # Remove duplicates while preserving order
            unique_phones = []
            for phone in phone_numbers:
                if phone not in unique_phones:
                    unique_phones.append(phone)
            
            # Set primary tel as address.phone (if available), otherwise use first unique phone
            primary_tel = address.phone if address.phone else (unique_phones[0] if unique_phones else "")
            
            # For secondaryTel, get other unique phones excluding the primary tel
            # secondary_phones = [phone for phone in unique_phones if phone != primary_tel]
            # For secondaryTel, use the first unique phone if it's different from primary_tel,
            # otherwise use the second unique phone if available
            if unique_phones:
                if unique_phones[0] != primary_tel:
                    secondary_tel = unique_phones[0]
                elif len(unique_phones) > 1:
                    secondary_tel = unique_phones[1]
                else:
                    secondary_tel = ""
            else:
                secondary_tel = ""
            
            # Get proper city name from government choices
            city_name = "Cairo"  # Default fallback
            if hasattr(address, 'government') and address.government:
                from products.models import GOVERNMENT_CHOICES
                gov_dict = dict(GOVERNMENT_CHOICES)
                government_name = gov_dict.get(address.government, "Cairo")
                city_part = address.city if address.city else ""
                if city_part:
                    # Combine government and city, but ensure it doesn't exceed Khazenly's 80-character limit
                    full_city = f"{government_name} - {city_part}"
                    if len(full_city) > 80:
                        # If too long, truncate the city part but keep the government name
                        max_city_length = 80 - len(government_name) - 3  # 3 for " - "
                        if max_city_length > 0:
                            truncated_city = city_part[:max_city_length].strip()
                            city_name = f"{government_name} - {truncated_city}"
                            logger.warning(f"City field truncated from '{full_city}' to '{city_name}' for Khazenly (max 80 chars)")
                        else:
                            # If government name itself is too long, just use it
                            city_name = government_name[:80]
                            logger.warning(f"Using only government name '{city_name}' due to length constraints")
                    else:
                        city_name = full_city
                else:
                    city_name = government_name
            elif address.city:
                # Ensure even standalone city doesn't exceed 80 characters
                city_name = address.city[:80] if len(address.city) > 80 else address.city
                if len(address.city) > 80:
                    logger.warning(f"City field truncated from '{address.city}' to '{city_name}' for Khazenly")
            
            logger.info(f"Final city name for Khazenly: '{city_name}' (length: {len(city_name)})")
            
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
                    "customerName": (address.name or f"Customer {pill.user.username}")[:50],  # Limit name length
                    "tel": primary_tel,  # Primary phone (address.phone or first available)
                    "secondaryTel": secondary_tel,  # Other unique phones separated by " | "
                    "address1": (address.address or "Address not provided")[:100],  # Limit address length
                    "address2": "",
                    "address3": "",
                    "city": city_name,
                    "country": "Egypt",
                    "customerId": f"USER-{pill.user.id}"  # Use prefixed customer ID format
                },
                "lineItems": line_items
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
                    if "STRING_TOO_LONG" in error_msg:
                        if "City" in error_msg:
                            return {'success': False, 'error': 'Address city field is too long. Please use a shorter address.'}
                        else:
                            return {'success': False, 'error': 'One of the address fields is too long. Please shorten your address details.'}
                    elif "REQUIRED_FIELD_MISSING" in error_msg:
                        return {'success': False, 'error': 'Required field missing. Please ensure all address information is complete.'}
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

# Global instance
khazenly_service = KhazenlyService()