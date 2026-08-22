from django.urls import path

from .views import (
    dashboard,
    customer_report,
    overdue_reminders,
    vehicle_report,
    payment_report,
    payment_report_add,
    customer_search_api,
    quick_add_customer,
    admin_reauth,
)
app_name = 'core'


urlpatterns = [
    path(
        'admin-reauth/',
        admin_reauth,
        name='admin_reauth',
    ),
    path(
        '',
        dashboard,
        name='dashboard',
    ),

    path(
        'reports/customers/',
        customer_report,
        name='customer_report',
    ),

    path(
        'reports/overdue/',
        overdue_reminders,
        name='overdue_reminders',
    ),

    path(
        'reports/vehicles/',
        vehicle_report,
        name='vehicle_report',
    ),

    path(
        'reports/payments/',
        payment_report,
        name='payment_report',
    ),

    path(
        'reports/payments/add/',
        payment_report_add,
        name='payment_report_add',
    ),

    path(
        'api/customer-search/',
        customer_search_api,
        name='customer_search_api',
    ),

    path(
        'customers/quick-add/',
        quick_add_customer,
        name='quick_add_customer',
    ),
]