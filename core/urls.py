from django.urls import path

from .views import (
    dashboard,
    customer_report,
    vehicle_report,
    payment_report,
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
        'customers/quick-add/',
        quick_add_customer,
        name='quick_add_customer',
    ),
]