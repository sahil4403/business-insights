from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer
from labour.models import Labour
from master_data.models import CustomerType

from .models import Trip


class VendorDriverTripCreateTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='vendor-trip-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        customer_type, _ = CustomerType.objects.get_or_create(
            code='VENDOR-TRIP-TEST',
            defaults={'name': 'Vendor Trip Test'},
        )
        self.customer = Customer.objects.create(
            customer_code='VT-001',
            name='Sharma Construction',
            customer_type=customer_type,
            opening_balance=0,
            is_active=True,
        )

    def test_vendor_supply_accepts_option_text_vendor_driver(self):
        option_text_driver = f'{self.customer} Driver'
        response = self.client.post(
            reverse('trips:create'),
            data={
                'trip_date': timezone.localdate().isoformat(),
                'transaction_type': 'VENDOR_SUPPLY',
                'customer': str(self.customer.pk),
                'vehicle_category': 'HYVA',
                'quantity': '1',
                'rate': '0',
                'trip_status': 'COMPLETED',
                'vendor_driver_name': option_text_driver,
                'vendor_driver_count': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        trip = Trip.objects.get(customer=self.customer)
        self.assertEqual(
            [driver.name for driver in trip.drivers.all()],
            [option_text_driver],
        )
        self.assertTrue(
            Labour.objects.filter(name=option_text_driver).exists()
        )
