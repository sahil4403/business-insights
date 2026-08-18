from django.db import models
from master_data.models import VehicleType


class Vehicle(models.Model):
    OWNERSHIP_CHOICES = [
        ('OWNED', 'Owned'),
        ('HIRED', 'Hired'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('MAINTENANCE', 'Maintenance'),
    ]

    vehicle_code = models.CharField(
        max_length=30,
        unique=True
    )

    vehicle_type = models.ForeignKey(
        VehicleType,
        on_delete=models.PROTECT,
        related_name='vehicles'
    )

    registration_number = models.CharField(
        max_length=20,
        unique=True
    )

    capacity_cft = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    ownership_type = models.CharField(
        max_length=10,
        choices=OWNERSHIP_CHOICES,
        default='OWNED'
    )

    owner_name = models.CharField(
        max_length=200,
        blank=True
    )

    status = models.CharField(
        max_length=15,
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
        ordering = ['registration_number']

    def __str__(self):
        return f"{self.registration_number} - {self.vehicle_type.name}"