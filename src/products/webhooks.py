# api/webhooks.py
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
import logging

logger = logging.getLogger(__name__)

# NOTE: The main Fawaterak webhook is now handled in payment_views.py
# This file only contains testing/utility webhooks

@csrf_exempt
@require_http_methods(["GET", "POST"])
def test_webhook(request):
    """Test endpoint to verify ngrok connectivity"""
    
    if request.method == "GET":
        return JsonResponse({
            'status': 'success',
            'message': 'Webhook endpoint is reachable',
            'timestamp': str(request.META.get('HTTP_HOST')),
            'method': 'GET'
        })
    
    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
            logger.info(f"Test webhook received: {data}")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Webhook data received',
                'received_data': data,
                'method': 'POST'
            })
        except Exception as e:
            logger.error(f"Test webhook error: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })

@csrf_exempt
def ping_endpoint(request):
    """Simple ping endpoint to test connectivity"""
    return JsonResponse({
        'status': 'ok',
        'message': 'Server is reachable',
        'timestamp': str(timezone.now())
    })