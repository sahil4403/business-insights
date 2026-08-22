from django.urls import path

from .views import (
    trip_create,
    trip_delete,
    trip_edit,
    trip_list,
    trip_detail,
    trip_payment_create,
    trip_payment_edit,
    trip_payment_delete,
    trip_quickfill,
)
app_name = 'trips'

urlpatterns = [

    path(
        '',
        trip_list,
        name='list',
    ),

    path(
        'add/',
        trip_create,
        name='create',
    ),

    path(
        'create/',
        trip_create,
        name='create_alias',
    ),

    path(
        '<int:trip_id>/',
        trip_detail,
        name='detail',
    ),

    path(
        '<int:trip_id>/edit/',
        trip_edit,
        name='edit',
    ),

    path(
        '<int:trip_id>/delete/',
        trip_delete,
        name='delete',
    ),

    path(
        '<int:trip_id>/payment/add/',
        trip_payment_create,
        name='payment_create',
    ),

    path(
        'payment/<int:payment_id>/edit/',
        trip_payment_edit,
        name='payment_edit',
    ),

    path(
        'payment/<int:payment_id>/delete/',
        trip_payment_delete,
        name='payment_delete',
    ),

    path(
        'api/quickfill/',
        trip_quickfill,
        name='quickfill',
    ),

]
