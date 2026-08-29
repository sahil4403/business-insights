from django.urls import path

from . import views

app_name = 'labour'

urlpatterns = [
    path('', views.labour_list, name='list'),
    path('add/', views.labour_create, name='create'),
    path('<int:labour_id>/', views.labour_detail, name='detail'),
    path('<int:labour_id>/remove/', views.labour_deactivate, name='remove'),
    path('<int:labour_id>/outstanding/set/', views.labour_set_outstanding, name='outstanding_set'),

    path('trips/add/', views.trip_group_create, name='trip_add'),
    path('trips/', views.trip_group_list, name='trips'),
    path('trips/edit/<int:group_id>/', views.trip_group_edit, name='trip_edit'),
    path('trips/delete/<int:group_id>/', views.trip_group_delete, name='trip_delete'),
    path('extras/add/', views.extra_create, name='extra_add'),
    path('extras/add/<int:labour_id>/', views.extra_create, name='extra_add_for'),
    path('advances/add/', views.advance_create, name='advance_add'),
    path('advances/add/<int:labour_id>/', views.advance_create, name='advance_add_for'),
    path('advances/quick/', views.advance_multi, name='advance_multi'),
    path('driver-payment/add/', views.driver_payment_create, name='driver_add'),
    path('driver-payment/add/<int:labour_id>/', views.driver_payment_create, name='driver_add_for'),
    path('<int:labour_id>/settle/', views.settlement_create, name='settle'),
    path('settlements/<int:settlement_id>/edit/', views.settlement_edit, name='settlement_edit'),
    path('settlements/<int:settlement_id>/revert/', views.settlement_revert, name='settlement_revert'),
    path('<int:labour_id>/statement/', views.labour_statement_export, name='statement_export'),
    path('book/', views.labour_book, name='book'),
]
