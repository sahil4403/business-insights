from django.urls import path

from . import views

app_name = 'labour'

urlpatterns = [
    path('', views.labour_list, name='list'),
    path('category/<str:category_code>/', views.labour_category_detail, name='category_detail'),
    path('add/', views.labour_create, name='create'),
    path('<int:labour_id>/edit/', views.labour_edit, name='edit'),
    path('<int:labour_id>/', views.labour_detail, name='detail'),
    path('<int:labour_id>/remove/', views.labour_deactivate, name='remove'),
    path('<int:labour_id>/outstanding/set/', views.labour_set_outstanding, name='outstanding_set'),

    path('trips/add/', views.trip_group_create, name='trip_add'),
    path('hyva/trips/add/', views.hyva_trip_create, name='hyva_trip_add'),
    path('hyva/trips/edit/<int:group_id>/', views.hyva_trip_edit, name='hyva_trip_edit'),
    path('trips/', views.trip_group_list, name='trips'),
    path('trips/edit/<int:group_id>/', views.trip_group_edit, name='trip_edit'),
    path('trips/delete/<int:group_id>/', views.trip_group_delete, name='trip_delete'),
    path('extras/add/', views.extra_create, name='extra_add'),
    path('extras/add/<int:labour_id>/', views.extra_create, name='extra_add_for'),
    path('extras/delete/<int:extra_id>/', views.extra_delete, name='extra_delete'),
    path('extras/edit/<int:extra_id>/', views.extra_edit, name='extra_edit'),

    # Advances
    path('advances/add/', views.advance_create, name='advance_add'),
    path('advances/add/<int:labour_id>/', views.advance_create, name='advance_add_for'),
    path('advances/delete/<int:advance_id>/', views.advance_delete, name='advance_delete'),
    path('advances/edit/<int:advance_id>/', views.advance_edit, name='advance_edit'),
    path('rozi/add/', views.rozi_create, name='rozi_add'),
    path('rozi/add/<int:labour_id>/', views.rozi_create, name='rozi_add_for'),
    path('rozi/delete/<int:rozi_id>/', views.rozi_delete, name='rozi_delete'),
    path('rozi/edit/<int:rozi_id>/', views.rozi_edit, name='rozi_edit'),
    path('rozi/quick/', views.rozi_multi, name='rozi_multi'),
    path('advances/quick/', views.advance_multi, name='advance_multi'),
    path('driver-payment/add/', views.driver_payment_create, name='driver_add'),
    path('driver-payment/add/<int:labour_id>/', views.driver_payment_create, name='driver_add_for'),
    path('<int:labour_id>/settle/', views.settlement_create, name='settle'),
    path('settlements/<int:settlement_id>/edit/', views.settlement_edit, name='settlement_edit'),
    path('settlements/<int:settlement_id>/revert/', views.settlement_revert, name='settlement_revert'),
    path('<int:labour_id>/statement/', views.labour_statement_export, name='statement_export'),
    path('book/', views.labour_book, name='book'),
    path('summary/', views.labour_summary, name='summary'),
    path('daily-activity/', views.daily_activity, name='daily_activity'),
]
