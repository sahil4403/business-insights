from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'customer_code',
        'name',
        'customer_type',
        'mobile',
        'city',
        'opening_balance',
        'gstin',
        'is_active',
        'created_at',
        'view_statement',
    )

    list_editable = (
        'opening_balance',
    )

    list_filter = (
        'customer_type',
        'is_active',
        'state',
    )

    search_fields = (
        'customer_code',
        'name',
        'mobile',
        'gstin',
        'pan',
    )

    ordering = (
        'name',
    )

    @admin.display(description='Statement')
    def view_statement(self, obj):
        url = reverse(
            'ledger:customer_statement',
            args=[obj.pk]
        )

        return format_html(
            '<a href="{}" target="_blank">View Statement</a>',
            url
        )
