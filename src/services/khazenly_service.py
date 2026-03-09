import requests
import json
import logging
import re
import copy
import unicodedata
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class KhazenlyService:
    def __init__(self):
        self.base_url = settings.KHAZENLY_BASE_URL
        self.client_id = settings.KHAZENLY_CLIENT_ID
        self.client_secret = settings.KHAZENLY_CLIENT_SECRET
        self.store_name = settings.KHAZENLY_STORE_NAME
        self.order_user_email = settings.KHAZENLY_ORDER_USER_EMAIL
        self.refresh_token = settings.KHAZENLY_REFRESH_TOKEN
        self.consignee_prefix = getattr(settings, 'KHAZENLY_CONSIGNEE_PREFIX', 'BOOKIFAY')

        # Cache keys
        self.access_token_cache_key = 'khazenly_access_token'
        self.token_expiry_cache_key = 'khazenly_token_expiry'

    # ------------------------------------------------------------------
    #  Authentication
    # ------------------------------------------------------------------

    def get_access_token(self):
        """Get valid access token, refresh if needed."""
        try:
            cached_token = cache.get(self.access_token_cache_key)
            token_expiry = cache.get(self.token_expiry_cache_key)

            if cached_token and token_expiry:
                if datetime.now() < token_expiry:
                    return cached_token

            logger.info("Refreshing Khazenly access token...")

            token_url = f"{self.base_url}/selfservice/services/oauth2/token"

            token_data = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token,
            }

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            }

            response = requests.post(token_url, data=token_data, headers=headers, timeout=30)

            logger.info(f"Token response status: {response.status_code}")

            if response.status_code == 200:
                token_response = response.json()
                access_token = token_response.get('access_token')

                if access_token:
                    expiry_time = datetime.now() + timedelta(hours=1, minutes=50)
                    cache.set(self.access_token_cache_key, access_token, timeout=6600)
                    cache.set(self.token_expiry_cache_key, expiry_time, timeout=6600)
                    logger.info("Access token refreshed and cached successfully")
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

    # ------------------------------------------------------------------
    #  Text / phone sanitization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize_text(text, max_length, field_name="field"):
        """
        Sanitize text for Khazenly API:
        - Normalize Unicode (NFC)
        - Remove zero-width / invisible characters
        - Remove control characters
        - Collapse whitespace
        - Truncate to max_length on a word boundary
        """
        if not text:
            return ""

        sanitized = str(text).strip()
        sanitized = unicodedata.normalize('NFC', sanitized)

        # Remove zero-width and bidi control characters
        _invisible = re.compile(
            r'[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\ufffe]+'
        )
        sanitized = _invisible.sub('', sanitized)

        # Remove control chars except basic whitespace
        sanitized = "".join(ch for ch in sanitized if ord(ch) >= 32 or ch in "\n\r\t")
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()

        # Safe UTF-8 round-trip
        try:
            sanitized = sanitized.encode('utf-8').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            sanitized = sanitized.encode('utf-8', 'ignore').decode('utf-8')
            logger.warning(f"Encoding issues in {field_name}, removed problematic characters")

        if len(sanitized) > max_length:
            logger.warning(f"Truncating {field_name} from {len(sanitized)} to {max_length} chars")
            sanitized = sanitized[:max_length].strip()
            last_space = sanitized.rfind(' ')
            if last_space > max_length * 0.8:
                sanitized = sanitized[:last_space].strip()

        return sanitized

    @staticmethod
    def validate_phone(phone):
        """
        Clean and validate an Egyptian mobile number.
        Returns 11-digit string (01XXXXXXXXX) or empty string if invalid.
        """
        if not phone:
            return ""

        phone_str = re.sub(r'[^\d+]', '', str(phone).strip())

        # Strip country code prefix
        if phone_str.startswith('+2'):
            phone_str = phone_str[2:]
        elif phone_str.startswith('2') and len(phone_str) > 11:
            phone_str = phone_str[1:]

        valid_prefixes = ('010', '011', '012', '015')
        if not phone_str.startswith(valid_prefixes):
            logger.warning(f"Phone '{phone}' invalid prefix - rejected")
            return ""

        if len(phone_str) < 11:
            logger.warning(f"Phone '{phone}' too short ({len(phone_str)} digits) - rejected")
            return ""

        if len(phone_str) > 11:
            phone_str = phone_str[:11]

        if not phone_str.isdigit():
            logger.warning(f"Phone '{phone_str}' contains non-digits - rejected")
            return ""

        return phone_str

    @staticmethod
    def sanitize_item_name(text):
        """Remove emojis / special chars from product name for Khazenly."""
        if not text:
            return ""
        sanitized = str(text).strip()
        sanitized = re.sub(
            r'[^\w\s\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF'
            r'\uFB50-\uFDFF\uFE70-\uFEFF.,\-()]+', ' ', sanitized
        )
        return re.sub(r'\s+', ' ', sanitized).strip()

    def sanitize_for_khazenly(self, text, max_length=None):
        """Convenience wrapper kept for backward-compat."""
        return self.sanitize_text(text, max_length or 255, "field")

    # ------------------------------------------------------------------
    #  Customer ID helper
    # ------------------------------------------------------------------

    def build_customer_id(self, validated_phone):
        """
        Build the Khazenly Consignee Code for a customer.

        Khazenly auto-generates codes in the format {STORE_PREFIX}-{phone}
        (e.g. BOOKIFAY-01000003102).  By sending the SAME format as
        customerId we ensure:
        * Returning customers are matched - no DUPLICATES_DETECTED error.
        * New customers are created with a predictable code.
        """
        if not validated_phone:
            return None
        return f"{self.consignee_prefix}-{validated_phone}"

    # ------------------------------------------------------------------
    #  Validation
    # ------------------------------------------------------------------

    def validate_order_data(self, order_data):
        """
        Comprehensive validation of order data against Khazenly requirements.
        Returns dict with 'valid', 'issues', and 'summary' keys.
        """
        try:
            issues = []
            order = order_data.get('Order', {})
            customer = order_data.get('Customer', {})

            # Required order fields
            for field in ('orderId', 'orderNumber', 'storeName', 'totalAmount'):
                if not order.get(field):
                    issues.append(f"Missing required order field: {field}")

            # Required customer fields
            for field in ('customerName', 'Tel', 'Address1', 'City'):
                if not customer.get(field):
                    issues.append(f"Missing required customer field: {field}")

            city = customer.get('City', '')
            if city and len(city) > 80:
                issues.append(f"City too long: '{city}' ({len(city)}/80 chars)")

            customer_name = customer.get('customerName', '')
            if customer_name and len(customer_name) > 100:
                issues.append(f"Customer name too long ({len(customer_name)}/100 chars)")

            primary_tel = customer.get('Tel', '')
            if primary_tel:
                if len(primary_tel) > 20:
                    issues.append(f"Primary phone too long ({len(primary_tel)}/20)")
                if not primary_tel.startswith(('010', '011', '012', '015')):
                    issues.append(f"Primary phone invalid prefix: '{primary_tel}'")

            secondary_tel = customer.get('secondaryTel', '') or customer.get('SecondaryTel', '')
            if secondary_tel:
                if len(secondary_tel) > 20:
                    issues.append(f"Secondary phone too long ({len(secondary_tel)}/20)")
                if not secondary_tel.startswith(('010', '011', '012', '015')):
                    issues.append(f"Secondary phone invalid prefix: '{secondary_tel}'")

            address1 = customer.get('Address1', '')
            if address1 and len(address1) > 255:
                issues.append(f"Address too long ({len(address1)}/255)")

            line_items = order_data.get('lineItems', [])
            if not line_items:
                issues.append("No products found in order")
            else:
                for i, item in enumerate(line_items):
                    n = i + 1
                    name = item.get('ItemName', '')
                    if name and len(name) > 200:
                        issues.append(f"Product {n} name too long ({len(name)}/200)")
                    if not item.get('SKU'):
                        issues.append(f"Product {n} missing SKU")
                    if not item.get('Quantity'):
                        issues.append(f"Product {n} missing quantity")
                    if not item.get('Price'):
                        issues.append(f"Product {n} missing price")

            # City must be in Khazenly's supported list
            if city:
                if city not in self._supported_cities():
                    available = ', '.join(self._supported_cities()[:8]) + '...'
                    issues.append(f"City '{city}' not supported. Available: {available}")

            if issues:
                summary = f"Validation failed ({len(issues)} issues): " + "; ".join(issues[:3])
                if len(issues) > 3:
                    summary += f" ... and {len(issues) - 3} more"
                return {'valid': False, 'issues': issues, 'summary': summary}

            return {'valid': True, 'issues': [], 'summary': 'Validation passed'}

        except Exception as e:
            logger.error(f"Error validating order data: {e}")
            return {'valid': False, 'issues': [f'Validation error: {e}']}

    # ------------------------------------------------------------------
    #  Static data
    # ------------------------------------------------------------------

    @staticmethod
    def _supported_cities():
        return [
            'Alexandria', 'Assiut', 'Aswan', 'Bani-Sweif', 'Behera', 'Cairo',
            'Dakahleya', 'Damietta', 'Fayoum', 'Giza', 'Hurghada', 'Ismailia',
            'Luxor', 'Mahalla', 'Mansoura', 'Marsa Matrouh', 'Menya', 'Monefeya',
            'North Coast', 'Port-Said', 'Qalyubia', 'Qena', 'Red Sea', 'Sharkeya',
            'Sohag', 'Suez', 'Tanta', 'Zagazig', 'Gharbeya', 'Kafr El Sheikh',
            'Al-Wadi Al-Gadid', 'Sharm El Sheikh', 'North Sinai', 'South Sinai',
        ]

    @staticmethod
    def _government_to_city():
        return {
            '1': 'Cairo', '2': 'Alexandria', '3': 'Kafr El Sheikh',
            '4': 'Dakahleya', '5': 'Sharkeya', '6': 'Gharbeya',
            '7': 'Monefeya', '8': 'Qalyubia', '9': 'Giza',
            '10': 'Bani-Sweif', '11': 'Fayoum', '12': 'Menya',
            '13': 'Assiut', '14': 'Sohag', '15': 'Qena',
            '16': 'Luxor', '17': 'Aswan', '18': 'Red Sea',
            '19': 'Behera', '20': 'Ismailia', '21': 'Suez',
            '22': 'Port-Said', '23': 'Damietta', '24': 'Marsa Matrouh',
            '25': 'Al-Wadi Al-Gadid', '26': 'North Sinai', '27': 'South Sinai',
        }

    # ------------------------------------------------------------------
    #  Internal: send order to Khazenly API (single attempt)
    # ------------------------------------------------------------------

    def _send_order_request(self, api_url, headers, order_data):
        """
        Make a single POST to CreateOrder.
        Returns (response_obj | None, error_string | None).
        """
        try:
            response = requests.post(api_url, json=order_data, headers=headers, timeout=60)
            return response, None
        except requests.exceptions.Timeout:
            return None, 'Khazenly API request timed out (60s). Please try again later.'
        except requests.exceptions.ConnectionError as exc:
            return None, f'Could not connect to Khazenly API: {exc}'
        except requests.exceptions.RequestException as exc:
            return None, f'Network error: {exc}'

    def _parse_success(self, response_data):
        """Extract order info from a successful Khazenly response."""
        order_info = response_data.get('order', {})
        return {
            'success': True,
            'data': {
                'khazenly_order_id': order_info.get('id'),
                'sales_order_number': order_info.get('salesOrderNumber'),
                'order_number': order_info.get('orderNumber'),
                'line_items': response_data.get('lineItems', []),
                'customer': response_data.get('customer', {}),
                'raw_response': response_data,
            },
        }

    # ------------------------------------------------------------------
    #  CREATE ORDER  -  main public method
    # ------------------------------------------------------------------

    def create_order(self, pill):
        """
        Create an order in Khazenly for the given Pill.

        Key design decisions (March 2026 rewrite):
        1. **Deterministic orderId** - always pill_number (no timestamps).
           This means re-sends are idempotent from Khazenly's perspective.
        2. **Always send customerId** - formatted as {PREFIX}-{phone} so
           returning customers are matched, not duplicated.
        3. **No phone-swap retries** - swapping secondary->primary created
           garbage customer records.  Instead, for "corrupted customer" errors
           we retry once with cleaned data and clear secondaryTel.  If that
           still fails the admin must contact Khazenly support.
        4. **Pre-flight duplicate check** - query Khazenly for existing order
           by orderNumber before creating, to avoid double-sends.
        """
        try:
            logger.info(f"Creating Khazenly order for pill {pill.pill_number}")

            # 1. Access token
            access_token = self.get_access_token()
            if not access_token:
                return {'success': False, 'error': 'Failed to get Khazenly access token'}

            # 2. Validate pill has address
            if not hasattr(pill, 'pilladdress'):
                return {'success': False, 'error': 'Pill address information missing'}
            address = pill.pilladdress

            # 3. Pre-flight: check if this order already exists in Khazenly
            existing = self.check_order_exists(pill.pill_number)
            if existing and existing.get('salesOrderNumber'):
                logger.info(
                    f"Order {pill.pill_number} already exists in Khazenly "
                    f"as {existing.get('salesOrderNumber')} - returning existing data"
                )
                return {
                    'success': True,
                    'data': {
                        'khazenly_order_id': existing.get('id'),
                        'sales_order_number': existing.get('salesOrderNumber'),
                        'order_number': existing.get('orderNumber'),
                        'already_exists': True,
                        'message': 'Order already exists in Khazenly (pre-flight check)',
                    },
                }

            # 4. Prepare line items
            line_items = []
            total_product_price = 0
            pill_items = pill.items.all()
            logger.info(f"Processing pill {pill.pill_number}: {len(pill_items)} items")

            for item in pill_items:
                product = item.product
                original_price = float(product.price) if product.price else 0
                discounted_price = float(product.discounted_price())
                item_discount = original_price - discounted_price
                total_product_price += discounted_price * item.quantity

                description = self.sanitize_item_name(product.name)
                parts = []
                if item.size:
                    parts.append(f"Size: {item.size}")
                if item.color:
                    parts.append(f"Color: {self.sanitize_item_name(item.color.name)}")
                if parts:
                    description += f" ({', '.join(parts)})"
                description = description[:150]

                line_items.append({
                    "SKU": product.product_number or f"PROD-{product.id}",
                    "ItemName": description,
                    "Price": discounted_price,
                    "Quantity": item.quantity,
                    "DiscountAmount": item_discount if item_discount > 0 else None,
                    "ItemId": str(item.id),
                })

            if not line_items:
                return {'success': False, 'error': f'No line items for pill {pill.pill_number}'}

            # 5. Calculate amounts
            shipping_fees = float(pill.shipping_price())
            gift_discount = float(pill.calculate_gift_discount())
            coupon_discount = float(pill.coupon_discount) if pill.coupon_discount else 0
            total_discount = gift_discount + coupon_discount
            total_amount = total_product_price + shipping_fees - total_discount

            # 6. Phone numbers
            primary_tel = self.validate_phone(address.phone) if address.phone else ""

            # Secondary phone priority: user.phone -> user.phone2 -> user.parent_phone
            # Skip any phone identical to primary.
            secondary_tel = ""
            primary_normalized = primary_tel  # already clean 11 digits or ""

            for attr in ('phone', 'phone2', 'parent_phone'):
                candidate_raw = getattr(pill.user, attr, None)
                if not candidate_raw:
                    continue
                candidate = self.validate_phone(candidate_raw)
                if candidate and candidate != primary_normalized:
                    secondary_tel = candidate
                    logger.info(f"Using user.{attr} as secondary phone: {secondary_tel}")
                    break

            # 7. Resolve city from government code
            khazenly_city = ""
            if hasattr(address, 'government') and address.government:
                khazenly_city = self._government_to_city().get(address.government, '')
                if not khazenly_city:
                    from products.models import GOVERNMENT_CHOICES
                    khazenly_city = dict(GOVERNMENT_CHOICES).get(address.government, 'Cairo')
            if not khazenly_city:
                khazenly_city = "Cairo"

            if khazenly_city not in self._supported_cities():
                logger.warning(f"City '{khazenly_city}' not supported - falling back to Cairo")
                khazenly_city = "Cairo"

            # 8. Build customer ID  (PREFIX-phone)
            customer_id = self.build_customer_id(primary_tel)

            # 9. Build order payload
            # IMPORTANT: orderId is ALWAYS pill_number (deterministic, no timestamp)
            order_data = {
                "Order": {
                    "orderId": str(pill.pill_number),
                    "orderNumber": pill.pill_number,
                    "storeName": self.store_name,
                    "totalAmount": total_amount,
                    "shippingFees": shipping_fees,
                    "discountAmount": total_discount,
                    "taxAmount": 0,
                    "invoiceTotalAmount": total_amount,
                    "weight": 0,
                    "noOfBoxes": 1,
                    "paymentMethod": "Pre-Paid",
                    "paymentStatus": "paid",
                    "storeCurrency": "EGP",
                    "isPickedByMerchant": False,
                    "merchantAWB": "",
                    "merchantCourier": "",
                    "merchantAwbDocument": "",
                    "additionalNotes": (
                        f"Prepaid order - pill {pill.pill_number} - "
                        f"{len(line_items)} items - Payment via website"
                    ),
                },
                "Customer": {
                    "customerName": self.sanitize_text(
                        address.name or f"Customer {pill.user.username}", 50, "customerName"
                    ),
                    "customerId": customer_id,
                    "Tel": primary_tel,
                    "secondaryTel": secondary_tel,
                    "Address1": self.sanitize_text(
                        address.address or 'Address not provided', 100, "address1"
                    ),
                    "Address2": "",
                    "Address3": "",
                    "City": khazenly_city,
                    "Country": "Egypt",
                },
                "lineItems": line_items,
            }

            # 10. Pre-send validation
            validation = self.validate_order_data(order_data)
            if not validation['valid']:
                summary = validation.get('summary', 'Validation failed')
                issues_list = validation.get('issues', [])
                admin_msg = (
                    f"KHAZENLY VALIDATION FAILED\n\n{summary}\n\n"
                    + "\n".join(f"- {i}" for i in issues_list[:10])
                    + f"\n\nPill #{pill.pill_number}"
                )
                return {'success': False, 'error': admin_msg}

            # 11. Send to Khazenly
            api_url = f"{self.base_url}/services/apexrest/api/CreateOrder"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }

            logger.info(f"Sending order to Khazenly: orderId={order_data['Order']['orderId']}")
            logger.info(f"Customer: {order_data['Customer']['customerName']}, "
                        f"Tel: {order_data['Customer']['Tel']}, "
                        f"customerId: {order_data['Customer'].get('customerId')}")

            response, net_error = self._send_order_request(api_url, headers, order_data)
            if net_error:
                return {'success': False, 'error': net_error}

            # 12. Handle response
            return self._handle_create_response(
                response, order_data, api_url, headers, pill
            )

        except Exception as e:
            logger.error(f"Exception creating Khazenly order: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------------
    #  Response handling (extracted for clarity)
    # ------------------------------------------------------------------

    def _handle_create_response(self, response, order_data, api_url, headers, pill):
        """
        Process the Khazenly CreateOrder response.
        Handles success, known error codes, and retry logic.
        """
        logger.info(f"Khazenly response: {response.status_code} - {response.text[:500]}")

        # ----- HTTP 200 (could still be a logical error) ------------------
        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError:
                return {'success': False, 'error': 'Invalid JSON from Khazenly API'}

            if data.get('resultCode') == 0:
                logger.info("Khazenly order created successfully")
                return self._parse_success(data)

            # Logical error inside a 200 response
            error_msg = data.get('result', data.get('message', 'Unknown Khazenly error'))
            result_code = data.get('resultCode', '?')
            logger.error(f"Khazenly resultCode={result_code}: {error_msg}")

            return self._handle_logical_error(
                error_msg, order_data, api_url, headers, pill
            )

        # ----- HTTP non-200 -----------------------------------------------
        logger.error(f"HTTP {response.status_code} from Khazenly")
        try:
            error_data = response.json()
            error_msg = error_data.get(
                'result', error_data.get('message',
                error_data.get('error', f'HTTP {response.status_code}'))
            )
        except Exception:
            error_msg = response.text[:300] if response.text else f'HTTP {response.status_code}'

        # Check for DUPLICATES_DETECTED at HTTP level
        if "DUPLICATES_DETECTED" in str(error_msg) or "Consignee Code already exists" in str(error_msg):
            return self._handle_duplicate_customer(error_msg, order_data, api_url, headers, pill)

        return {'success': False, 'error': f'Khazenly API error: {error_msg}'}

    def _handle_logical_error(self, error_msg, order_data, api_url, headers, pill):
        """Handle a logical (resultCode != 0) error from Khazenly."""

        lower = error_msg.lower()

        # ---- Corrupted customer data / wrong code ----
        if any(kw in lower for kw in ('corrupted customer data', 'wrong code', 'corpted')):
            return self._handle_corrupted_customer(
                error_msg, order_data, api_url, headers, pill
            )

        # ---- DUPLICATES_DETECTED ----
        if "DUPLICATES_DETECTED" in error_msg or "Consignee Code already exists" in error_msg:
            return self._handle_duplicate_customer(
                error_msg, order_data, api_url, headers, pill
            )

        # ---- STRING_TOO_LONG ----
        if "STRING_TOO_LONG" in error_msg:
            if "City" in error_msg:
                return {'success': False, 'error': 'City field too long for Khazenly.'}
            return {'success': False, 'error': 'A field is too long for Khazenly. Shorten address details.'}

        if "REQUIRED_FIELD_MISSING" in error_msg:
            return {'success': False, 'error': 'Required field missing. Check address info is complete.'}

        return {'success': False, 'error': f'Khazenly error: {error_msg}'}

    # ------------------------------------------------------------------
    #  Corrupted-customer retry (NO phone swap)
    # ------------------------------------------------------------------

    def _handle_corrupted_customer(self, original_error, order_data, api_url, headers, pill):
        """
        "Corrupted customer data / wrong code" means the customer record
        stored in Khazenly (matched by phone) is broken.

        Retry strategy (3 attempts total):
        1. Original request already failed.
        2. Retry with cleaned data (secondaryTel cleared, strict sanitization),
           same customerId.
        3. Retry with customerId=null — lets Khazenly bypass the corrupted
           record and auto-create a new customer entry.

        Keep the SAME orderId throughout (deterministic, no timestamp).
        Keep the SAME primary phone — do NOT swap to secondary.

        If all retries fail -> return a clear message for admin to contact
        Khazenly support to fix the customer record.
        """
        logger.warning(f"Corrupted customer for pill {pill.pill_number} - retrying with cleaned data")

        retry_data = copy.deepcopy(order_data)

        # Strip secondaryTel completely (both casing variants)
        retry_data['Customer']['secondaryTel'] = ""
        retry_data['Customer'].pop('SecondaryTel', None)

        # Extra-strict sanitization
        for field in ('customerName', 'Address1'):
            val = retry_data['Customer'].get(field, '')
            if val:
                clean = unicodedata.normalize('NFC', str(val).strip())
                clean = re.sub(
                    r'[^\w\s\u0600-\u06FF\u0750-\u077F.,\-()]+', ' ', clean
                )
                clean = re.sub(r'\s+', ' ', clean).strip()
                retry_data['Customer'][field] = clean

        # ----- Retry 1: cleaned data, same customerId ---------------------
        logger.info(f"Retry 1 - Tel: {retry_data['Customer']['Tel']}, "
                    f"secondaryTel cleared, customerId: {retry_data['Customer'].get('customerId')}")

        response, net_err = self._send_order_request(api_url, headers, retry_data)
        if net_err:
            return {'success': False, 'error': net_err}

        if response.status_code == 200:
            try:
                rdata = response.json()
            except json.JSONDecodeError:
                rdata = {}

            if rdata.get('resultCode') == 0:
                logger.info("Corrupted-customer retry 1 succeeded (secondaryTel cleared)")
                result = self._parse_success(rdata)
                result['data']['retry_note'] = 'Succeeded after clearing secondaryTel'
                return result

        # ----- Retry 2: customerId=null to bypass corrupted record ---------
        # The corrupted record in Khazenly is matched by our customerId.
        # Sending null lets Khazenly auto-create a fresh customer entry,
        # bypassing the broken record.
        logger.warning(
            f"Retry 1 failed for pill {pill.pill_number} - "
            f"trying with customerId=null to bypass corrupted record"
        )
        retry_data2 = copy.deepcopy(retry_data)
        retry_data2['Customer']['customerId'] = None

        response2, net_err2 = self._send_order_request(api_url, headers, retry_data2)
        if net_err2:
            return {'success': False, 'error': net_err2}

        if response2.status_code == 200:
            try:
                rdata2 = response2.json()
            except json.JSONDecodeError:
                rdata2 = {}

            if rdata2.get('resultCode') == 0:
                logger.info(
                    "Corrupted-customer retry 2 succeeded "
                    "(customerId=null bypassed corrupted record)"
                )
                result = self._parse_success(rdata2)
                result['data']['retry_note'] = (
                    'Succeeded with customerId=null (corrupted record bypassed). '
                    'Customer record in Khazenly may need cleanup.'
                )
                return result

            # Log what Khazenly returned on the second retry
            retry2_error = rdata2.get('result', rdata2.get('message', 'Unknown'))
            logger.error(f"Retry 2 also failed: {retry2_error}")

        # All retries exhausted
        primary_phone = order_data['Customer'].get('Tel', '?')
        cust_id = order_data['Customer'].get('customerId', '?')
        return {
            'success': False,
            'error': (
                f"Customer record for phone {primary_phone} (ID: {cust_id}) is "
                f"CORRUPTED in Khazenly and cannot be used.\n\n"
                f"ACTION REQUIRED: Contact Khazenly support and ask them to "
                f"fix or delete the customer record '{cust_id}' in their system.\n\n"
                f"Original error: {original_error}"
            ),
        }

    # ------------------------------------------------------------------
    #  Duplicate-customer handler
    # ------------------------------------------------------------------

    def _handle_duplicate_customer(self, error_msg, order_data, api_url, headers, pill):
        """
        DUPLICATES_DETECTED / "Consignee Code already exists"

        This typically means:
        - We sent a customerId that doesn't match the existing customer
          record for that phone number.
        - OR the order itself was already created in a prior attempt.

        Strategy:
        1. Check if the ORDER already exists -> return success.
        2. Retry with customerId=null to let Khazenly match automatically.
        """
        logger.warning(f"Duplicate detected for pill {pill.pill_number}")

        # Step 1: Check if the order already exists (prior successful send?)
        existing = self.check_order_exists(pill.pill_number)
        if existing and existing.get('salesOrderNumber'):
            logger.info(f"Order already exists: {existing.get('salesOrderNumber')}")
            return {
                'success': True,
                'data': {
                    'khazenly_order_id': existing.get('id'),
                    'sales_order_number': existing.get('salesOrderNumber'),
                    'order_number': existing.get('orderNumber'),
                    'already_exists': True,
                    'message': 'Order already existed in Khazenly',
                },
            }

        # Step 2: Retry with customerId=null  (let Khazenly auto-match)
        logger.info("Retrying with customerId=null to let Khazenly auto-match")
        retry_data = copy.deepcopy(order_data)
        retry_data['Customer']['customerId'] = None

        response, net_err = self._send_order_request(api_url, headers, retry_data)
        if net_err:
            return {'success': False, 'error': net_err}

        if response.status_code == 200:
            try:
                rdata = response.json()
            except json.JSONDecodeError:
                rdata = {}

            if rdata.get('resultCode') == 0:
                logger.info("Duplicate-customer retry succeeded with customerId=null")
                result = self._parse_success(rdata)
                result['data']['duplicate_recovered'] = True
                return result

            logger.warning(f"Retry with customerId=null also failed: {rdata.get('result', '')}")

        phone = order_data['Customer'].get('Tel', '?')
        customer_id = order_data['Customer'].get('customerId', '?')
        return {
            'success': False,
            'error': (
                f"Customer already exists in Khazenly (DUPLICATES_DETECTED). "
                f"Phone: {phone}, customerId tried: {customer_id}. "
                f"Please check Khazenly dashboard for order {pill.pill_number} "
                f"or contact support. Details: {error_msg}"
            ),
        }

    # ------------------------------------------------------------------
    #  Order lookup
    # ------------------------------------------------------------------

    def check_order_exists(self, order_number):
        """
        Check if an order already exists in Khazenly by orderNumber.
        Returns the order dict if found, None otherwise.
        """
        try:
            access_token = self.get_access_token()
            if not access_token:
                return None

            query_url = f"{self.base_url}/services/apexrest/api/GetOrder"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            params = {'orderNumber': order_number}

            logger.info(f"Checking if order {order_number} exists in Khazenly...")
            response = requests.get(query_url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if data.get('resultCode') == 0 and data.get('order', {}).get('id'):
                    logger.info(f"Order {order_number} exists in Khazenly")
                    return data.get('order')

            return None

        except Exception as e:
            logger.warning(f"Could not check order existence: {e}")
            return None

    # ------------------------------------------------------------------
    #  Order status
    # ------------------------------------------------------------------

    def get_order_status(self, sales_order_number):
        """Get order status from Khazenly."""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {'success': False, 'error': 'Failed to get access token'}

            status_url = (
                f"{self.base_url}/services/apexrest/"
                f"ExternalIntegrationWebService/orders/{sales_order_number}"
            )
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
            }

            response = requests.get(status_url, headers=headers, timeout=30)
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}

        except Exception as e:
            logger.error(f"Exception getting order status: {e}")
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------------
    #  Diagnostics
    # ------------------------------------------------------------------

    def diagnose_customer_data(self, pill):
        """Diagnose customer data issues that might cause Khazenly API errors."""
        try:
            logger.info(f"DIAGNOSING CUSTOMER DATA for Pill {pill.pill_number}")

            if not hasattr(pill, 'pilladdress'):
                return {'issues': ['Missing address'], 'details': 'No pilladdress'}

            address = pill.pilladdress
            issues = []
            details = {}

            # Name
            name = address.name or f"Customer {pill.user.username}"
            details['customerName'] = {
                'value': name, 'length': len(name),
                'has_special': bool(re.search(r'[^\w\s\-.,()]+', name)),
            }
            if len(name) > 50:
                issues.append(f'Customer name too long ({len(name)}/50)')

            # Phones
            for label, raw in [
                ('primary', getattr(address, 'phone', '')),
                ('user_phone', getattr(pill.user, 'phone', '')),
                ('user_phone2', getattr(pill.user, 'phone2', '')),
                ('parent_phone', getattr(pill.user, 'parent_phone', '')),
            ]:
                if not raw:
                    continue
                validated = self.validate_phone(raw)
                details[f'{label}_phone'] = {
                    'original': raw, 'validated': validated,
                    'valid': bool(validated),
                }
                if raw and not validated:
                    issues.append(f'{label} phone invalid: {raw}')

            # Address
            addr_text = address.address or ""
            details['address'] = {'value': addr_text, 'length': len(addr_text)}
            if len(addr_text) > 100:
                issues.append(f'Address too long ({len(addr_text)}/100)')

            # City
            gov = getattr(address, 'government', '')
            city = self._government_to_city().get(gov, '') if gov else ''
            details['city'] = {'government_code': gov, 'mapped': city}
            if city and city not in self._supported_cities():
                issues.append(f"City '{city}' not in Khazenly list")

            logger.info(f"Diagnosis: {len(issues)} issues found")
            return {
                'success': True,
                'has_issues': len(issues) > 0,
                'issues': issues,
                'details': details,
            }

        except Exception as e:
            logger.error(f"Error diagnosing customer data: {e}")
            return {'success': False, 'error': str(e)}


# Global instance
khazenly_service = KhazenlyService()
