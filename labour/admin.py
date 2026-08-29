from django.contrib import admin
from .models import (
    Labour,
    LabourTypeAssignment,
    LabourEarning,
    LabourPayment,
    LabourSalaryPeriod,
    LabourTripGroup,
    LabourExtraPayment,
    LabourAdvance,
    LabourDriverPayment,
    LabourOldBalance,
    LabourSettlement,
)

@admin.register(Labour)
class LabourAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'mobile',
        'joining_date',
        'is_driver',
        'status',
        'is_active',
        'created_at',
    )

    list_filter = (
        'status',
        'is_active',
        'is_driver',
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


# =========================================================================
# New feature admin registrations
# =========================================================================

@admin.register(LabourTripGroup)
class LabourTripGroupAdmin(admin.ModelAdmin):
    list_display = ('date', 'trip_count', 'rate_per_trip', 'total_amount', 'fill_type')
    list_filter = ('date', 'fill_type')
    search_fields = ('note',)
    filter_horizontal = ('labourers',)
    date_hierarchy = 'date'
    ordering = ('-date', '-id')


@admin.register(LabourExtraPayment)
class LabourExtraPaymentAdmin(admin.ModelAdmin):
    list_display = ('labour', 'date', 'amount', 'note')
    list_filter = ('date',)
    search_fields = ('labour__name', 'note')
    date_hierarchy = 'date'
    ordering = ('-date', '-id')


@admin.register(LabourAdvance)
class LabourAdvanceAdmin(admin.ModelAdmin):
    list_display = ('labour', 'date', 'amount', 'note')
    list_filter = ('date',)
    search_fields = ('labour__name', 'note')
    date_hierarchy = 'date'
    ordering = ('-date', '-id')


@admin.register(LabourDriverPayment)
class LabourDriverPaymentAdmin(admin.ModelAdmin):
    list_display = ('labour', 'period_start', 'period_end', 'amount')
    list_filter = ('period_end',)
    search_fields = ('labour__name',)
    ordering = ('-period_end', '-id')


@admin.register(LabourOldBalance)
class LabourOldBalanceAdmin(admin.ModelAdmin):
    list_display = ('labour', 'amount', 'last_updated')
    search_fields = ('labour__name',)
    ordering = ('-amount',)


@admin.register(LabourSettlement)
class LabourSettlementAdmin(admin.ModelAdmin):
    list_display = (
        'labour', 'settlement_date', 'period_start', 'period_end',
        'total_salary', 'total_advance', 'net_payable',
        'old_balance_before', 'old_balance_deducted', 'cash_paid',
        'final_old_balance',
    )
    list_filter = ('settlement_date',)
    search_fields = ('labour__name',)
    date_hierarchy = 'settlement_date'
    ordering = ('-settlement_date', '-id')