from django.contrib import admin
from .models import (
    Role,
    PaymentMethod,
    LabourType,
    VehicleType,
    DocumentType,
    ExpenseCategory,
    CustomerType,
    Material,
)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'code',
        'name',
    )
    ordering = (
        'name',
    )


@admin.register(CustomerType)
class CustomerTypeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'code',
        'name',
    )
    ordering = (
        'name',
    )


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'code',
        'name',
    )
    ordering = (
        'name',
    )

@admin.register(LabourType)
class LabourTypeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'payment_basis',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'payment_basis',
        'is_active',
    )
    search_fields = (
        'code',
        'name',
    )
    ordering = (
        'name',
    )

@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'code',
        'name',
    )
    ordering = (
        'name',
    )


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'code',
        'name',
    )
    ordering = (
        'name',
    )

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'parent',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'is_active',
    )
    search_fields = (
        'code',
        'name',
    )
    ordering = (
        'name',
    )

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'unit',
        'gst_applicable',
        'gst_rate',
        'is_active',
        'created_at',
    )

    list_filter = (
        'unit',
        'gst_applicable',
        'is_active',
    )

    search_fields = (
        'code',
        'name',
    )

    ordering = (
        'name',
    )