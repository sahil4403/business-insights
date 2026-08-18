from django.contrib import admin
from .models import (
    Labour,
    LabourTypeAssignment,
    LabourEarning,
    LabourPayment,
    LabourSalaryPeriod,
)

@admin.register(Labour)
class LabourAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'mobile',
        'joining_date',
        'status',
        'is_active',
        'created_at',
    )

    list_filter = (
        'status',
        'is_active',
    )

    search_fields = (
        'name',
        'mobile',
    )

    ordering = (
        'name',
    )


@admin.register(LabourTypeAssignment)
class LabourTypeAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'labour',
        'labour_type',
        'payment_basis',
        'effective_from',
        'effective_to',
        'is_active',
    )

    list_filter = (
        'labour_type',
        'payment_basis',
        'is_active',
    )

    search_fields = (
        'labour__name',
        'labour_type__name',
    )

    ordering = (
        '-effective_from',
    )


@admin.register(LabourEarning)
class LabourEarningAdmin(admin.ModelAdmin):
    list_display = (
        'labour',
        'earning_type',
        'earning_date',
        'amount',
        'created_at',
    )

    list_filter = (
        'earning_type',
        'earning_date',
    )

    search_fields = (
        'labour__name',
    )

    ordering = (
        '-earning_date',
    )

@admin.register(LabourPayment)
class LabourPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'labour',
        'payment_type',
        'payment_date',
        'amount',
        'payment_method',
        'reference_number',
        'created_at',
    )

    list_filter = (
        'payment_type',
        'payment_method',
        'payment_date',
    )

    search_fields = (
        'labour__name',
        'reference_number',
    )

    ordering = (
        '-payment_date',
    )

@admin.register(LabourSalaryPeriod)
class LabourSalaryPeriodAdmin(admin.ModelAdmin):
    list_display = (
        'labour',
        'month',
        'year',
        'salary_amount',
        'display_total_advance',
        'display_net_payable',
        'status',
        'settled_at',
        'created_at',
    )

    list_filter = (
        'status',
        'year',
        'month',
    )

    search_fields = (
        'labour__name',
    )

    ordering = (
        '-year',
        '-month',
    )

    @admin.display(description='Total Advance')
    def display_total_advance(self, obj):
        return obj.total_advance

    @admin.display(description='Net Payable')
    def display_net_payable(self, obj):
        return obj.net_payable