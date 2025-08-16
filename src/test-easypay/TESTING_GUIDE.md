# Payment Gateway Testing Guide

## Collection Overview

This updated Postman collection provides comprehensive testing for both **Shakeout** and **EasyPay** payment gateways.

## Collection Structure

### 🔹 Shakeout Payment Gateway
- **Create Shakeout Invoice**: Test Shakeout-specific invoice creation
- **Shakeout Webhook Simulation**: Simulate payment completion webhook

### 🔸 EasyPay Payment Gateway
- **Create EasyPay Invoice**: Test EasyPay-specific invoice creation
- **EasyPay Webhook Simulation**: Simulate payment completion webhook with API key
- **EasyPay Webhook (No API Key)**: Test webhook without API key authentication

### 🔄 Generic Payment Gateway
- **Create Payment Invoice (Active Gateway)**: Uses the gateway specified in `ACTIVE_PAYMENT_METHOD`

### 🔧 Utilities & Health Checks
- **Webhook Health Checks**: Test webhook endpoints are responding
- **Resend Khazenly Orders**: Utility for Khazenly integration

## Collection Variables

Update these variables in your Postman collection:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `base_url` | Your server URL | `http://localhost:9999` |
| `jwt_token` | Your authentication token | `eyJhbGci...` |
| `pill_id` | Test pill ID | `36` |
| `customer_phone` | Test customer phone | `01030265229` |
| `webhook_amount` | Test amount | `180.00` |
| `easypay_secret_key` | EasyPay secret key | `aa093225-cb06-4b39-b684-1f8533c5e2f6` |
| `api_key` | Webhook API key | `your-secure-api-key-here` |

## Testing Workflows

### 1. Test EasyPay Integration

#### Step 1: Set Active Payment Method
In your `.env` file:
```env
ACTIVE_PAYMENT_METHOD=easypay
```
Restart your server.

#### Step 2: Create EasyPay Invoice
1. Run: **Create EasyPay Invoice**
2. Expected response:
```json
{
  "success": true,
  "message": "EasyPay invoice created successfully",
  "data": {
    "invoice_uid": "WWpRe5YUMGZcePQS",
    "invoice_sequence": "77657497986560326295",
    "payment_url": "https://dash.easy-adds.com/invoice/...",
    "amount": "180.00"
  }
}
```

#### Step 3: Update Collection Variables
Copy the returned values:
- Set `easypay_invoice_sequence` to the returned `invoice_sequence`

#### Step 4: Test EasyPay Webhook
1. Run: **EasyPay Webhook Simulation**
2. The pre-request script will automatically calculate the correct signature
3. Expected response:
```json
{
  "message": "Webhook processed successfully",
  "pill_number": "12345678901234567890",
  "status": "PAID"
}
```

### 2. Test Shakeout Integration

#### Step 1: Set Active Payment Method
In your `.env` file:
```env
ACTIVE_PAYMENT_METHOD=shakeout
```
Restart your server.

#### Step 2: Create Shakeout Invoice
1. Run: **Create Shakeout Invoice**
2. Update `shakeout_invoice_id` and `shakeout_invoice_ref` variables

#### Step 3: Test Shakeout Webhook
1. Run: **Shakeout Webhook Simulation**

### 3. Test Generic Payment Method

#### Test Active Gateway Selection
1. Set `ACTIVE_PAYMENT_METHOD` to either `easypay` or `shakeout`
2. Run: **Create Payment Invoice (Active Gateway)**
3. Verify it uses the correct gateway based on your setting

## Signature Verification Testing

### EasyPay Signature Calculation

The collection automatically calculates EasyPay webhook signatures using this logic:

```javascript
// Pre-request script in EasyPay webhook requests
const amount = pm.collectionVariables.get('webhook_amount');
const customer_phone = pm.collectionVariables.get('customer_phone');
const secret_key = pm.collectionVariables.get('easypay_secret_key');

const stringToHash = `${amount}${customer_phone}${secret_key}`;
const signature = CryptoJS.SHA256(stringToHash).toString(CryptoJS.enc.Hex);
```

### Manual Signature Verification

You can verify signatures manually:

#### EasyPay Webhook Signature:
```
String to hash: "180.0001030265229aa093225-cb06-4b39-b684-1f8533c5e2f6"
SHA256 result: [calculated signature]
```

#### EasyPay Invoice Signature:
```
String to hash: "easytech_73497801958412aa093225-cb06-4b39-b684-1f8533c5e2f6180.00501030265229"
SHA256 result: [calculated signature]
```

## Health Check Testing

### Test Webhook Endpoints
1. Run: **Shakeout Webhook Health Check** (GET request)
2. Run: **EasyPay Webhook Health Check** (GET request)
3. Both should return status 200 with health information

## Error Testing Scenarios

### Test Invalid Signatures
1. Modify the `easypay_secret_key` variable to an incorrect value
2. Run the EasyPay webhook simulation
3. Should receive 403 Forbidden error

### Test Missing Fields
1. Remove required fields from webhook payload
2. Should receive 400 Bad Request error

### Test Duplicate Invoices
1. Create an invoice for a pill
2. Try to create another invoice for the same pill
3. Should receive appropriate error response

## Environment Switching Test

### Test Payment Method Switching
1. Create invoice with `ACTIVE_PAYMENT_METHOD=shakeout`
2. Change to `ACTIVE_PAYMENT_METHOD=easypay`
3. Restart server
4. Create invoice with generic endpoint
5. Verify it uses EasyPay

## Troubleshooting

### Common Issues

1. **401 Unauthorized**: Check your JWT token is valid
2. **400 Bad Request**: Verify pill exists and has address information
3. **403 Forbidden**: Check API key and signature calculation
4. **404 Not Found**: Verify the pill ID exists

### Debug Information

Check your Django logs for detailed information:
- EasyPay service logs
- Webhook processing logs
- Signature verification details

### Collection Variables Check

Ensure all variables are properly set:
```
base_url: http://localhost:9999
jwt_token: [your valid token]
pill_id: [existing pill with address]
customer_phone: [valid phone number]
webhook_amount: [numeric amount]
easypay_secret_key: [your EasyPay secret]
api_key: [your webhook API key]
```

## Expected Test Results

### Successful EasyPay Flow
1. Invoice creation returns payment URL
2. Database shows `payment_gateway='easypay'`
3. Webhook updates pill to `paid=True`
4. Khazenly order created (if configured)

### Successful Shakeout Flow
1. Invoice creation returns payment URL
2. Database shows `payment_gateway='shakeout'`
3. Webhook updates pill to `paid=True`
4. Khazenly order created (if configured)

## Production Testing

When testing in production:
1. Use production URLs in `base_url`
2. Use production API keys
3. Test with small amounts first
4. Verify webhook URLs are accessible from payment providers
