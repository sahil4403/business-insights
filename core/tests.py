import html
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from master_data.models import CustomerType


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
