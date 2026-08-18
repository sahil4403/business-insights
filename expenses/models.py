from django.db import models

from labour.models import Labour
from master_data.models import PaymentMethod
from trips.models import Trip
from vehicles.models import Vehicle
from decimal import Decimal

from django.core.validators import MinValueValidator

class Expense(models.Model):

    expense_date = models.DateField()

    category = models.ForeignKey(
        'master_data.ExpenseCategory',
        on_delete=models.PROTECT,
        related_name='expenses'
    )

    description = models.CharField(
        max_length=255
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.01'))
        ]
    )

    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='expenses'
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name='expenses',
        null=True,
        blank=True
    )

    trip = models.ForeignKey(
        Trip,
        on_delete=models.PROTECT,
        related_name='expenses',
        null=True,
        blank=True
    )

    labour = models.ForeignKey(
        Labour,
        on_delete=models.PROTECT,
        related_name='expenses',
        null=True,
        blank=True
    )

    paid_to = models.CharField(
        max_length=150,
        blank=True
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    include_in_profit = models.BooleanField(
        default=True,
        help_text="Include this expense in business profit calculation."
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return (
            f"{self.expense_date} - "
            f"{self.category} - "
            f"₹{self.amount}"
        )