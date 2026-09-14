import html
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer
from master_data.models import CustomerType
from trips.models import Trip


class CustomerSortReturnTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='sort-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        customer_type, _ = CustomerType.objects.get_or_create(
            code='SORT-TEST',
            defaults={'name': 'Sort Test'},
        )
        self.alpha = Customer.objects.create(
            customer_code='SORT-ALPHA',
            name='Alpha Customer',
            customer_type=customer_type,
            opening_balance=Decimal('100.00'),
            is_active=True,
        )
        self.beta = Customer.objects.create(
            customer_code='SORT-BETA',
            name='Beta Customer',
            customer_type=customer_type,
            opening_balance=Decimal('200.00'),
            is_active=True,
        )
        self.list_path = reverse('core:customer_report')
        self.sorted_list_path = f'{self.list_path}?sort=asc'

    def test_view_statement_preserves_customer_name_sort_on_back(self):
        list_response = self.client.get(self.sorted_list_path)

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [row['customer_name'] for row in list_response.context['customer_rows']],
            ['Alpha Customer', 'Beta Customer'],
        )

        statement_hrefs = re.findall(
            r'/ledger/customer/\d+/\?next=[^"\s<>]+',
            html.unescape(list_response.content.decode()),
        )
        self.assertTrue(
            statement_hrefs,
            'View Statement links must carry the sorted Customers URL as next',
        )

        statement_response = self.client.get(statement_hrefs[0])
        self.assertEqual(statement_response.status_code, 200)
        self.assertEqual(
            statement_response.content.decode().count(
                f'href="{self.sorted_list_path}"'
            ),
            2,
        )


class VendorSupplyBalanceTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='vendor-balance-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        customer_type, _ = CustomerType.objects.get_or_create(
            code='VENDOR-BAL-TEST',
            defaults={'name': 'Vendor Balance Test'},
        )
        self.customer = Customer.objects.create(
            customer_code='VB-001',
            name='Inward Vendor',
            customer_type=customer_type,
            opening_balance=Decimal('0.00'),
            is_active=True,
        )
        self.trip = Trip.objects.create(
            trip_date=timezone.localdate(),
            transaction_type='VENDOR_SUPPLY',
            customer=self.customer,
            quantity=2,
            rate=500,
            trip_status='COMPLETED',
        )

    def test_vendor_supply_reduces_outstanding(self):
        response = self.client.get(
            reverse('core:customer_report'),
            {'search': 'Inward Vendor'},
        )

        self.assertEqual(response.status_code, 200)
        rows = response.context['customer_rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['total_revenue'], Decimal('-1000.00'))
        self.assertEqual(rows[0]['total_received'], Decimal('0.00'))
        self.assertEqual(rows[0]['total_outstanding'], Decimal('-1000.00'))

    def test_vendor_supply_shows_as_credit_in_statement(self):
        response = self.client.get(
            reverse('ledger:customer_statement', args=[self.customer.id])
        )

        self.assertEqual(response.status_code, 200)
        transactions = response.context['transactions']
        vendor_rows = [t for t in transactions if t['type'] == 'VENDOR_SUPPLY']
        self.assertEqual(len(vendor_rows), 1)
        self.assertEqual(vendor_rows[0]['debit'], Decimal('0.00'))
        self.assertEqual(vendor_rows[0]['credit'], Decimal('1000.00'))
        self.assertEqual(response.context['closing_balance'], Decimal('-1000.00'))

    def test_vendor_supply_has_no_pay_button_in_statement(self):
        outward = Trip.objects.create(
            trip_date=timezone.localdate(),
            transaction_type='CUSTOMER_DELIVERY',
            customer=self.customer,
            quantity=1,
            rate=500,
            trip_status='COMPLETED',
        )
        response = self.client.get(
            reverse('ledger:customer_statement', args=[self.customer.id])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Outward sale keeps its Pay action (mobile + desktop markup)...
        self.assertContains(response, f'Pay \u20b9{outward.outstanding_amount:,.0f}')
        # ...but the inward vendor row must not offer Pay.
        self.assertEqual(content.count('Pay \u20b9'), 2)


class CustomerMobileUiTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='mobile-ui-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        customer_type, _ = CustomerType.objects.get_or_create(
            code='MOBILE-UI-TEST',
            defaults={'name': 'Mobile UI Test'},
        )
        Customer.objects.create(
            customer_code='MOB-ALPHA',
            name='Alpha Customer',
            customer_type=customer_type,
            opening_balance=Decimal('100.00'),
            is_active=True,
        )
        Customer.objects.create(
            customer_code='MOB-BETA',
            name='Beta Customer',
            customer_type=customer_type,
            opening_balance=Decimal('200.00'),
            is_active=True,
        )
        self.list_path = reverse('core:customer_report')

    def test_mobile_sort_dropdown_with_selected(self):
        response = self.client.get(f'{self.list_path}?sort=desc')

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="mobile-sort"', content)
        self.assertIn(
            f'<option value="{response.context["sort_desc_url"]}" selected>',
            content,
        )
        self.assertIn(
            f'<option value="{response.context["sort_asc_url"]}" >',
            content,
        )

    def test_overdue_pill_count(self):
        response = self.client.get(self.list_path)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['overdue_count'], 2)
        self.assertContains(response, '2 Overdue')

    def test_search_keeps_sort_param(self):
        response = self.client.get(f'{self.list_path}?sort=asc')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="sort" value="asc"')

    def test_mobile_cards_have_initials(self):
        response = self.client.get(self.list_path)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '>AC<')
        self.assertContains(response, '>BC<')
