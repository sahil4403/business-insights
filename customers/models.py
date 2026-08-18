from django.db import models
from master_data.models import CustomerType


class Customer(models.Model):
    customer_code = models.CharField(
        max_length=30,
        unique=True
    )
    name = models.CharField(
        max_length=200
    )
    customer_type = models.ForeignKey(
        CustomerType,
        on_delete=models.PROTECT,
        related_name='customers'
    )

    mobile = models.CharField(
        max_length=15,
        blank=True
    )
    alternate_mobile = models.CharField(
        max_length=15,
        blank=True
    )
    email = models.EmailField(
        blank=True
    )

    billing_address = models.TextField(
        blank=True
    )
    city = models.CharField(
        max_length=100,
        blank=True
    )
    state = models.CharField(
        max_length=100,
        blank=True
    )
    pincode = models.CharField(
        max_length=10,
        blank=True
    )

    gstin = models.CharField(
        max_length=15,
        blank=True
    )
    pan = models.CharField(
        max_length=10,
        blank=True
    )

    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    payment_terms_days = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Starting outstanding amount for this customer (editable anytime).'
    )

    is_vendor = models.BooleanField(
        default=False,
        help_text='Check if party is also a Material Supplier/Vendor (Dual-role).'
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
        return f"{self.customer_code} - {self.name}"