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

    def test_edit_save_shows_popup_then_returns_to_origin(self):
        trip = self._make_trip()
        response = self.client.post(
            reverse('trips:edit', args=[trip.id]) + '?next=/trips/',
            data={
                'trip_date': timezone.localdate().isoformat(),
                'transaction_type': 'VENDOR_SUPPLY',
                'customer': str(self.customer.pk),
                'vehicle_category': 'HYVA',
                'quantity': '1',
                'rate': '0',
                'trip_status': 'COMPLETED',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('updated=1', response['Location'])
        self.assertIn('next=/trips/', response['Location'])

        popup_response = self.client.get(response['Location'])
        self.assertEqual(popup_response.status_code, 200)
        self.assertContains(popup_response, 'id="updated_modal"')
        self.assertContains(popup_response, 'href="/trips/"')

    def test_edit_success_message_reaches_origin_page(self):
        trip = self._make_trip()
        response = self.client.post(
            reverse('trips:edit', args=[trip.id]) + '?next=/trips/',
            data={
                'trip_date': timezone.localdate().isoformat(),
                'transaction_type': 'VENDOR_SUPPLY',
                'customer': str(self.customer.pk),
                'vehicle_category': 'HYVA',
                'quantity': '1',
                'rate': '0',
                'trip_status': 'COMPLETED',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        messages = [str(message) for message in response.context['messages']]
        self.assertTrue(
            any('updated successfully' in message for message in messages),
            f'success toast missing, got: {messages}',
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


class PaymentDeleteResilienceTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='payment-delete-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)

    def test_missing_payment_delete_redirects_instead_of_404(self):
        url = reverse('trips:payment_delete', args=[999999]) + '?next=/trips/'

        get_response = self.client.get(url)
        post_response = self.client.post(url)

        self.assertEqual(get_response.status_code, 302)
        self.assertEqual(get_response['Location'], '/trips/')
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response['Location'], '/trips/')

    def test_valid_payment_delete_still_works(self):
        customer_type, _ = CustomerType.objects.get_or_create(
            code='PAY-DEL-TEST',
            defaults={'name': 'Pay Delete Test'},
        )
        customer = Customer.objects.create(
            customer_code='PD-001',
            name='Pay Delete Customer',
            customer_type=customer_type,
            opening_balance=0,
            is_active=True,
        )
        trip = Trip.objects.create(
            trip_date=timezone.localdate(),
            transaction_type='CUSTOMER_DELIVERY',
            customer=customer,
            quantity=1,
            rate=100,
            trip_status='COMPLETED',
        )
        payment = trip.payments.create(
            payment_date=timezone.localdate(),
            amount=100,
            payment_type='RECEIVED',
        )

        response = self.client.post(
            reverse('trips:payment_delete', args=[payment.id]) + '?next=/trips/'
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/trips/')
        self.assertFalse(
            trip.payments.filter(pk=payment.id).exists()
        )


class TripPaymentPrefetchTest(TestCase):
    def test_received_uses_prefetched_payments_without_extra_queries(self):
        trip = Trip.objects.create(
            trip_date=timezone.localdate(),
            transaction_type='CUSTOMER_DELIVERY',
            quantity=1,
            rate=100,
            trip_status='COMPLETED',
        )
        trip.payments.create(
            payment_date=timezone.localdate(),
            amount=40,
            payment_type='RECEIVED',
        )

        trip = Trip.objects.prefetch_related('payments').get(pk=trip.pk)
        with self.assertNumQueries(0):
            received = trip.total_received
            outstanding = trip.outstanding_amount
            status = trip.calculated_payment_status

        self.assertEqual(received, 40)
        self.assertEqual(outstanding, trip.total_amount - 40)
        self.assertEqual(status, 'PARTIAL')


class TripListPaginationTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='trip-paging-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        for i in range(55):
            Trip.objects.create(
                trip_date=timezone.localdate(),
                transaction_type='CUSTOMER_DELIVERY',
                quantity=1,
                rate=100,
                trip_status='COMPLETED',
            )

    def test_list_paginates_fifty_per_page(self):
        page_one = self.client.get(reverse('trips:list'))
        page_two = self.client.get(reverse('trips:list'), {'page': 2})

        self.assertEqual(page_one.status_code, 200)
        self.assertEqual(page_two.status_code, 200)
        self.assertEqual(page_one.context['page_obj'].paginator.count, 55)
        self.assertEqual(len(page_one.context['page_obj'].object_list), 50)
        self.assertEqual(len(page_two.context['page_obj'].object_list), 5)
        # Summary full filtered set par based hai, page par nahi.
        self.assertEqual(page_one.context['summary']['total_count'], 55)
        self.assertContains(page_one, 'page=2')

    def test_dashboard_caps_trip_records(self):
        for _i in range(50):
            Trip.objects.create(
                trip_date=timezone.localdate(),
                transaction_type='CUSTOMER_DELIVERY',
                quantity=1,
                rate=100,
                trip_status='COMPLETED',
            )
        response = self.client.get(reverse('core:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['trips']), 100)
        self.assertTrue(response.context['trips_truncated'])
