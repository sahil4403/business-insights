from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer, CustomerType
from trips.models import Trip


class StatementPaginationTest(TestCase):
    """Customer statement: newest-first, 20 per page, totals intact."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='stmt-paging-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        ct = CustomerType.objects.create(code='PAG', name='Paging')
        self.customer = Customer.objects.create(
            customer_code='PAG-1', name='Paging Customer',
            customer_type=ct, opening_balance=0, is_active=True,
        )
        base = date(2026, 1, 5)
        for i in range(25):
            Trip.objects.create(
                customer=self.customer,
                trip_date=base + timedelta(days=i * 3),
                transaction_type='CUSTOMER_DELIVERY',
                quantity=1, rate=100, trip_status='COMPLETED',
            )
        self.url = reverse('ledger:customer_statement', args=[self.customer.pk])

    def test_newest_first_and_paged(self):
        r1 = self.client.get(self.url)
        r2 = self.client.get(self.url, {'page': 2})
        d1 = [t['date'].isoformat() for t in r1.context['transactions']]
        d2 = [t['date'].isoformat() for t in r2.context['transactions']]
        # 20 per page, newest-first across pages.
        self.assertEqual(len(d1), 20)
        self.assertEqual(len(d2), 5)
        self.assertTrue(all(a >= b for a, b in zip(d1, d1[1:])))
        self.assertTrue(all(a >= b for a, b in zip(d2, d2[1:])))
        self.assertTrue(d1[-1] >= d2[0])
        p1 = r1.content.decode()
        p2 = r2.content.decode()
        self.assertIn('Page 1 of 2', p1)
        self.assertIn('Page 2 of 2', p2)
        self.assertIn('25 transactions', p1)

    def test_bad_page_numbers_fall_back(self):
        self.assertContains(self.client.get(self.url, {'page': 99}), 'Page 2 of 2')
        self.assertContains(self.client.get(self.url, {'page': 'abc'}), 'Page 1 of 2')

    def test_balances_stay_correct(self):
        from decimal import Decimal as D

        p1 = self.client.get(self.url).content.decode()
        # 25 trips x Rs 100, no payments: newest row balance 2500.
        self.assertIn('₹2500.00', p1)

    def test_oldest_first_order(self):
        r = self.client.get(self.url, {'order': 'old'})
        dates = [t['date'].isoformat() for t in r.context['transactions']]
        self.assertTrue(all(a <= b for a, b in zip(dates, dates[1:])))
        self.assertIn('value="old" selected', r.content.decode())
