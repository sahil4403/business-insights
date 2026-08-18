from django.contrib import admin
from django.db.models import Sum

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):

    list_display = (
        'expense_date',
        'category',
        'description',
        'amount',
        'payment_method',
        'vehicle',
        'trip',
        'labour',
        'paid_to',
    )

    list_filter = (
        'category',
        'payment_method',
        'expense_date',
        'vehicle',
        'trip',
        'labour',
    )

    search_fields = (
        'description',
        'paid_to',
        'reference_number',
        'notes',
        'category__name',
        'payment_method__name',
    )

    date_hierarchy = 'expense_date'

    ordering = (
        '-expense_date',
        '-id',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
    )

    list_per_page = 25

    def changelist_view(self, request, extra_context=None):

        response = super().changelist_view(
            request,
            extra_context=extra_context,
        )

        try:
            filtered_queryset = response.context_data['cl'].queryset

            total_expense = (
                filtered_queryset.aggregate(
                    total=Sum('amount')
                )['total']
                or 0
            )

            response.context_data['total_expense'] = (
                total_expense
            )

        except (AttributeError, KeyError):
            pass

        return response