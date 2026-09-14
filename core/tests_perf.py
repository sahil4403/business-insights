"""Performance regression tests — query counts must stay flat as data grows.

These tests use small but multi-row fixtures and assert generous upper
bounds. If data-size-proportional queries (N+1) creep back in, they fail.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer
from labour.models import Labour, LabourTripGroup
from master_data.models import CustomerType
from trips.models import Trip, TripPayment


class QueryCountPerfTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username='perf-tester',
            password='test-password-123',
        )
        customer_type, _ = CustomerType.objects.get_or_create(
            code='PERF-TEST',
            defaults={'name': 'Perf Test'},
        )
        cls.customers = []
        for i in range(8):
            customer = Customer.objects.create(
                customer_code=f'PERF-{i:03d}',
                name=f'Perf Customer {i}',
                customer_type=customer_type,
                opening_balance=Decimal('0.00'),
                is_active=True,
            )
            cls.customers.append(customer)
            for _j in range(2):
                trip = Trip.objects.create(
                    trip_date=date(2026, 9, 10),
                    transaction_type='CUSTOMER_DELIVERY',
                    customer=customer,
                    quantity=1,
                    rate=100,
                    trip_status='COMPLETED',
                )
                TripPayment.objects.create(
                    trip=trip,
                    payment_date=date(2026, 9, 11),
                    amount=Decimal('50.00'),
                    payment_type='RECEIVED',
                )
        cls.labour = Labour.objects.create(
            name='Perf Labour',
            category='TRACTOR',
            is_active=True,
            status='ACTIVE',
        )
        for day in range(1, 7):
            group = LabourTripGroup.objects.create(
                date=date(2026, 9, day),
                trip_count=2,
                rate_per_trip=Decimal('450.00'),
            )
            group.labourers.add(cls.labour)

    def setUp(self):
        self.client.force_login(self.user)

    def _get(self, url):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        return response, len(ctx)

    def test_overdue_query_count_stable(self):
        response, queries = self._get(reverse('core:overdue_reminders'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 8)
        self.assertLess(queries, 16, f'{queries} queries for 8 customers')

    def test_labour_detail_query_count_stable(self):
        response, queries = self._get(
            reverse('labour:detail', args=[self.labour.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertLess(queries, 22, f'{queries} queries for 6 trip groups')

    def test_payment_report_query_count_stable(self):
        response, queries = self._get(reverse('core:payment_report'))

        self.assertEqual(response.status_code, 200)
        self.assertLess(queries, 18, f'{queries} queries for 16 payments')

    def test_dashboard_query_count_stable(self):
        response, queries = self._get(reverse('core:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertLess(queries, 45, f'{queries} dashboard queries')

    def test_customer_report_query_count_stable(self):
        response, queries = self._get(reverse('core:customer_report'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['customer_rows']), 8)
        self.assertLess(queries, 20, f'{queries} queries for 8 customers')

    def test_statement_query_count_stable(self):
        response, queries = self._get(
            reverse(
                'ledger:customer_statement',
                args=[self.customers[0].pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertLess(queries, 20, f'{queries} statement queries')

    def test_trip_list_query_count_stable(self):
        response, queries = self._get(reverse('trips:list'))

        self.assertEqual(response.status_code, 200)
        self.assertLess(queries, 30, f'{queries} trip list queries')
