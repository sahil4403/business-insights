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

class VehicleDocument(models.Model):
    """
    Vehicle ke documents (PUC, Insurance, Fitness, Permit, RC, Tax)
    + expiry notification tracking (30/15/7 din pehle + expired).
    """

    DOC_TYPE_CHOICES = [
        ('PUC', 'PUC Certificate'),
        ('INSURANCE', 'Insurance'),
        ('FITNESS', 'Fitness Certificate'),
        ('PERMIT', 'Permit'),
        ('RC', 'RC Book'),
        ('TAX', 'Road Tax'),
        ('OTHER', 'Other'),
    ]

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='documents'
    )

    doc_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES
    )

    document_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Policy/Certificate number (optional)"
    )

    issue_date = models.DateField(
        null=True,
        blank=True
    )

    expiry_date = models.DateField(
        db_index=True
    )

    file = models.FileField(
        upload_to='vehicle_docs/',
        null=True,
        blank=True,
        help_text="PDF/Photo upload (optional)"
    )

    notes = models.TextField(
        blank=True
    )

    # ---- Notification dedupe flags (ek window me ek hi baar WhatsApp) ----
    notified_30 = models.BooleanField(default=False)
    notified_15 = models.BooleanField(default=False)
    notified_7 = models.BooleanField(default=False)
    notified_expired = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expiry_date', 'id']

    @property
    def days_left(self):
        from django.utils import timezone
        return (self.expiry_date - timezone.localdate()).days

    @property
    def urgency(self):
        d = self.days_left
        if d < 0:
            return 'expired'
        if d <= 7:
            return 'critical'
        if d <= 15:
            return 'warning'
        if d <= 30:
            return 'info'
        return 'ok'

    def __str__(self):
        return f"{self.vehicle.registration_number} - {self.get_doc_type_display()} ({self.expiry_date})"
