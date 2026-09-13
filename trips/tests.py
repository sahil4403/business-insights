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


class VendorDriverTripEditTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='vendor-trip-edit-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        customer_type, _ = CustomerType.objects.get_or_create(
            code='VENDOR-TRIP-EDIT-TEST',
            defaults={'name': 'Vendor Trip Edit Test'},
        )
        self.customer = Customer.objects.create(
            customer_code='VE-001',
            name='Verma Suppliers',
            customer_type=customer_type,
            opening_balance=0,
            is_active=True,
        )
        self.option_text_driver = f'{self.customer} Driver'

    def _make_trip(self):
        return Trip.objects.create(
            trip_date=timezone.localdate(),
            transaction_type='VENDOR_SUPPLY',
            customer=self.customer,
            quantity=1,
            rate=0,
            trip_status='COMPLETED',
        )

    def test_edit_page_shows_linked_vendor_driver(self):
        trip = self._make_trip()
        driver = Labour.objects.create(
            name=self.option_text_driver,
            category='HYVA_DRIVER',
            is_active=True,
            status='ACTIVE',
            is_driver=True,
            is_vendor=True,
        )
        trip.drivers.add(driver)

        response = self.client.get(reverse('trips:edit', args=[trip.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.option_text_driver)

    def test_edit_assigns_vendor_driver_to_old_trip(self):
        trip = self._make_trip()
        response = self.client.post(
            reverse('trips:edit', args=[trip.id]),
            data={
                'trip_date': timezone.localdate().isoformat(),
                'transaction_type': 'VENDOR_SUPPLY',
                'customer': str(self.customer.pk),
                'vehicle_category': 'HYVA',
                'quantity': '1',
                'rate': '0',
                'trip_status': 'COMPLETED',
                'vendor_driver_name': self.option_text_driver,
                'vendor_driver_count': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        trip.refresh_from_db()
        self.assertEqual(
            [driver.name for driver in trip.drivers.all()],
            [self.option_text_driver],
        )

    def test_edit_keeps_existing_driver_and_adds_vendor_driver(self):
        trip = self._make_trip()
        existing = Labour.objects.create(
            name='Gaju Bhau',
            category='HYVA_DRIVER',
            is_active=True,
            status='ACTIVE',
            is_driver=True,
        )
        trip.drivers.add(existing)
        response = self.client.post(
            reverse('trips:edit', args=[trip.id]),
            data={
                'trip_date': timezone.localdate().isoformat(),
                'transaction_type': 'VENDOR_SUPPLY',
                'customer': str(self.customer.pk),
                'vehicle_category': 'HYVA',
                'quantity': '1',
                'rate': '0',
                'trip_status': 'COMPLETED',
                'drivers': [str(existing.pk)],
                'vendor_driver_name': self.option_text_driver,
                'vendor_driver_count': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        trip.refresh_from_db()
        self.assertEqual(
            sorted(driver.name for driver in trip.drivers.all()),
            sorted(['Gaju Bhau', self.option_text_driver]),
        )
