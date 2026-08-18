from django.db import models
from master_data.models import LabourType


class Labour(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]

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

