from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from products.models import Pill, PillItem, Product, ProductAvailability


class PaidPillInventoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer',
            password='secret123',
            name='Buyer One'
        )

    def create_product(self, name='Test Product', quantity=1, price=100):
        product = Product.objects.create(name=name, price=price)
        ProductAvailability.objects.create(
            product=product,
            quantity=quantity,
            native_price=50
        )
        return product

    def create_pill(self, product, quantity=1, paid=False, status='i', **invoice_fields):
        pill = Pill.objects.create(user=self.user, paid=paid, status=status)
        item = PillItem.objects.create(
            pill=pill,
            user=self.user,
            product=product,
            quantity=quantity,
            status=status
        )
        pill.items.add(item)

        for field_name, value in invoice_fields.items():
            setattr(pill, field_name, value)

        if invoice_fields:
            pill.save(update_fields=list(invoice_fields.keys()))

        return pill

    @patch('products.models.Pill._create_khazenly_order')
    @patch('services.shakeout_service.shakeout_service.cancel_invoice')
    @patch('services.easypay_service.easypay_service.cancel_invoice')
    def test_payment_deducts_inventory_and_cancels_pending_invoices_when_product_depleted(
        self,
        easypay_cancel_mock,
        shakeout_cancel_mock,
        khazenly_mock
    ):
        product = self.create_product(quantity=1)
        paid_pill = self.create_pill(product, quantity=1)
        easypay_pending = self.create_pill(
            product,
            quantity=1,
            payment_gateway='easypay',
            easypay_fawry_ref='FWR-123',
            easypay_data={'invoice_details': {'payment_status': 'pending'}}
        )
        shakeout_pending = self.create_pill(
            product,
            quantity=1,
            payment_gateway='shakeout',
            shakeout_invoice_id='INV-1',
            shakeout_invoice_ref='REF-1',
            shakeout_data={'status': 'active'}
        )

        easypay_cancel_mock.return_value = {'success': True, 'data': {}}
        shakeout_cancel_mock.return_value = {'success': True, 'data': {}}

        paid_pill.paid = True
        paid_pill.status = 'p'
        paid_pill.save()

        product.refresh_from_db()
        paid_pill.refresh_from_db()
        easypay_pending.refresh_from_db()
        shakeout_pending.refresh_from_db()

        self.assertEqual(product.total_quantity(), 0)
        self.assertTrue(paid_pill.inventory_deducted)
        self.assertFalse(paid_pill.has_stock_problem)

        easypay_cancel_mock.assert_called_once_with('FWR-123')
        shakeout_cancel_mock.assert_called_once_with('INV-1', 'REF-1')
        khazenly_mock.assert_called_once()

        self.assertEqual(
            easypay_pending.easypay_data['invoice_details']['payment_status'],
            'cancelled'
        )
        self.assertEqual(
            shakeout_pending.shakeout_data['system_status'],
            'cancelled'
        )

    @patch('products.models.Pill._create_khazenly_order')
    @patch('services.easypay_service.easypay_service.cancel_invoice')
    def test_payment_does_not_cancel_pending_invoices_when_stock_remains(
        self,
        easypay_cancel_mock,
        khazenly_mock
    ):
        product = self.create_product(quantity=2)
        paid_pill = self.create_pill(product, quantity=1)
        self.create_pill(
            product,
            quantity=1,
            payment_gateway='easypay',
            easypay_fawry_ref='FWR-456',
            easypay_data={'invoice_details': {'payment_status': 'pending'}}
        )

        paid_pill.paid = True
        paid_pill.status = 'p'
        paid_pill.save()

        product.refresh_from_db()
        paid_pill.refresh_from_db()

        self.assertEqual(product.total_quantity(), 1)
        self.assertTrue(paid_pill.inventory_deducted)
        easypay_cancel_mock.assert_not_called()
        khazenly_mock.assert_called_once()

    @patch('products.models.Pill._create_khazenly_order')
    def test_delivery_does_not_double_deduct_inventory_after_payment(self, khazenly_mock):
        product = self.create_product(quantity=5)
        paid_pill = self.create_pill(product, quantity=2)

        paid_pill.paid = True
        paid_pill.status = 'p'
        paid_pill.save()

        self.assertEqual(product.total_quantity(), 3)

        paid_pill.status = 'd'
        paid_pill.save()

        product.refresh_from_db()
        paid_pill.refresh_from_db()

        self.assertEqual(product.total_quantity(), 3)
        self.assertTrue(paid_pill.inventory_deducted)
        khazenly_mock.assert_called_once()

    @patch('products.models.Pill._create_khazenly_order')
    def test_cancelling_paid_pill_restores_inventory_reserved_at_payment(self, khazenly_mock):
        product = self.create_product(quantity=3)
        paid_pill = self.create_pill(product, quantity=2)

        paid_pill.paid = True
        paid_pill.status = 'p'
        paid_pill.save()
        self.assertEqual(product.total_quantity(), 1)

        paid_pill.status = 'c'
        paid_pill.save()

        product.refresh_from_db()
        paid_pill.refresh_from_db()

        self.assertEqual(product.total_quantity(), 3)
        self.assertFalse(paid_pill.inventory_deducted)
        khazenly_mock.assert_called_once()

    @patch('products.models.Pill._create_khazenly_order')
    @patch('services.easypay_service.easypay_service.cancel_invoice')
    def test_payment_continues_even_if_pending_invoice_cancellation_fails(
        self,
        easypay_cancel_mock,
        khazenly_mock
    ):
        product = self.create_product(quantity=1)
        paid_pill = self.create_pill(product, quantity=1)
        pending_pill = self.create_pill(
            product,
            quantity=1,
            payment_gateway='easypay',
            easypay_fawry_ref='FWR-789',
            easypay_data={'invoice_details': {'payment_status': 'pending'}}
        )

        easypay_cancel_mock.return_value = {
            'success': False,
            'error': 'remote api failed'
        }

        paid_pill.paid = True
        paid_pill.status = 'p'
        paid_pill.save()

        product.refresh_from_db()
        paid_pill.refresh_from_db()
        pending_pill.refresh_from_db()

        self.assertEqual(product.total_quantity(), 0)
        self.assertTrue(paid_pill.inventory_deducted)
        self.assertEqual(
            pending_pill.easypay_data['invoice_details']['payment_status'],
            'pending'
        )
        khazenly_mock.assert_called_once()
