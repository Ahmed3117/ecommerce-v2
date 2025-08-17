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
        
        # FIXED: Use the correct store name as provided by Khazenly
        self.store_name = "https://bookefay.com"  # Updated from BOOKIFAY
        
        # FIXED: Use the correct user email for order creation
        self.order_user_email = "mohamedaymab26@gmail.com"  # Not the API user
        
        # Updated tokens from successful authentication
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
            
            for item in pill.items.all():
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
            secondary_phones = [phone for phone in unique_phones if phone != primary_tel]
            secondary_tel = " | ".join(secondary_phones) if secondary_phones else ""
            
            # Get proper city name from government choices
            city_name = "Cairo"  # Default fallback
            if hasattr(address, 'government') and address.government:
                from products.models import GOVERNMENT_CHOICES
                gov_dict = dict(GOVERNMENT_CHOICES)
                government_name = gov_dict.get(address.government, "Cairo")
                city_part = address.city if address.city else ""
                if city_part:
                    city_name = f"{government_name} - {city_part}"
                else:
                    city_name = government_name
            elif address.city:
                city_name = address.city
            
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
            
            # FIXED: Use correct API endpoint from Postman collection
            api_url = f"{self.base_url}/services/apexrest/api/CreateOrder"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            logger.info(f"Making order request to: {api_url}")
            logger.info(f"Order data: {json.dumps(order_data, indent=2)}")
            
            response = requests.post(api_url, json=order_data, headers=headers, timeout=60)
            
            logger.info(f"Khazenly order response status: {response.status_code}")
            logger.info(f"Khazenly order response: {response.text}")
            
            if response.status_code == 200:
                response_data = response.json()
                
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
                    error_msg = response_data.get('message', 'Unknown error from Khazenly')
                    logger.error(f"Khazenly order creation failed: {error_msg}")
                    return {'success': False, 'error': error_msg}
            else:
                logger.error(f"HTTP error creating Khazenly order: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
                
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