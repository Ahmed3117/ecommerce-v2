# EasyPay Integration Documentation

## Overview

This project now supports two payment gateways:
- **Shakeout** (existing)
- **EasyPay** (newly added)

The active payment gateway is controlled by the `ACTIVE_PAYMENT_METHOD` environment variable.

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Payment Gateway Selection
ACTIVE_PAYMENT_METHOD=shakeout  # or 'easypay'

# EasyPay Configuration
EASYPAY_VENDOR_CODE=easytech_73497801958412
EASYPAY_SECRET_KEY=aa093225-cb06-4b39-b684-1f8533c5e2f6
EASYPAY_BASE_URL=https://api.easy-adds.com/api
EASYPAY_PAYMENT_METHOD=fawry
EASYPAY_PAYMENT_EXPIRY=172800000  # 48 hours in milliseconds

# Webhook Authentication (for EasyPay webhooks with API key)
API_KEY_MANASA=your-secure-api-key-here
```

### Settings Configuration

The following settings are automatically configured in `core/settings.py`:

```python
# Payment Gateway Configuration
ACTIVE_PAYMENT_METHOD = os.getenv('ACTIVE_PAYMENT_METHOD', 'shakeout').lower()

# EasyPay Configuration
EASYPAY_VENDOR_CODE = os.getenv('EASYPAY_VENDOR_CODE', 'easytech_73497801958412')
EASYPAY_SECRET_KEY = os.getenv('EASYPAY_SECRET_KEY', 'aa093225-cb06-4b39-b684-1f8533c5e2f6')
EASYPAY_BASE_URL = os.getenv('EASYPAY_BASE_URL', 'https://api.easy-adds.com/api')
EASYPAY_WEBHOOK_URL = os.getenv('EASYPAY_WEBHOOK_URL', f'{SITE_URL}/api/webhook/easypay/')
EASYPAY_PAYMENT_METHOD = os.getenv('EASYPAY_PAYMENT_METHOD', 'fawry')
EASYPAY_PAYMENT_EXPIRY = int(os.getenv('EASYPAY_PAYMENT_EXPIRY', '172800000'))
```

## Database Changes

### New Pill Model Fields

The following fields have been added to the `Pill` model:

```python
# EasyPay fields
easypay_invoice_uid = models.CharField(max_length=100, null=True, blank=True)
easypay_invoice_sequence = models.CharField(max_length=100, null=True, blank=True)
easypay_data = models.JSONField(null=True, blank=True)
easypay_created_at = models.DateTimeField(null=True, blank=True)

# Payment gateway tracking
payment_gateway = models.CharField(
    max_length=20, 
    choices=PAYMENT_GATEWAY_CHOICES, 
    null=True, 
    blank=True
)
```

### Migration

Run the following commands to apply the database changes:

```bash
python manage.py makemigrations products
python manage.py migrate
```

## API Endpoints

### Invoice Creation Endpoints

1. **Generic Payment Invoice Creation** (Recommended)
   ```
   POST /api/pills/{pill_id}/create-payment-invoice/
   ```
   - Uses the active payment method from settings
   - Automatically selects between Shakeout and EasyPay

2. **EasyPay Specific Invoice Creation**
   ```
   POST /api/pills/{pill_id}/create-easypay-invoice/
   ```
   - Forces EasyPay usage regardless of settings

3. **Shakeout Specific Invoice Creation** (Existing)
   ```
   POST /api/pills/{pill_id}/create-shakeout-invoice/
   ```
   - Forces Shakeout usage regardless of settings

### Webhook Endpoints

1. **EasyPay Webhook**
   ```
   POST /api/webhook/easypay/
   POST /api/webhook/easypay/{api_key}/
   ```

2. **Shakeout Webhook** (Existing)
   ```
   POST /api/webhook/shakeout/
   ```

## Usage Examples

### Creating a Payment Invoice

```python
from products.models import Pill

# Get a pill
pill = Pill.objects.get(id=123)

# Method 1: Use active payment gateway (recommended)
payment_url = pill.create_payment_invoice()

# Method 2: Force specific gateway
easypay_url = pill.create_easypay_invoice()
shakeout_url = pill.create_shakeout_invoice()
```

### API Usage

```bash
# Create invoice using active payment method
curl -X POST \
  http://localhost:8000/api/pills/123/create-payment-invoice/ \
  -H "Authorization: Bearer your-jwt-token"

# Create EasyPay invoice specifically
curl -X POST \
  http://localhost:8000/api/pills/123/create-easypay-invoice/ \
  -H "Authorization: Bearer your-jwt-token"
```

### Response Format

#### Success Response
```json
{
  "success": true,
  "message": "EasyPay invoice created successfully",
  "data": {
    "invoice_uid": "WWpRe5YUMGZcePQS",
    "invoice_sequence": "77657497986560326295",
    "payment_url": "https://dash.easy-adds.com/invoice/WWpRe5YUMGZcePQS/77657497986560326295",
    "amount": "180.00",
    "pill_number": "12345678901234567890",
    "payment_method": "fawry"
  }
}
```

#### Error Response
```json
{
  "success": false,
  "error": "Pill already has an active EasyPay invoice",
  "data": {
    "invoice_uid": "existing_uid",
    "invoice_sequence": "existing_sequence",
    "payment_url": "existing_url",
    "payment_gateway": "easypay"
  }
}
```

## Pill Model Methods

### Payment Creation Methods

```python
# Generic method (uses ACTIVE_PAYMENT_METHOD)
pill.create_payment_invoice()

# Specific methods
pill.create_easypay_invoice()
pill.create_shakeout_invoice()
```

### Payment Status Methods

```python
# Generic methods
pill.check_payment_status()
pill.payment_url
pill.payment_status

# EasyPay specific
pill.check_easypay_payment()
pill.easypay_payment_url
pill.easypay_payment_status

# Shakeout specific
pill.check_shakeout_payment()
pill.shakeout_payment_url
pill.shakeout_payment_status
```

### Invoice Expiry Methods

```python
# Generic method
pill.is_payment_invoice_expired()

# Specific methods
pill.is_easypay_invoice_expired()
pill.is_shakeout_invoice_expired()
```

## Serializer Fields

The following fields have been added to the `PillSerializer` and `PillDetailSerializer`:

```python
# EasyPay fields
'easypay_invoice_uid',
'easypay_invoice_sequence', 
'easypay_invoice_url',

# Generic fields
'payment_gateway',
'payment_url',
'payment_status'
```

## Webhook Implementation

### EasyPay Webhook

The EasyPay webhook expects the following payload:

```json
{
  "easy_pay_sequence": "77657497986560326295",
  "status": "PAID",
  "signature": "calculated_sha256_signature",
  "customer_phone": "01030265229",
  "amount": "180.00"
}
```

### Signature Verification

EasyPay webhooks use SHA256 signature verification:

```python
# Signature calculation for webhooks
string_to_hash = f"{amount}{customer_phone}{secret_key}"
expected_signature = hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
```

## Testing

### Test Script

Run the test script to verify your configuration:

```bash
cd /path/to/your/project/src
python test_easypay.py
```

### Manual Testing

1. **Create a test pill with address information**
2. **Set ACTIVE_PAYMENT_METHOD=easypay in .env**
3. **Restart the server**
4. **Call the payment invoice creation endpoint**
5. **Verify the EasyPay invoice is created**

## Switching Payment Methods

To switch between payment gateways:

1. **Update `.env` file:**
   ```env
   ACTIVE_PAYMENT_METHOD=easypay  # or 'shakeout'
   ```

2. **Restart the Django server**

3. **New invoices will use the selected method**

## Security Considerations

1. **Keep your secret keys secure**
2. **Use HTTPS for webhook endpoints**
3. **Validate webhook signatures**
4. **Set strong API_KEY_MANASA for webhook authentication**

## Troubleshooting

### Common Issues

1. **"Missing API_KEY_MANASA" error**
   - Add `API_KEY_MANASA` to your `.env` file

2. **"Invalid signature" in webhooks**
   - Verify your `EASYPAY_SECRET_KEY` is correct
   - Check the signature calculation logic

3. **"Pill already has invoice" error**
   - Check if the invoice is expired using `is_payment_invoice_expired()`
   - Clear old invoice data if needed

### Logs

Check the Django logs for detailed error information:

```bash
# In your Django logs, look for:
# - EasyPay service messages
# - Webhook processing logs
# - Signature verification logs
```

## Integration Checklist

- [ ] Add EasyPay configuration to `.env`
- [ ] Run database migrations
- [ ] Update webhook URLs in EasyPay dashboard
- [ ] Test invoice creation
- [ ] Test webhook reception
- [ ] Verify signature calculation
- [ ] Test payment flow end-to-end
- [ ] Update frontend to handle new fields (if applicable)
