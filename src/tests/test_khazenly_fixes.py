"""
Full test suite for the Khazenly integration fixes (March 2026).

Tests the 3 main problems that were fixed:
  1. DUPLICATES_DETECTED — "Consignee Code already exists"
  2. Duplicate orders being sent (same pill sent twice to Khazenly)
  3. Corrupted customer data (phone-swap retry removed)

Also tests:
  4. Multi-site support (Bookify / Fastbook env switching)
  5. Sanitization & validation helpers

Run with:
    python manage.py test tests.test_khazenly_fixes -v2
"""

import json
import copy
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, TransactionTestCase, override_settings
from django.core.cache import cache
from django.utils import timezone

from accounts.models import User
from products.models import (
    Product, Category, PillItem, Pill, PillAddress, Shipping, Color,
    GOVERNMENT_CHOICES,
)
from services.khazenly_service import KhazenlyService, khazenly_service


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _make_user(**kwargs):
    """Create a test user with Egyptian phone numbers."""
    defaults = dict(
        username="testuser",
        email="test@example.com",
        phone="01000003102",
        phone2="01111111111",
        parent_phone="01222222222",
    )
    defaults.update(kwargs)
    return User.objects.create_user(password="testpass123", **defaults)


def _make_product(**kwargs):
    """Create a test product."""
    defaults = dict(name="كشكول أحياء ثالثة ثانوي", price=150.0)
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


def _make_pill(user, products=None, government="1", address_phone=None):
    """
    Create a fully-formed Pill + PillAddress + PillItems.
    Does NOT trigger the save() payment flow (paid=False initially).
    """
    pill = Pill.objects.create(user=user, status="i", paid=False)

    PillAddress.objects.create(
        pill=pill,
        name="اسراء محمد علي",
        email="esraa@example.com",
        phone=address_phone or user.phone or "01000003102",
        address="15 شارع الجمهورية، وسط البلد",
        government=government,
    )

    if products is None:
        products = [_make_product()]

    for product in products:
        item = PillItem.objects.create(
            user=user, product=product, quantity=1, status="i",
        )
        pill.items.add(item)

    # Create a Shipping entry for the government so shipping_price() works
    Shipping.objects.get_or_create(government=government, defaults={"shipping_price": 50.0})

    pill.refresh_from_db()
    return pill


# Fake successful Khazenly API response
FAKE_SUCCESS_RESPONSE = {
    "resultCode": 0,
    "result": "Success",
    "order": {
        "id": "a0B5g00000FAKE01",
        "salesOrderNumber": "KH-BOOKIFAY-00123",
        "orderNumber": "PLACEHOLDER",
    },
    "lineItems": [{"id": "item1"}],
    "customer": {"id": "cust1"},
}

# Fake "order already exists" GET response
FAKE_GET_ORDER_EXISTS = {
    "resultCode": 0,
    "order": {
        "id": "a0B5g00000EXIST",
        "salesOrderNumber": "KH-BOOKIFAY-00999",
        "orderNumber": "PLACEHOLDER",
    },
}

# Fake DUPLICATES_DETECTED error (200 with resultCode != 0)
FAKE_DUPLICATE_ERROR = {
    "resultCode": 1,
    "result": "DUPLICATES_DETECTED: Consignee Code already exists",
}

# Fake corrupted customer error
FAKE_CORRUPTED_ERROR = {
    "resultCode": 1,
    "result": "corrupted customer data - wrong code",
}


def _mock_response(status_code=200, json_data=None, text=""):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or json.dumps(json_data or {})
    resp.json.return_value = json_data or {}
    return resp


# =========================================================================
#  1. CUSTOMER ID (DUPLICATES_DETECTED fix)
# =========================================================================

class TestCustomerIdGeneration(TestCase):
    """Verify customerId is always sent as PREFIX-phone."""

    def setUp(self):
        self.svc = KhazenlyService()

    def test_build_customer_id_normal(self):
        self.assertEqual(self.svc.build_customer_id("01000003102"), "BOOKIFAY-01000003102")

    def test_build_customer_id_different_phone(self):
        self.assertEqual(self.svc.build_customer_id("01100527125"), "BOOKIFAY-01100527125")

    def test_build_customer_id_empty(self):
        self.assertIsNone(self.svc.build_customer_id(""))

    def test_build_customer_id_none(self):
        self.assertIsNone(self.svc.build_customer_id(None))

    @override_settings(KHAZENLY_CONSIGNEE_PREFIX="FASTBOOK")
    def test_build_customer_id_fastbook(self):
        """Fastbook should use its own prefix."""
        svc = KhazenlyService()
        self.assertEqual(svc.build_customer_id("01000003102"), "FASTBOOK-01000003102")

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_create_order_sends_customer_id(self, mock_post, mock_check, mock_token):
        """The order payload must include customerId=BOOKIFAY-{phone}."""
        user = _make_user()
        pill = _make_pill(user)

        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number
        mock_post.return_value = _mock_response(200, success)

        result = self.svc.create_order(pill)

        self.assertTrue(result["success"], f"Expected success, got: {result}")

        # Inspect the payload sent to the API
        call_args = mock_post.call_args
        sent_payload = call_args.kwargs.get("json") or call_args[1].get("json") or call_args[0][1] if len(call_args[0]) > 1 else None
        if sent_payload is None:
            # requests.post(url, json=...) — json is a kwarg
            sent_payload = call_args.kwargs.get("json")

        self.assertIsNotNone(sent_payload, "No JSON payload was sent to Khazenly")
        customer_id = sent_payload["Customer"]["customerId"]
        self.assertTrue(
            customer_id.startswith("BOOKIFAY-"),
            f"customerId should start with BOOKIFAY-, got: {customer_id}",
        )
        self.assertEqual(customer_id, "BOOKIFAY-01000003102")


# =========================================================================
#  2. DETERMINISTIC ORDER ID (duplicate orders fix)
# =========================================================================

class TestDeterministicOrderId(TestCase):
    """Verify orderId is always pill_number (no timestamps)."""

    def setUp(self):
        self.svc = KhazenlyService()

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_order_id_is_pill_number(self, mock_post, mock_check, mock_token):
        """orderId must be pill_number exactly — no suffix, no timestamp."""
        user = _make_user()
        pill = _make_pill(user)

        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number
        mock_post.return_value = _mock_response(200, success)

        self.svc.create_order(pill)

        sent_payload = mock_post.call_args.kwargs.get("json")
        self.assertEqual(sent_payload["Order"]["orderId"], str(pill.pill_number))
        self.assertEqual(sent_payload["Order"]["orderNumber"], pill.pill_number)

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_retry_keeps_same_order_id(self, mock_post, mock_check, mock_token):
        """Even on DUPLICATES_DETECTED retry, orderId must stay the same."""
        user = _make_user()
        pill = _make_pill(user)

        # First call: duplicate error. Second call (retry with customerId=null): success.
        dup_resp = _mock_response(200, FAKE_DUPLICATE_ERROR)
        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number
        success_resp = _mock_response(200, success)

        mock_post.side_effect = [dup_resp, success_resp]

        result = self.svc.create_order(pill)
        self.assertTrue(result["success"])

        # Both attempts must use the same orderId
        for call in mock_post.call_args_list:
            payload = call.kwargs.get("json")
            self.assertEqual(payload["Order"]["orderId"], str(pill.pill_number))


# =========================================================================
#  3. PRE-FLIGHT DUPLICATE CHECK
# =========================================================================

class TestPreFlightDuplicateCheck(TestCase):
    """If the order already exists in Khazenly, return success without re-sending."""

    def setUp(self):
        self.svc = KhazenlyService()

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.requests.post")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists")
    def test_existing_order_returns_success_no_post(self, mock_check, mock_post, mock_token):
        """If check_order_exists finds the order, create_order should NOT call POST."""
        user = _make_user()
        pill = _make_pill(user)

        mock_check.return_value = {
            "id": "a0BEXISTING",
            "salesOrderNumber": "KH-BOOKIFAY-00999",
            "orderNumber": pill.pill_number,
        }

        result = self.svc.create_order(pill)

        self.assertTrue(result["success"])
        self.assertTrue(result["data"].get("already_exists"))
        mock_post.assert_not_called()  # No POST should have been made


# =========================================================================
#  4. CORRUPTED CUSTOMER HANDLING (no phone swap)
# =========================================================================

class TestCorruptedCustomerRetry(TestCase):
    """
    When Khazenly returns "corrupted customer data", verify:
    - We retry ONCE with secondaryTel cleared
    - We do NOT swap phones
    - If retry still fails, we get a clear error message
    """

    def setUp(self):
        self.svc = KhazenlyService()

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_corrupted_retry_clears_secondary_tel(self, mock_post, mock_check, mock_token):
        """On corrupted error, retry should clear secondaryTel but keep primary phone."""
        user = _make_user(phone="01000003102", phone2="01555555555")
        pill = _make_pill(user)

        # First call: corrupted error. Second call: success.
        corrupted_resp = _mock_response(200, FAKE_CORRUPTED_ERROR)
        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number
        success_resp = _mock_response(200, success)

        mock_post.side_effect = [corrupted_resp, success_resp]

        result = self.svc.create_order(pill)
        self.assertTrue(result["success"])
        self.assertIn("retry_note", result["data"])

        # Verify: first call has secondaryTel, second call has it empty
        first_payload = mock_post.call_args_list[0].kwargs.get("json")
        retry_payload = mock_post.call_args_list[1].kwargs.get("json")

        # First call may or may not have secondary — that's fine
        # Retry MUST have empty secondaryTel
        self.assertEqual(retry_payload["Customer"]["secondaryTel"], "")

        # Primary phone must be the SAME in both calls (NO SWAP)
        self.assertEqual(
            first_payload["Customer"]["Tel"],
            retry_payload["Customer"]["Tel"],
        )

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_corrupted_retry2_succeeds_with_null_customer_id(self, mock_post, mock_check, mock_token):
        """Retry 1 fails (corrupted), retry 2 with customerId=null succeeds."""
        user = _make_user(phone="01000003102", phone2="01555555555")
        pill = _make_pill(user)

        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number

        # Original: corrupted, Retry 1: corrupted, Retry 2: success
        mock_post.side_effect = [
            _mock_response(200, FAKE_CORRUPTED_ERROR),
            _mock_response(200, FAKE_CORRUPTED_ERROR),
            _mock_response(200, success),
        ]

        result = self.svc.create_order(pill)
        self.assertTrue(result["success"])
        self.assertIn("retry_note", result["data"])
        self.assertIn("customerId=null", result["data"]["retry_note"])

        # 3 POST calls total
        self.assertEqual(mock_post.call_count, 3)

        # Retry 2 payload must have customerId=None
        retry2_payload = mock_post.call_args_list[2].kwargs.get("json")
        self.assertIsNone(retry2_payload["Customer"]["customerId"])

        # Primary phone must be constant across all calls
        for i, call in enumerate(mock_post.call_args_list):
            payload = call.kwargs.get("json")
            self.assertEqual(
                payload["Customer"]["Tel"], "01000003102",
                f"Call #{i+1}: Primary phone was swapped!"
            )

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_corrupted_retry_fails_gives_clear_message(self, mock_post, mock_check, mock_token):
        """If all 3 attempts fail (corrupted), error message must mention contacting Khazenly support."""
        user = _make_user()
        pill = _make_pill(user)

        # All 3 calls fail with corrupted data (original + retry1 + retry2)
        mock_post.side_effect = [
            _mock_response(200, FAKE_CORRUPTED_ERROR),
            _mock_response(200, FAKE_CORRUPTED_ERROR),
            _mock_response(200, FAKE_CORRUPTED_ERROR),
        ]

        result = self.svc.create_order(pill)

        self.assertFalse(result["success"])
        error = result["error"]
        self.assertIn("CORRUPTED", error)
        self.assertIn("Contact Khazenly support", error)
        self.assertIn("01000003102", error)
        self.assertEqual(mock_post.call_count, 3)

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_no_phone_swap_on_any_error(self, mock_post, mock_check, mock_token):
        """
        The old code swapped primary/secondary phones on error.
        Verify this NEVER happens — primary Tel must stay constant across all 3 retries.
        Also verify retry 2 sends customerId=None.
        """
        user = _make_user(phone="01000003102", phone2="01999999999")
        pill = _make_pill(user)

        # All 3 calls fail with corrupted data
        mock_post.side_effect = [
            _mock_response(200, FAKE_CORRUPTED_ERROR),
            _mock_response(200, FAKE_CORRUPTED_ERROR),
            _mock_response(200, FAKE_CORRUPTED_ERROR),
        ]

        self.svc.create_order(pill)

        # Must be exactly 3 POST calls (original + retry1 + retry2)
        self.assertEqual(mock_post.call_count, 3)

        # All POST calls must have the SAME primary phone
        for i, call in enumerate(mock_post.call_args_list):
            payload = call.kwargs.get("json")
            self.assertEqual(
                payload["Customer"]["Tel"], "01000003102",
                f"Call #{i+1}: Primary phone was swapped to {payload['Customer']['Tel']}!"
            )

        # Retry 2 (3rd call) must have customerId=None
        retry2_payload = mock_post.call_args_list[2].kwargs.get("json")
        self.assertIsNone(retry2_payload["Customer"]["customerId"])


# =========================================================================
#  5. DUPLICATE CUSTOMER HANDLER
# =========================================================================

class TestDuplicateCustomerHandler(TestCase):
    """Test the DUPLICATES_DETECTED error handler."""

    def setUp(self):
        self.svc = KhazenlyService()

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.requests.post")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists")
    def test_duplicate_detected_order_exists(self, mock_check, mock_post, mock_token):
        """
        DUPLICATES_DETECTED but order already exists -> return success (no retry needed).
        """
        user = _make_user()
        pill = _make_pill(user)

        # First POST: dup error
        mock_post.return_value = _mock_response(200, FAKE_DUPLICATE_ERROR)

        # check_order_exists: first call returns None (pre-flight), second returns existing
        mock_check.side_effect = [
            None,  # pre-flight before create
            {"id": "EXIST1", "salesOrderNumber": "KH-BOOKIFAY-00555", "orderNumber": pill.pill_number},  # inside handler
        ]

        result = self.svc.create_order(pill)

        self.assertTrue(result["success"])
        self.assertTrue(result["data"].get("already_exists"))

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.requests.post")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    def test_duplicate_detected_retry_with_null_customer_id(self, mock_check, mock_post, mock_token):
        """
        DUPLICATES_DETECTED, order doesn't exist -> retry with customerId=null.
        """
        user = _make_user()
        pill = _make_pill(user)

        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number

        # First call: dup error. Second call: success.
        mock_post.side_effect = [
            _mock_response(200, FAKE_DUPLICATE_ERROR),
            _mock_response(200, success),
        ]

        result = self.svc.create_order(pill)
        self.assertTrue(result["success"])

        # The retry payload must have customerId=None
        retry_payload = mock_post.call_args_list[1].kwargs.get("json")
        self.assertIsNone(retry_payload["Customer"]["customerId"])


# =========================================================================
#  6. PAYMENT METHOD
# =========================================================================

class TestPaymentMethod(TestCase):
    """Verify paymentMethod is 'Pre-Paid' (not 'Prepaid')."""

    def setUp(self):
        self.svc = KhazenlyService()

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_payment_method_pre_paid(self, mock_post, mock_check, mock_token):
        user = _make_user()
        pill = _make_pill(user)

        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number
        mock_post.return_value = _mock_response(200, success)

        self.svc.create_order(pill)

        payload = mock_post.call_args.kwargs.get("json")
        self.assertEqual(payload["Order"]["paymentMethod"], "Pre-Paid")


# =========================================================================
#  7. PHONE VALIDATION
# =========================================================================

class TestPhoneValidation(TestCase):
    """Test the validate_phone helper."""

    def test_normal_phone(self):
        self.assertEqual(KhazenlyService.validate_phone("01000003102"), "01000003102")

    def test_plus_20_prefix(self):
        self.assertEqual(KhazenlyService.validate_phone("+201000003102"), "01000003102")

    def test_20_prefix(self):
        self.assertEqual(KhazenlyService.validate_phone("201000003102"), "01000003102")

    def test_too_short(self):
        self.assertEqual(KhazenlyService.validate_phone("0100"), "")

    def test_invalid_prefix(self):
        self.assertEqual(KhazenlyService.validate_phone("09000003102"), "")

    def test_with_spaces(self):
        self.assertEqual(KhazenlyService.validate_phone("0100 000 3102"), "01000003102")

    def test_empty(self):
        self.assertEqual(KhazenlyService.validate_phone(""), "")

    def test_none(self):
        self.assertEqual(KhazenlyService.validate_phone(None), "")


# =========================================================================
#  8. TEXT SANITIZATION
# =========================================================================

class TestSanitization(TestCase):
    """Test sanitize_text and sanitize_item_name."""

    def test_removes_zero_width_chars(self):
        result = KhazenlyService.sanitize_text("Ahmed\u200b Ali\u200e", 50, "test")
        self.assertEqual(result, "Ahmed Ali")

    def test_truncates_long_text(self):
        result = KhazenlyService.sanitize_text("a" * 120, 50, "test")
        self.assertLessEqual(len(result), 50)

    def test_arabic_text_preserved(self):
        result = KhazenlyService.sanitize_text("اسراء محمد علي", 50, "test")
        self.assertEqual(result, "اسراء محمد علي")

    def test_empty_returns_empty(self):
        self.assertEqual(KhazenlyService.sanitize_text("", 50, "test"), "")
        self.assertEqual(KhazenlyService.sanitize_text(None, 50, "test"), "")

    def test_sanitize_item_name_emojis(self):
        result = KhazenlyService.sanitize_item_name("كشكول 📚 أحياء")
        self.assertNotIn("📚", result)
        self.assertIn("كشكول", result)
        self.assertIn("أحياء", result)


# =========================================================================
#  9. ORDER VALIDATION
# =========================================================================

class TestOrderValidation(TestCase):
    """Test the pre-send order validator."""

    def setUp(self):
        self.svc = KhazenlyService()

    def _valid_order(self):
        return {
            "Order": {
                "orderId": "12345",
                "orderNumber": "12345",
                "storeName": "https://bookefay.com",
                "totalAmount": 250.0,
            },
            "Customer": {
                "customerName": "اسراء محمد",
                "Tel": "01000003102",
                "Address1": "15 شارع الجمهورية",
                "City": "Cairo",
            },
            "lineItems": [
                {"SKU": "PROD-1", "ItemName": "كشكول أحياء", "Price": 150.0, "Quantity": 1}
            ],
        }

    def test_valid_order_passes(self):
        result = self.svc.validate_order_data(self._valid_order())
        self.assertTrue(result["valid"])
        self.assertEqual(result["issues"], [])

    def test_missing_customer_name(self):
        order = self._valid_order()
        order["Customer"]["customerName"] = ""
        result = self.svc.validate_order_data(order)
        self.assertFalse(result["valid"])
        self.assertTrue(any("customerName" in i for i in result["issues"]))

    def test_unsupported_city(self):
        order = self._valid_order()
        order["Customer"]["City"] = "InvalidCity"
        result = self.svc.validate_order_data(order)
        self.assertFalse(result["valid"])
        self.assertTrue(any("not supported" in i for i in result["issues"]))

    def test_no_line_items(self):
        order = self._valid_order()
        order["lineItems"] = []
        result = self.svc.validate_order_data(order)
        self.assertFalse(result["valid"])
        self.assertTrue(any("No products" in i for i in result["issues"]))


# =========================================================================
#  10. MODEL-LEVEL LOCKING (_create_khazenly_order)
# =========================================================================

class TestModelLevelLocking(TransactionTestCase):
    """
    Test the _create_khazenly_order method on the Pill model.
    Verifies cache lock, select_for_update, and double-send prevention.
    """

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("services.khazenly_service.KhazenlyService.create_order")
    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    def test_cache_lock_prevents_double_send(self, mock_token, mock_create):
        """If cache lock is already held, second call should be skipped."""
        user = _make_user(username="lockuser1")
        pill = _make_pill(user)

        # Simulate lock already held
        lock_key = f"khazenly_send_lock:{pill.pk}"
        cache.set(lock_key, "1", timeout=300)

        # Call _create_khazenly_order — should skip because lock is held
        pill._create_khazenly_order()

        mock_create.assert_not_called()

    @patch("services.khazenly_service.KhazenlyService.create_order")
    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    def test_already_has_order_skips(self, mock_token, mock_create):
        """If pill already has khazenly_data, it should skip."""
        user = _make_user(username="skipuser1")
        pill = _make_pill(user)

        # Pre-set khazenly_data to simulate already sent
        Pill.objects.filter(pk=pill.pk).update(
            khazenly_data={"salesOrderNumber": "KH-BOOKIFAY-00001"},
        )

        pill._create_khazenly_order()

        mock_create.assert_not_called()

    @patch("services.khazenly_service.KhazenlyService.create_order")
    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    def test_successful_send_stores_data(self, mock_token, mock_create):
        """On success, khazenly_data, order_id, sales_order_number should be stored."""
        user = _make_user(username="successuser1")
        pill = _make_pill(user)

        mock_create.return_value = {
            "success": True,
            "data": {
                "khazenly_order_id": "a0BFAKE123",
                "sales_order_number": "KH-BOOKIFAY-09999",
                "order_number": pill.pill_number,
            },
        }

        pill._create_khazenly_order()

        pill.refresh_from_db()
        self.assertIsNotNone(pill.khazenly_data)
        self.assertEqual(pill.khazenly_order_id, "a0BFAKE123")
        self.assertEqual(pill.khazenly_sales_order_number, "KH-BOOKIFAY-09999")
        self.assertTrue(pill.is_shipped)

    @patch("services.khazenly_service.KhazenlyService.create_order")
    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    def test_failed_send_raises_exception(self, mock_token, mock_create):
        """On failure, the method should raise so the transaction rolls back."""
        user = _make_user(username="failuser1")
        pill = _make_pill(user)

        mock_create.return_value = {
            "success": False,
            "error": "Some Khazenly error",
        }

        with self.assertRaises(Exception) as ctx:
            pill._create_khazenly_order()

        self.assertIn("Khazenly service error", str(ctx.exception))

        # Pill should NOT have khazenly data
        pill.refresh_from_db()
        self.assertIsNone(pill.khazenly_data)
        self.assertFalse(pill.is_shipped)

    @patch("services.khazenly_service.KhazenlyService.create_order")
    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    def test_cache_lock_released_after_send(self, mock_token, mock_create):
        """After send (success or failure), cache lock must be released."""
        user = _make_user(username="releaseuser1")
        pill = _make_pill(user)

        mock_create.return_value = {
            "success": True,
            "data": {
                "khazenly_order_id": "a0BRELEASE",
                "sales_order_number": "KH-BOOKIFAY-08888",
                "order_number": pill.pill_number,
            },
        }

        pill._create_khazenly_order()

        lock_key = f"khazenly_send_lock:{pill.pk}"
        self.assertIsNone(cache.get(lock_key), "Cache lock was not released after send")


# =========================================================================
#  11. MULTI-SITE SUPPORT
# =========================================================================

class TestMultiSiteSettings(TestCase):
    """Verify settings properly switch between Bookify and Fastbook."""

    def test_bookify_defaults(self):
        from django.conf import settings
        # These are the values from current .env or defaults
        self.assertIn("bookefay", settings.FRONTEND_URL)
        self.assertEqual(settings.KHAZENLY_CONSIGNEE_PREFIX, "BOOKIFAY")

    @override_settings(
        KHAZENLY_CONSIGNEE_PREFIX="FASTBOOK",
        FRONTEND_URL="https://fast-book-store.com",
        FALLBACK_EMAIL_DOMAIN="fast-book-store.com",
        ACTIVE_SITE_NAME="FASTBOOK",
    )
    def test_fastbook_settings(self):
        from django.conf import settings
        svc = KhazenlyService()
        self.assertEqual(svc.consignee_prefix, "FASTBOOK")
        self.assertEqual(svc.build_customer_id("01000003102"), "FASTBOOK-01000003102")
        self.assertEqual(settings.FRONTEND_URL, "https://fast-book-store.com")
        self.assertEqual(settings.FALLBACK_EMAIL_DOMAIN, "fast-book-store.com")


# =========================================================================
#  12. SECONDARY PHONE FIELD CASING
# =========================================================================

class TestSecondaryTelCasing(TestCase):
    """Verify we send 'secondaryTel' (lowercase s), matching API docs."""

    def setUp(self):
        self.svc = KhazenlyService()

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.KhazenlyService.check_order_exists", return_value=None)
    @patch("services.khazenly_service.requests.post")
    def test_secondary_tel_lowercase(self, mock_post, mock_check, mock_token):
        user = _make_user(phone="01000003102", phone2="01555666777")
        pill = _make_pill(user)

        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number
        mock_post.return_value = _mock_response(200, success)

        self.svc.create_order(pill)

        payload = mock_post.call_args.kwargs.get("json")
        customer = payload["Customer"]

        # Must use lowercase 's' in secondaryTel
        self.assertIn("secondaryTel", customer)
        # Must NOT have uppercase 'S' SecondaryTel
        self.assertNotIn("SecondaryTel", customer)


# =========================================================================
#  13. END-TO-END SCENARIO — "مى عامر" duplicate example
# =========================================================================

class TestEndToEndDuplicateScenario(TestCase):
    """
    Simulates the real-world bug: a returning customer whose order was sent
    twice because the old code used timestamp-based orderId.

    With the fix, the second send must detect the existing order and return
    success without creating a new order.
    """

    def setUp(self):
        self.svc = KhazenlyService()

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.requests.post")
    @patch("services.khazenly_service.requests.get")
    def test_returning_customer_second_order(self, mock_get, mock_post, mock_token):
        """
        Scenario:
        1. Customer "مى عامر" placed order #1 (already completed).
        2. She places order #2 — new pill, same phone.
        3. create_order for pill #2 should succeed with customerId=BOOKIFAY-phone.
        """
        user = _make_user(username="mai_amer", phone="01012345678")
        pill = _make_pill(user)

        # Pre-flight: order does not exist yet
        preflight_resp = _mock_response(200, {"resultCode": 1, "result": "Order not found"})
        mock_get.return_value = preflight_resp

        # POST: success
        success = copy.deepcopy(FAKE_SUCCESS_RESPONSE)
        success["order"]["orderNumber"] = pill.pill_number
        success["order"]["salesOrderNumber"] = "KH-BOOKIFAY-00200"
        mock_post.return_value = _mock_response(200, success)

        result = self.svc.create_order(pill)

        self.assertTrue(result["success"])
        payload = mock_post.call_args.kwargs.get("json")
        self.assertEqual(payload["Customer"]["customerId"], "BOOKIFAY-01012345678")
        self.assertEqual(payload["Order"]["orderId"], str(pill.pill_number))

    @patch("services.khazenly_service.KhazenlyService.get_access_token", return_value="fake-token")
    @patch("services.khazenly_service.requests.get")
    @patch("services.khazenly_service.requests.post")
    def test_resend_same_order_detected(self, mock_post, mock_get, mock_token):
        """
        Scenario: Admin clicks "Send to Khazenly" again for the same pill.
        Pre-flight check finds the existing order -> return success, no POST.
        """
        user = _make_user(username="mai_resend")
        pill = _make_pill(user)

        # Pre-flight GET: order already exists
        existing = copy.deepcopy(FAKE_GET_ORDER_EXISTS)
        existing["order"]["orderNumber"] = pill.pill_number
        mock_get.return_value = _mock_response(200, existing)

        result = self.svc.create_order(pill)

        self.assertTrue(result["success"])
        self.assertTrue(result["data"].get("already_exists"))
        # POST should never have been called
        mock_post.assert_not_called()


# =========================================================================
#  14. GOVERNMENT-TO-CITY MAPPING
# =========================================================================

class TestGovernmentMapping(TestCase):
    """Verify all government codes map to valid Khazenly cities."""

    def test_all_governments_map_to_supported_cities(self):
        mapping = KhazenlyService._government_to_city()
        supported = KhazenlyService._supported_cities()

        for code, city in mapping.items():
            self.assertIn(
                city, supported,
                f"Government '{code}' maps to '{city}' which is not in supported cities list"
            )

    def test_all_government_choices_covered(self):
        """Every GOVERNMENT_CHOICES code should have a mapping."""
        mapping = KhazenlyService._government_to_city()
        for code, display_name in GOVERNMENT_CHOICES:
            self.assertIn(
                code, mapping,
                f"GOVERNMENT_CHOICES code '{code}' ({display_name}) has no Khazenly mapping"
            )
