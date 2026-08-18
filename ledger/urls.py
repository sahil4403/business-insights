from django.urls import path

from . import views

app_name = 'ledger'

urlpatterns = [
    path(
        'customer/<int:customer_id>/',
        views.customer_statement,
        name='customer_statement'
    ),

    path(
        'customer/<int:customer_id>/pdf/',
        views.customer_statement_pdf,
        name='customer_statement_pdf'
    ),

    path(
        'customer/<int:customer_id>/record-payment/',
        views.customer_record_payment,
        name='customer_record_payment'
    ),

    path(
        'customer/<int:customer_id>/update-opening-balance/',
        views.update_customer_opening_balance,
        name='update_customer_opening_balance'
    ),
]