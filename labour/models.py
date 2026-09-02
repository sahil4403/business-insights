from decimal import Decimal

from django.db import models
from master_data.models import LabourType


class Labour(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]

    CATEGORY_CHOICES = [
        ('TRACTOR', 'Tractor'),
        ('HYVA_DRIVER', 'Hyva Driver'),
        ('JCB_OPERATOR', 'JCB Operator'),
        ('MISTRI', 'Mistri'),
    ]

    # Sub-category for MISTRI — distinguishes the Mistri himself (fixed ₹800)
    # from his Helper/Labour (variable base daily rate).
    MISTRI_SUB_CATEGORY_CHOICES = [
        ('MISTRI', 'Mistri'),
        ('HELPER', 'Mistri Helper (Labour)'),
    ]

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='TRACTOR',
        help_text="Worker category — Tractor (driver+labour), Hyva Driver, JCB Operator or Mistri (incl. labour)"
    )

    sub_category = models.CharField(
        max_length=20,
        choices=MISTRI_SUB_CATEGORY_CHOICES,
        blank=True,
        default='',
        help_text="For Mistri category — Mistri (fixed ₹800/day) or Mistri Helper/Labour (variable base rate)"
    )

    name = models.CharField(
        max_length=200
    )

    mobile = models.CharField(
        max_length=15,
        blank=True
    )

    joining_date = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )

    description = models.TextField(
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    is_driver = models.BooleanField(
        default=False,
        help_text="Mark if this labour also gets Driver Payment"
    )

    is_vendor = models.BooleanField(
        default=False,
        help_text="Auto-created placeholder for a vendor's own driver "
                  "(<Customer> Driver). Hidden from daily labour lists so "
                  "no advances/payments are tracked for it."
    )

    base_daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('500'),
        help_text="Base daily rate (Rozi full day). One & Half = 1.5x, Half = 0.5x"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def current_old_balance(self):
        ob = LabourOldBalance.objects.filter(labour=self).first()
        return ob.amount if ob else 0


class LabourTypeAssignment(models.Model):
    PAYMENT_BASIS_CHOICES = [
        ('DAILY', 'Daily'),
        ('MONTHLY', 'Monthly'),
    ]

    labour = models.ForeignKey(
        Labour,
        on_delete=models.PROTECT,
        related_name='type_assignments'
    )

    labour_type = models.ForeignKey(
        LabourType,
        on_delete=models.PROTECT,
        related_name='assignments'
    )

    payment_basis = models.CharField(
        max_length=10,
        choices=PAYMENT_BASIS_CHOICES
    )

    effective_from = models.DateField(
        null=True,
        blank=True
    )

    effective_to = models.DateField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        # Effective date validation
        if (
                self.effective_from
                and self.effective_to
                and self.effective_to < self.effective_from
        ):
            raise ValidationError(
                "Effective To date cannot be earlier than Effective From date."
            )

        # Payment basis must match Labour Type master
        if self.labour_type:
            expected_basis = self.labour_type.payment_basis

            if expected_basis != self.payment_basis:
                raise ValidationError(
                    f"{self.labour_type.name} must use "
                    f"{expected_basis.lower().replace('_', ' ')} payment basis."
                )

        # Check overlapping active assignments
        if self.labour and self.labour_type:
            assignments = LabourTypeAssignment.objects.filter(
                labour=self.labour,
                labour_type=self.labour_type,
                is_active=True,
            ).exclude(pk=self.pk)

            for assignment in assignments:

                existing_start = assignment.effective_from
                existing_end = assignment.effective_to

                new_start = self.effective_from
                new_end = self.effective_to

                # If either assignment has no start date,
                # date overlap cannot be determined.
                if not existing_start or not new_start:
                    continue

                # Existing assignment has no end date (open-ended)
                if existing_end is None:

                    if new_end is None or new_end >= existing_start:
                        raise ValidationError(
                            "An active assignment for this labour and "
                            "labour type already exists."
                        )

                # Existing assignment has an end date
                else:

                    if new_end is None:

                        if new_start <= existing_end:
                            raise ValidationError(
                                "The assignment dates overlap with "
                                "an existing active assignment."
                            )

                    elif (
                            new_start <= existing_end
                            and new_end >= existing_start
                    ):
                        raise ValidationError(
                            "The assignment dates overlap with "
                            "an existing active assignment."
                        )

    class Meta:
        ordering = ['-effective_from']


    def __str__(self):
        return f"{self.labour.name} - {self.labour_type.name}"

class LabourEarning(models.Model):
    EARNING_TYPE_CHOICES = [
        ('DAILY_WAGE', 'Daily Wage'),
        ('MONTHLY_SALARY', 'Monthly Salary'),
    ]

    labour = models.ForeignKey(
        Labour,
        on_delete=models.PROTECT,
        related_name='earnings'
    )

    earning_type = models.CharField(
        max_length=20,
        choices=EARNING_TYPE_CHOICES
    )

    earning_date = models.DateField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    description = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['-earning_date']

    def __str__(self):
        return f"{self.labour.name} - {self.earning_type} - {self.amount}"

class LabourPayment(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('ADVANCE', 'Advance'),
        ('SALARY', 'Salary / Settlement'),
    ]

    labour = models.ForeignKey(
        Labour,
        on_delete=models.PROTECT,
        related_name='payments'
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES
    )

    payment_date = models.DateField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    payment_method = models.ForeignKey(
        'master_data.PaymentMethod',
        on_delete=models.PROTECT,
        related_name='labour_payments'
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.amount is not None and self.amount <= 0:
            raise ValidationError(
                "Payment amount must be greater than zero."
            )

        if not self.labour:
            raise ValidationError(
                "Labour is required."
            )

        if not self.payment_method:
            raise ValidationError(
                "Payment method is required."
            )

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.labour.name} - {self.payment_type} - {self.amount}"

class LabourSalaryPeriod(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('SETTLED', 'Settled'),
    ]

    labour = models.ForeignKey(
        Labour,
        on_delete=models.PROTECT,
        related_name='salary_periods'
    )

    year = models.PositiveIntegerField()

    month = models.PositiveSmallIntegerField()

    salary_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='OPEN'
    )

    settled_at = models.DateTimeField(
        null=True,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    @property
    def total_advance(self):
        from django.db.models import Sum
        from calendar import monthrange
        from datetime import date

        start_date = date(self.year, self.month, 1)
        end_date = date(
            self.year,
            self.month,
            monthrange(self.year, self.month)[1]
        )

        total = self.labour.payments.filter(
            payment_type='ADVANCE',
            payment_date__gte=start_date,
            payment_date__lte=end_date,
        ).aggregate(
            total=Sum('amount')
        )['total']

        return total or 0

    @property
    def net_payable(self):
        balance = self.salary_amount - self.total_advance

        return max(balance, 0)

    def __str__(self):
        return f"{self.labour.name} - {self.month}/{self.year}"

    class Meta:
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(
                fields=['labour', 'year', 'month'],
                name='unique_labour_salary_period'
            )
        ]


# =========================================================================
# NEW LABOUR FEATURE MODELS — flexible per-trip groups, advances,
# extras, driver payments, old balance & settlement.
# Existing Labour model above is shared (with added is_driver flag).
# =========================================================================


class LabourTripGroup(models.Model):
    """
    One row per "group" of labourers who worked a batch of trips together.
    A single day can have any number of these rows — owner creates a new
    row every time the worker group changes.
    """
    FILL_TYPE_CHOICES = [
        ('HAND', 'Hand'),
        ('JCB', 'JCB'),
    ]

    date = models.DateField()
    trip_count = models.PositiveIntegerField()
    rate_per_trip = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=450,
        help_text="Per-trip rate (default ₹450)",
    )
    fill_type = models.CharField(
        max_length=10,
        choices=FILL_TYPE_CHOICES,
        default='HAND',
    )
    HYVA_LOAD_CHOICES = [
        ('', '— (Tractor trip)'),
        ('WHITE_HYVA', 'White Sand Hyva'),
        ('FLYASH_HYVA', 'Fly Ash Hyva'),
        ('HALFTON_WHITE', 'Halfton White'),
        ('HALFTON_FLYASH', 'Halfton Fly Ash'),
    ]
    HYVA_LOAD_RATES = {
        'WHITE_HYVA': '200',
        'FLYASH_HYVA': '100',
        'HALFTON_WHITE': '100',
        'HALFTON_FLYASH': '100',
    }
    load_type = models.CharField(
        max_length=20,
        choices=HYVA_LOAD_CHOICES,
        blank=True,
        default='',
        help_text="Hyva load type — sets the per-trip rate automatically",
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
    )
    labourers = models.ManyToManyField(
        Labour,
        related_name='trip_groups',
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']

    def save(self, *args, **kwargs):
        if self.load_type in self.HYVA_LOAD_RATES:
            self.rate_per_trip = Decimal(self.HYVA_LOAD_RATES[self.load_type])
        self.total_amount = self.trip_count * self.rate_per_trip
        super().save(*args, **kwargs)

    def __str__(self):
        names = ', '.join(self.labourers.values_list('name', flat=True)[:3])
        return f"{self.date} · {self.trip_count} trips · {names}"

    @property
    def load_label(self):
        if not self.load_type:
            return ''
        return dict(self.HYVA_LOAD_CHOICES).get(self.load_type, '')

    @property
    def per_labour_share(self):
        n = self.labourers.count()
        if not n:
            return 0
        return self.total_amount / n


class LabourExtraPayment(models.Model):
    """Optional extra work payment (variable bonus)."""
    labour = models.ForeignKey(
        Labour,
        on_delete=models.CASCADE,
        related_name='extra_payments',
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.labour.name} · {self.date} · ₹{self.amount}"


class LabourAdvance(models.Model):
    """Daily cash advance (only created if advance was actually taken)."""
    labour = models.ForeignKey(
        Labour,
        on_delete=models.CASCADE,
        related_name='advances',
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['labour', 'date'],
                name='unique_advance_per_labour_per_day',
            )
        ]

    def __str__(self):
        return f"{self.labour.name} · {self.date} · ₹{self.amount}"


class LabourRozi(models.Model):
    """Daily rozi (wages) for a labourer — full / one-and-half / half day.

    For Mistri category: FIXED rates ₹800 / ₹1200 / ₹400.
    For other categories: base_daily_rate × multiplier.
    """

    DAY_TYPE_CHOICES = [
        ('FULL', 'Full Day'),
        ('ONE_HALF', 'One & Half Day'),
        ('HALF', 'Half Day'),
    ]
    DAY_MULTIPLIER = {
        'FULL': Decimal('1.0'),
        'ONE_HALF': Decimal('1.5'),
        'HALF': Decimal('0.5'),
    }

    # Mistri fixed rates (overrides base_daily_rate)
    MISTRI_RATES = {
        'FULL': Decimal('800'),
        'ONE_HALF': Decimal('1200'),
        'HALF': Decimal('400'),
    }

    labour = models.ForeignKey(
        Labour,
        on_delete=models.CASCADE,
        related_name='rozis',
    )
    date = models.DateField()
    day_type = models.CharField(
        max_length=10,
        choices=DAY_TYPE_CHOICES,
        default='FULL',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def save(self, *args, **kwargs):
        if self.day_type in self.DAY_MULTIPLIER:
            if self.labour.category == 'MISTRI' and self.labour.sub_category == 'MISTRI':
                self.amount = self.MISTRI_RATES[self.day_type]
            else:
                self.amount = (
                    self.labour.base_daily_rate * self.DAY_MULTIPLIER[self.day_type]
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.labour.name} · {self.date} · ₹{self.amount}"


class LabourDriverPayment(models.Model):
    """Manual driver payment for a settlement period (labour.is_driver=True)."""
    labour = models.ForeignKey(
        Labour,
        on_delete=models.CASCADE,
        related_name='driver_payments',
    )
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period_end', '-id']

    def __str__(self):
        return f"{self.labour.name} driver · {self.period_start}→{self.period_end} · ₹{self.amount}"


class LabourOldBalance(models.Model):
    """
    Running outstanding balance owed BY the labour TO the owner.
    Positive = labour still owes owner.
    """
    labour = models.OneToOneField(
        Labour,
        on_delete=models.CASCADE,
        related_name='old_balance',
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.labour.name} old balance ₹{self.amount}"


class LabourSettlement(models.Model):
    """Settlement record. Snapshot of totals + owner-entered deductions."""
    labour = models.ForeignKey(
        Labour,
        on_delete=models.CASCADE,
        related_name='settlements',
    )
    settlement_date = models.DateField()
    period_start = models.DateField()
    period_end = models.DateField()

    # Calculated snapshots
    total_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Trip shares + extras + driver payment",
    )
    total_advance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )
    net_payable = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="total_salary - total_advance",
    )
    old_balance_before = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )

    # Owner-entered
    old_balance_deducted = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )
    cash_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )

    # Calculated: old_balance_before + net_payable - old_balance_deducted - cash_paid
    final_old_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )

    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-settlement_date', '-id']

    def __str__(self):
        return f"{self.labour.name} settle {self.settlement_date}"

    def recalculate(self):
        """Recompute all calculated fields and write to LabourOldBalance."""
        from django.db.models import Sum, Q
        from decimal import Decimal

        period_q = Q(date__gte=self.period_start, date__lte=self.period_end)

        # Trip shares for this labour
        trip_total = Decimal('0')
        for grp in LabourTripGroup.objects.filter(date__gte=self.period_start,
                                                  date__lte=self.period_end):
            n = grp.labourers.count()
            if n and grp.labourers.filter(pk=self.labour.pk).exists():
                trip_total += grp.total_amount / n

        extra_total = LabourExtraPayment.objects.filter(
            labour=self.labour, date__gte=self.period_start, date__lte=self.period_end
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        rozi_total = LabourRozi.objects.filter(
            labour=self.labour, date__gte=self.period_start, date__lte=self.period_end
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        driver_total = LabourDriverPayment.objects.filter(
            labour=self.labour,
            period_start__lte=self.period_end,
            period_end__gte=self.period_start,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        advance_total = LabourAdvance.objects.filter(
            labour=self.labour, date__gte=self.period_start, date__lte=self.period_end
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        self.total_salary = trip_total + extra_total + rozi_total + driver_total
        self.total_advance = advance_total
        self.net_payable = self.total_salary - self.total_advance
        self.final_old_balance = (
            self.old_balance_before + self.net_payable
            - self.old_balance_deducted - self.cash_paid
        )
        return self

