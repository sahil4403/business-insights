from decimal import Decimal
from django.db import models
from django.utils import timezone

from customers.models import Customer
from vehicles.models import Vehicle
from master_data.models import Material
from labour.models import Labour


class Trip(models.Model):
    TRIP_STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
    ]

    trip_code = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        editable=False
    )

    trip_date = models.DateField(db_index=True)

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='trips',
        null=True,
        blank=True
    )

    destination = models.CharField(
        max_length=200,
        blank=True,
        default=''
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name='trips',
        null=True,
        blank=True
    )

    material = models.ForeignKey(
        Material,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trips'
    )

    TRANSACTION_TYPE_CHOICES = [
        ('CUSTOMER_DELIVERY', 'Customer Delivery (Outward)'),
        ('VENDOR_SUPPLY', 'Vendor/Supplier Material (Inward)'),
        ('INTERNAL_STOCK', 'Internal Stock'),
    ]

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        default='CUSTOMER_DELIVERY'
    )

    drivers = models.ManyToManyField(
        Labour,
        blank=True,
        related_name='trips_driven'
    )

    driver_trip_counts = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores trip counts completed per driver, e.g. {'18': 3, '6': 2}"
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    rate = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    trip_status = models.CharField(
        max_length=20,
        choices=TRIP_STATUS_CHOICES,
        default='PLANNED'
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='UNPAID'
    )

    notes = models.TextField(
        blank=True
    )

    # Linked inward trip (for outward trips created from inward)
    linked_inward_trip = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='linked_outward_trips',
        help_text='VENDOR_SUPPLY inward trip jisse ye outward bana'
    )

    # JCB Specific Fields
    start_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="JCB Hour Meter Starting Reading (e.g. 1233.2)"
    )

    end_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="JCB Hour Meter Ending Reading (e.g. 1235.1)"
    )

    total_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total Hours Worked = End Reading - Start Reading"
    )

    driver_bhatta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True,
        help_text="Driver Bhatta Allowance (Applicable for JCB trips, Default ₹200.00 for JCB)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.quantity <= 0:
            raise ValidationError(
                "Quantity must be greater than zero."
            )

        if self.rate < 0:
            raise ValidationError(
                "Rate cannot be negative."
            )

        if self.material and self.material.unit not in ('TRIP', 'PIECE'):
            raise ValidationError(
                "Material must have a valid unit: Trip or Piece."
            )

    def save(self, *args, **kwargs):
        category = getattr(self, 'temp_category', None)
        is_jcb = False
        if category and str(category).upper() == 'JCB':
            is_jcb = True
        elif self.vehicle and 'JCB' in str(self.vehicle).upper():
            is_jcb = True
        elif self.start_reading is not None or self.end_reading is not None or self.total_hours is not None:
            is_jcb = True

        if is_jcb:
            if not self.driver_bhatta or self.driver_bhatta == Decimal('0.00'):
                self.driver_bhatta = Decimal('200.00')
            jcb_mat, _ = Material.objects.get_or_create(
                name='JCB Work',
                defaults={'unit': 'TRIP', 'description': 'JCB Excavator & Earthmover Work', 'is_active': True}
            )
            self.material = jcb_mat
        else:
            if not getattr(self, 'bhatta_manually_set', False):
                self.driver_bhatta = Decimal('0.00')

        bhatta = self.driver_bhatta if self.driver_bhatta is not None else Decimal('0.00')
        self.total_amount = (self.quantity * self.rate) + bhatta

        if not self.material:
            default_mat = Material.objects.filter(is_active=True).first()
            if default_mat:
                self.material = default_mat

        category = getattr(self, 'temp_category', None)
        if not self.vehicle and category:
            from vehicles.models import Vehicle
            veh_code = f"VEH-{category.upper()}"
            v_match = Vehicle.objects.filter(vehicle_code=veh_code).first()
            if not v_match:
                v_match = Vehicle.objects.filter(vehicle_type__code=category.upper()).first()
            if v_match:
                self.vehicle = v_match

        if not self.trip_code:
            super().save(*args, **kwargs)

            category = getattr(self, 'temp_category', 'HYVA')
            if category == 'TRACTOR':
                self.trip_code = f"TRIP-T-{self.pk:05d}"
            elif category == 'HALFTON':
                self.trip_code = f"TRIP-HF-{self.pk:05d}"
            elif category == 'JCB':
                self.trip_code = f"TRIP-JCB-{self.pk:05d}"
            else:
                self.trip_code = f"TRIP-{self.pk:06d}"

            type(self).objects.filter(
                pk=self.pk
            ).update(
                trip_code=self.trip_code,
                vehicle=self.vehicle
            )

            return

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-trip_date', '-id']

    @property
    def total_received(self):
        from django.db.models import Sum

        total = self.payments.aggregate(
            total=Sum('amount')
        )['total']

        return total or 0

    @property
    def outstanding_amount(self):
        return max(
            self.total_amount - self.total_received,
            0
        )

    @property
    def get_driver_breakdown(self):
        breakdown = []
        counts = self.driver_trip_counts or {}
        for d in self.drivers.all():
            cnt = counts.get(str(d.id)) or counts.get(int(d.id))
            breakdown.append({
                'driver': d,
                'count': cnt
            })
        return breakdown

    @property
    def calculated_payment_status(self):
        if self.total_received <= 0:
            return 'UNPAID'

        if self.total_received < self.total_amount:
            return 'PARTIAL'

        return 'PAID'

    def __str__(self):
        customer_name = self.customer.name if self.customer else 'Internal Stock'
        return f"{self.trip_code} - {customer_name}"

class TripPayment(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.PROTECT,
        related_name='payments',
        null=True,
        blank=True
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        related_name='payments',
        null=True,
        blank=True
    )
    payment_code = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    PAYMENT_TYPE_CHOICES = [
        ('RECEIVED', 'Payment Received from Customer'),
        ('PAID', 'Payment Paid to Vendor/Customer'),
        ('CONTRA', 'Contra Settlement (Netting Off)'),
    ]

    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='RECEIVED'
    )

    payment_date = models.DateField(
        null=True,
        blank=True,
        db_index=True
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    payment_method = models.ForeignKey(
        'master_data.PaymentMethod',
        on_delete=models.PROTECT,
        related_name='trip_payments',
        null=True,
        blank=True
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def save(self, *args, **kwargs):
        # A payment without a date is invisible in reports/statements —
        # never allow blank dates; default to today.
        if not self.payment_date:
            self.payment_date = timezone.localdate()
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.amount is None or self.amount <= 0:
            raise ValidationError(
                "Payment amount must be greater than zero."
            )

        if not self.trip and not self.customer:
            raise ValidationError(
                "Either a Trip or a Customer must be specified for payment."
            )

        if self.trip:
            total_paid = self.trip.payments.exclude(
                pk=self.pk
            ).aggregate(
                total=models.Sum('amount')
            )['total'] or 0

            if total_paid + self.amount > self.trip.total_amount:
                raise ValidationError(
                    "Payment amount cannot be greater than "
                    "the remaining outstanding amount."
                )

    class Meta:
        ordering = ['-payment_date', '-id']

    def __str__(self):
        ref = self.trip.trip_code if self.trip else (self.customer.name if self.customer else "On-Account")
        return f"{ref} - ₹{self.amount}"