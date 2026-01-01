"""
Standalone script to test Khazenly API with hardcoded pill data.
Run: python manage.py shell < test_khazenly_manual.py
OR:  python test_khazenly_manual.py (after setting up Django)
"""
import os
import sys
import django
import requests
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.conf import settings
from django.utils import timezone

print("=" * 80)
print("🧪 KHAZENLY API MANUAL TEST")
print("=" * 80)

# Step 1: Get access token
print("\n🔑 Step 1: Getting access token...")

token_url = f"{settings.KHAZENLY_BASE_URL}/selfservice/services/oauth2/token"
token_data = {
    'grant_type': 'refresh_token',
    'client_id': settings.KHAZENLY_CLIENT_ID,
    'client_secret': settings.KHAZENLY_CLIENT_SECRET,
    'refresh_token': settings.KHAZENLY_REFRESH_TOKEN
}

print(f"   Token URL: {token_url}")
print(f"   Client ID: {settings.KHAZENLY_CLIENT_ID[:20]}..." if settings.KHAZENLY_CLIENT_ID else "   Client ID: NOT SET")

try:
    token_response = requests.post(token_url, data=token_data, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }, timeout=30)
    
    print(f"   Token Response Status: {token_response.status_code}")
    
    if token_response.status_code != 200:
        print(f"   ❌ Token Error: {token_response.text}")
        sys.exit(1)
    
    token_json = token_response.json()
    access_token = token_json.get('access_token')
    
    if not access_token:
        print(f"   ❌ No access token in response: {token_json}")
        sys.exit(1)
    
    print(f"   ✅ Access Token: {access_token[:30]}...")
    
except Exception as e:
    print(f"   ❌ Token request failed: {e}")
    sys.exit(1)

# Step 2: Prepare order data using exact pill data from user
print("\n📋 Step 2: Preparing order data...")

# Using EXACT data from the user's exported pill:
# Pill 49065759842732150562
# Customer: شيماء  خالد
# Address: الحى التاني شارع الشعراوي فيلا 81
# City: Qalyubia - العبور
# Phone: 01070273180
# Secondary: 01063193367
# User ID: 33318

timestamp = int(timezone.now().timestamp())
order_id = f"49065759842732150562-{timestamp}"

# Build the order payload - testing FAILING pill 24381891334611609276
order_data = {
    "Order": {
        "orderId": f"24381891334611609276-{timestamp}",
        "orderNumber": "24381891334611609276",
        "storeName": settings.KHAZENLY_STORE_NAME,
        "totalAmount": 960.00,
        "shippingFees": 80.00,
        "discountAmount": 0.0,
        "taxAmount": 0,
        "invoiceTotalAmount": 960.00,
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
        "additionalNotes": "Test order for debugging"
    },
    "Customer": {
        "customerName": "علي زين",
        "Tel": "01287783212",  # Revert to REAL phone
        "SecondaryTel": "01115114018",
        "Address1": "اولاد ابراهيم المدخل الرئيسي",
        "Address2": "",
        "Address3": "",
        "City": "Assiut",
        "Country": "Egypt",
        "customerId": "BOOKIFAY-USER-70"  # Try using the EXISTING customer ID returned by Khazenly
    },
    "lineItems": [
        {
            "SKU": "Bookefy-53",
            "ItemName": "باكدج التيرم الثانى -مستر محمد صلاح",  # Removed emoji
            "Price": 200.0,
            "Quantity": 2,
            "DiscountAmount": None,
            "ItemId": "88583"
        },
        {
            "SKU": "Bookefy-55",
            "ItemName": "باكدج التيرم الثانى -دكتور محمد ايمن",  # Removed emoji
            "Price": 240.0,
            "Quantity": 2,
            "DiscountAmount": None,
            "ItemId": "88580"
        }
    ]
}

print("\n📤 ORDER DATA:")
print("-" * 80)
print(json.dumps(order_data, indent=2, ensure_ascii=False))
print("-" * 80)

# Step 3: Send to Khazenly
print("\n🚀 Step 3: Sending to Khazenly...")

api_url = f"{settings.KHAZENLY_BASE_URL}/services/apexrest/api/CreateOrder"
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

print(f"   API URL: {api_url}")

try:
    response = requests.post(api_url, json=order_data, headers=headers, timeout=60)
    
    print(f"\n📡 RESPONSE:")
    print(f"   Status Code: {response.status_code}")
    print("-" * 80)
    
    try:
        response_data = response.json()
        print(json.dumps(response_data, indent=2, ensure_ascii=False))
        
        if response_data.get('resultCode') == 0:
            print("\n" + "=" * 80)
            print("✅ SUCCESS! Order created.")
            order_info = response_data.get('order', {})
            print(f"   Sales Order Number: {order_info.get('salesOrderNumber')}")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print(f"❌ FAILED!")
            print(f"   Result Code: {response_data.get('resultCode')}")
            print(f"   Result: {response_data.get('result')}")
            print("=" * 80)
            
    except json.JSONDecodeError:
        print(response.text)
        print("\n❌ Invalid JSON response")

except Exception as e:
    print(f"\n❌ Request failed: {e}")
    import traceback
    traceback.print_exc()
