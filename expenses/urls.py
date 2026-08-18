from django.urls import path

from .views import (
    expense_dashboard,
    expense_create,
    expense_list,
    expense_edit,
    expense_delete,
)
app_name = 'expenses'


urlpatterns = [
    path(
        '',
        expense_dashboard,
        name='index',
    ),

    path(
        'dashboard/',
        expense_dashboard,
        name='dashboard',
    ),

    path(
        'add/',
        expense_create,
        name='create',
    ),

    path(
        'list/',
        expense_list,
        name='list',
    ),

    path(
        '<int:expense_id>/edit/',
        expense_edit,
        name='edit',
    ),

    path(
        '<int:expense_id>/delete/',
        expense_delete,
        name='delete',
    ),
]
