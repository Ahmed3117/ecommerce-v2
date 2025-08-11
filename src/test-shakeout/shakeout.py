from flask import Flask, request, jsonify
import requests
import hashlib
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables from Django's .env file
load_dotenv('/media/ahmedissa/AHMED4/mainwork/easytech/full_ecommerce/src/.env')

app = Flask(__name__)

# Configuration - now reads from Django's .env file
API_KEY = os.getenv('SHAKEOUT_API_KEY', '68909b3acd8cbojjCbFOPPJlGvwVTHSWKXxehYTJeFEuATalS1U1D')
SECRET_KEY = os.getenv('SHAKEOUT_SECRET_KEY', '9aa639b63b2a4c3182f73771fb2e11df')
SHAKEOUT_BASE_URL = os.getenv('SHAKEOUT_BASE_URL', 'https://dash.shake-out.com/api/public/vendor')
SHAKEOUT_API_URL = f"{SHAKEOUT_BASE_URL}/invoice"

print(f"🔧 Flask app using API Key: {API_KEY[:10]}...")
print(f"🔧 Flask app using Base URL: {SHAKEOUT_BASE_URL}")

def calculate_invoice_amount(items, shipping=0, discount=0, discount_type='fixed', tax=0):
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    
    if discount > 0:
        if discount_type == 'percent':
            discount_amount = subtotal * (discount / 100)
        else:
            discount_amount = discount
        subtotal -= discount_amount
    
    total = subtotal + shipping
    if tax > 0:
        total += total * (tax / 100)
    
    return round(total, 2)

@app.route('/create_invoice', methods=['POST'])
def create_invoice():
    try:
        # Example of VALID request with future due date
        request_data = request.json or {
            "customer": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+201234567890",
                "address": "123 Main St, Cairo"
            },
            "invoice_items": [
                {"name": "Laptop", "price": 1500, "quantity": 1},
                {"name": "Mouse", "price": 200, "quantity": 2}
            ],
            "due_date": (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),  # 7 days in future
            "shipping": 100,
            "discount": 50,
            "discount_type": "fixed",
            "tax": 14,
            "redirection_urls": {
                "success_url": "https://yourstore.com/success",
                "fail_url": "https://yourstore.com/fail",
                "pending_url": "https://yourstore.com/pending"
            }
        }

        # Validate items
        items = request_data.get('invoice_items', request_data.get('items', []))
        if not items:
            return jsonify({"error": "At least one invoice item is required"}), 400

        # Calculate amount
        amount = calculate_invoice_amount(
            items=items,
            shipping=request_data.get('shipping', 0),
            discount=request_data.get('discount', 0),
            discount_type=request_data.get('discount_type', 'fixed'),
            tax=request_data.get('tax', 0)
        )

        # Prepare API request
        invoice_data = {
            "amount": amount,
            "currency": "EGP",
            "due_date": "2025-12-31",
            "customer": request_data['customer'],
            "redirection_urls": request_data.get('redirection_urls', {
                "success_url": f"{request.host_url}payment/success",
                "fail_url": f"{request.host_url}payment/fail",
                "pending_url": f"{request.host_url}payment/pending"
            }),
            "invoice_items": items,
            "tax_enabled": bool(request_data.get('tax', 0)),
            "tax_value": request_data.get('tax', 0),
            "discount_enabled": bool(request_data.get('discount', 0)),
            "discount_type": request_data.get('discount_type', 'fixed'),
            "discount_value": request_data.get('discount', 0)
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'apikey {API_KEY}'
        }

        response = requests.post(SHAKEOUT_API_URL, json=invoice_data, headers=headers)
        
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({
                "error": "Failed to create invoice",
                "details": response.json(),
                "debug": {
                    "calculated_amount": amount,
                    "due_date_used": due_date,
                    "items_total": sum(item['price'] * item['quantity'] for item in items)
                }
            }), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """
    Handle Shake-out payment webhooks
    """
    try:
        data = request.json
        app.logger.info(f"Received webhook data: {data}")
        received_signature = data.get('signature')

        # Verify the signature
        invoice_id = data['data']['invoice_id']
        amount = str(data['data']['amount'])
        invoice_status = data['data']['invoice_status']
        updated_at = data['data']['updated_at']

        # Create the expected signature
        signature_string = invoice_id + amount + invoice_status + updated_at + SECRET_KEY
        expected_signature = hashlib.sha256(signature_string.encode()).hexdigest()

        if received_signature != expected_signature:
            app.logger.warning(f"Invalid webhook signature. Received: {received_signature}, Expected: {expected_signature}")
            return jsonify({"error": "Invalid signature"}), 401

        # Process the webhook event
        event_type = data['type']
        invoice_data = data['data']

        if event_type == "InvoiceCreated":
            app.logger.info(f"New invoice created: {invoice_id}")
            # Handle new invoice (store in DB, etc.)

        elif event_type == "InvoiceStatusUpdated":
            app.logger.info(f"Invoice status updated: {invoice_id} - {invoice_status}")
            # Update your system with payment status
            # This is where you would typically:
            # 1. Find the order in your database
            # 2. Update the payment status
            # 3. Trigger fulfillment if paid

        return jsonify({"status": "success"}), 200

    except Exception as e:
        app.logger.error(f"Webhook processing error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/payment/success', methods=['GET'])
def payment_success():
    """Handle successful payment redirect"""
    return jsonify({"status": "success", "message": "Payment completed successfully"})

@app.route('/payment/fail', methods=['GET'])
def payment_fail():
    """Handle failed payment redirect"""
    return jsonify({"status": "failed", "message": "Payment failed or was cancelled"})

@app.route('/payment/pending', methods=['GET'])
def payment_pending():
    """Handle pending payment redirect"""
    return jsonify({"status": "pending", "message": "Payment is being processed"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


# "success_url": "http://bookefay.com/payment-redirect/20/success",
#                 "fail_url": "http://bookefay.com/payment-redirect/20/fail",
#                 "pending_url": "http://bookefay.com/payment-redirect/20/pending"