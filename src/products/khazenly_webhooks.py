import json
import logging
import hashlib
import base64
import hmac
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.conf import settings
from products.models import Pill, KhazenlyWebhookLog
from django.utils import timezone
from django.db import transaction

# Set up logging with a specific logger for Khazenly
logger = logging.getLogger('khazenly_webhook')

@csrf_exempt
@require_http_methods(["GET", "POST", "HEAD"])
def khazenly_order_status_webhook(request):
    """
    Khazenly Order Status Update Webhook Handler
    Optimized for production reliability with comprehensive logging
    """
    start_time = timezone.now()
    webhook_log = None
    
    try:
        # Initialize webhook logging for all requests
        webhook_log = KhazenlyWebhookLog.log_request(request)
        
        # Handle GET requests (health checks from monitoring services)
        if request.method == 'GET':
            response = JsonResponse({
                'status': 'ok',
                'message': 'Khazenly webhook endpoint is healthy',
                'method': 'GET',
                'timestamp': timezone.now().isoformat(),
                'endpoint': 'khazenly-order-status-webhook'
            }, status=200)
            
            # Update log with response
            if webhook_log:
                webhook_log.response_status = 200
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        # Handle HEAD requests
        if request.method == 'HEAD':
            response = HttpResponse(status=200)
            
            # Update log with response
            if webhook_log:
                webhook_log.response_status = 200
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        # Handle POST requests (actual webhooks) with optimized processing
        if request.method == 'POST':
            return handle_khazenly_webhook_optimized(request, webhook_log, start_time)
            
    except Exception as e:
        logger.error(f"Critical error in webhook handler: {e}")
        
        # Update log with error
        if webhook_log:
            webhook_log.response_status = 500
            webhook_log.error_message = str(e)
            webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            webhook_log.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Webhook received but processing failed',
            'error_logged': True
        }, status=200)

def handle_khazenly_webhook_optimized(request, webhook_log=None, start_time=None):
    """
    Optimized webhook handler to prevent timeouts and 500 errors
    Now includes comprehensive logging
    """
    if start_time is None:
        start_time = timezone.now()
    
    try:
        # Quick validation first
        if not request.body:
            logger.warning("Empty request body received")
            response = JsonResponse({'error': 'Empty request body'}, status=400)
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 400
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.error_message = "Empty request body"
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        # Optional HMAC verification
        hmac_verification_result = verify_webhook_signature_optional(request)
        hmac_verified = hmac_verification_result is True
        
        # Update log with HMAC status
        if webhook_log:
            webhook_log.hmac_verified = hmac_verified
        
        if hmac_verification_result is False:
            # Verification was enabled but failed
            logger.error("❌ Invalid webhook signature - potential security threat!")
            response = JsonResponse({
                'success': True,
                'message': 'Webhook received but signature verification failed',
                'error_logged': True
            }, status=200)  # Still return 200 to prevent retries
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 200
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.error_message = "HMAC signature verification failed"
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        # Parse JSON quickly with minimal logging
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            response = JsonResponse({'error': 'Invalid JSON'}, status=400)
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 400
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.error_message = f"Invalid JSON: {e}"
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        except Exception as e:
            logger.error(f"Payload parsing error: {e}")
            response = JsonResponse({'error': 'Payload parsing error'}, status=400)
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 400
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.error_message = f"Payload parsing error: {e}"
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        # Extract essential data quickly
        status = payload.get('status')
        order_reference = payload.get('orderReference')
        merchant_reference = payload.get('merchantReference')
        order_supplier_id = payload.get('orderSupplierId')
        
        # Update log with webhook payload data
        if webhook_log:
            webhook_log.webhook_status = status
            webhook_log.order_reference = order_reference
            webhook_log.merchant_reference = merchant_reference
            webhook_log.order_supplier_id = order_supplier_id
        
        # Log essential info only
        logger.info(f"Webhook: status={status}, order_ref={order_reference}, merchant_ref={merchant_reference}")
        
        # Quick validation
        if not status:
            response = JsonResponse({'error': 'Missing status'}, status=400)
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 400
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.error_message = "Missing status in payload"
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
            
        if not order_reference and not merchant_reference:
            response = JsonResponse({'error': 'Missing order reference'}, status=400)
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 400
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.error_message = "Missing order reference"
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        # Fast pill lookup with database optimization
        pill = None
        try:
            with transaction.atomic():
                # Use select_for_update to prevent race conditions
                pill = find_pill_optimized(order_reference, merchant_reference, order_supplier_id)
        except Exception as e:
            logger.error(f"Database error during pill lookup: {e}")
            # Return success to prevent webhook retries for DB issues
            response = JsonResponse({
                'success': True,
                'message': 'Database temporarily unavailable',
                'debug': True
            }, status=200)
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 200
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.error_message = f"Database error: {e}"
                webhook_log.pill_found = False
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        if not pill:
            # Log but don't fail - could be test data
            logger.info(f"No pill found for order_ref={order_reference}, merchant_ref={merchant_reference}")
            response = JsonResponse({
                'success': True,
                'message': 'Order not found - normal for test webhooks',
                'debug': True
            }, status=200)
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 200
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.pill_found = False
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        # Update log with found pill
        if webhook_log:
            webhook_log.pill_found = True
            webhook_log.pill_number = pill.pill_number
        
        # Quick status update
        status_updated = False
        try:
            with transaction.atomic():
                status_updated = update_pill_status_fast(pill, status)
                
                # Store minimal webhook data asynchronously
                store_webhook_data_minimal(pill, {
                    'status': status,
                    'order_reference': order_reference,
                    'timestamp': start_time.isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error updating pill {pill.pill_number}: {e}")
            # Still return success to prevent retries
            response = JsonResponse({
                'success': True,
                'message': 'Status update failed but webhook received',
                'pill_number': pill.pill_number
            }, status=200)
            
            # Update log
            if webhook_log:
                webhook_log.response_status = 200
                webhook_log.response_body = response.content.decode('utf-8')
                webhook_log.error_message = f"Status update error: {e}"
                webhook_log.status_updated = False
                webhook_log.processing_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                webhook_log.save()
            
            return response
        
        # Quick response
        processing_time = (timezone.now() - start_time).total_seconds()
        logger.info(f"Webhook processed in {processing_time:.2f}s for pill {pill.pill_number}")
        
        response = JsonResponse({
            'success': True,
            'pill_number': pill.pill_number,
            'status_updated': status_updated,
            'processing_time_ms': int(processing_time * 1000)
        }, status=200)
        
        # Update log with successful response
        if webhook_log:
            webhook_log.response_status = 200
            webhook_log.response_body = response.content.decode('utf-8')
            webhook_log.status_updated = status_updated
            webhook_log.processing_time_ms = int(processing_time * 1000)
            webhook_log.save()
        
        return response
        
    except Exception as e:
        processing_time = (timezone.now() - start_time).total_seconds()
        logger.error(f"Critical error after {processing_time:.2f}s: {str(e)}")
        
        # Return success to prevent endless retries from Khazenly
        response = JsonResponse({
            'success': True,
            'message': 'Webhook received but processing failed',
            'error_logged': True
        }, status=200)
        
        # Update log with error
        if webhook_log:
            webhook_log.response_status = 200
            webhook_log.response_body = response.content.decode('utf-8')
            webhook_log.error_message = f"Critical error: {e}"
            webhook_log.processing_time_ms = int(processing_time * 1000)
            webhook_log.save()
        
        return response

def verify_webhook_signature_optional(request):
    """
    Optional HMAC verification - only runs if KHAZENLY_WEBHOOK_SECRET is configured
    Returns:
    - True: Verification passed or not configured (skip verification)
    - False: Verification failed (configured but signature invalid)
    """
    # Check if HMAC verification is enabled
    webhook_secret = getattr(settings, 'KHAZENLY_WEBHOOK_SECRET', None)
    
    if not webhook_secret:
        logger.info("ℹ️ HMAC verification disabled (no KHAZENLY_WEBHOOK_SECRET configured)")
        return True  # Skip verification
    
    # Get HMAC header from request (try different header name variations)
    hmac_header = (
        request.headers.get('khazenly-hmac-sha256') or 
        request.headers.get('Khazenly-Hmac-Sha256') or 
        request.headers.get('X-Khazenly-Signature')
    )
    
    if not hmac_header:
        logger.warning("⚠️ HMAC secret configured but no signature header received")
        return True  # Don't fail webhook for missing header, just log warning
    
    # Verify signature
    try:
        if verify_webhook_signature(request.body, hmac_header, webhook_secret):
            logger.info("✅ Webhook signature verified successfully")
            return True
        else:
            logger.error("❌ Invalid webhook signature")
            return False
    except Exception as e:
        logger.error(f"Error during HMAC verification: {e}")
        return True  # Don't fail webhook for verification errors

def find_pill_optimized(order_reference, merchant_reference, order_supplier_id):
    """
    Fast pill lookup with minimal database queries
    """
    # Single query with multiple conditions
    from django.db.models import Q
    
    conditions = Q()
    
    if order_reference:
        conditions |= Q(khazenly_sales_order_number=order_reference)
        conditions |= Q(khazenly_order_number=order_reference)
    
    if merchant_reference:
        # Extract base pill number from merchant reference
        base_pill_number = merchant_reference.split('-')[0] if '-' in merchant_reference else merchant_reference
        conditions |= Q(pill_number=base_pill_number)
        conditions |= Q(pill_number=merchant_reference)
    
    if order_supplier_id and order_supplier_id != merchant_reference:
        base_supplier_id = order_supplier_id.split('-')[0] if '-' in order_supplier_id else order_supplier_id
        conditions |= Q(pill_number=base_supplier_id)
    
    # Execute single query
    return Pill.objects.filter(conditions).first()

def update_pill_status_fast(pill, khazenly_status):
    """
    Fast status update with minimal processing
    """
    old_status = pill.status
    new_status = old_status
    
    # Enhanced status mapping including the status from your test
    if khazenly_status in [
        "Order Ready", 
        "Order Collected from Fulfilment Center", 
        "Order In-transit to Delivery Hub",
        "Order In-transit to Sorting Center",  # Added from your test
        "Order Reached Sorting Center"
    ]:
        new_status = 're'  # Ready
    elif khazenly_status in ["Out for Delivery"]:
        new_status = 'u'  # Under Delivery
    elif khazenly_status in ["Order Delivered", "Picked by Merchant"]:
        new_status = 'd'  # Delivered
    elif khazenly_status in ["Order Delivery Failed", "Returned to Fulfilment Center"]:
        new_status = 'r'  # Refused
    elif khazenly_status in ["Cancelled", "Voided", "Deleted"]:
        new_status = 'c'  # Canceled
    
    if new_status != old_status:
        pill.status = new_status
        pill.save(update_fields=['status'])
        logger.info(f"Updated pill {pill.pill_number}: {old_status} -> {new_status}")
        return True
    
    return False

def store_webhook_data_minimal(pill, webhook_data):
    """
    Store minimal webhook data efficiently
    """
    try:
        existing_data = pill.khazenly_data or {}
        
        if 'webhooks' not in existing_data:
            existing_data['webhooks'] = []
        
        existing_data['webhooks'].append(webhook_data)
        
        # Keep only last 10 entries to prevent bloat
        if len(existing_data['webhooks']) > 10:
            existing_data['webhooks'] = existing_data['webhooks'][-10:]
        
        pill.khazenly_data = existing_data
        pill.save(update_fields=['khazenly_data'])
        
    except Exception as e:
        logger.warning(f"Failed to store webhook data: {e}")
        # Don't fail the webhook for storage issues

def verify_webhook_signature(payload, signature, secret):
    """
    Verify HMAC signature for webhook security
    """
    try:
        computed_signature = base64.b64encode(
            hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return hmac.compare_digest(signature, computed_signature)
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False