from django.db import models


class Role(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True
    )
    name = models.CharField(
        max_length=100,
        unique=True
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


class PaymentMethod(models.Model):
    code = models.CharField(
         max_length=50,
         unique=True
    )
    name = models.CharField(
        max_length=100,
        unique=True
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


class LabourType(models.Model):
    PAYMENT_BASIS_CHOICES = [
        ('DAILY', 'Daily'),
        ('MONTHLY', 'Monthly'),
        ('PER_ENTRY', 'Per Entry'),
    ]

    code = models.CharField(
        max_length=50,
        unique=True
    )
    name = models.CharField(
        max_length=100,
        unique=True
    )
    payment_basis = models.CharField(
        max_length=20,
        choices=PAYMENT_BASIS_CHOICES
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

class VehicleType(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True
    )
    name = models.CharField(
        max_length=100,
        unique=True
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

class DocumentType(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True
    )
    name = models.CharField(
        max_length=100,
        unique=True
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

class ExpenseCategory(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True
    )
    name = models.CharField(
        max_length=100,
        unique=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='subcategories'
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


class CustomerType(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True
    )
    name = models.CharField(
        max_length=100,
        unique=True
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

class Material(models.Model):
    UNIT_CHOICES = [
        ('TRIP', 'Trip'),
        ('PIECE', 'Piece'),
    ]

    code = models.CharField(
        max_length=50,
        unique=True
    )
    name = models.CharField(
        max_length=150,
        unique=True
    )
    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES
    )
    gst_applicable = models.BooleanField(
        default=False
    )
    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
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