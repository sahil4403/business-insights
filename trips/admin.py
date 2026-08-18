from django.contrib import admin
from .models import Trip, TripPayment
from .forms import TripAdminForm


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):

    form = TripAdminForm

    list_display = (
        'trip_code',
        'trip_date',
        'customer',
        'vehicle',
        'material',
        'quantity',
        'rate',
        'total_amount',
        'trip_status',
        'display_payment_status',
        'total_received',
        'outstanding_amount',
    )

    readonly_fields = (
        'total_amount',
    )

    list_filter = (
        'trip_status',
        'payment_status',
        'trip_date',
        'material',
    )

    search_fields = (
        'trip_code',
        'customer__name',
        'customer__customer_code',
        'vehicle__registration_number',
        'vehicle__vehicle_code',
        'drivers__name',
    )

    ordering = (
        '-trip_date',
        '-id',
    )


    @admin.display(description='Payment Status')
    def display_payment_status(self, obj):
        return obj.calculated_payment_status

    @admin.display(description='Drivers')
    def display_drivers(self, obj):
        return ", ".join(
            driver.name for driver in obj.drivers.all()
        )

@admin.register(TripPayment)
class TripPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'trip',
        'payment_date',
        'amount',
        'payment_method',
        'reference_number',
        'created_at',

    )

    list_filter = (
        'payment_method',
        'payment_date',
    )

    search_fields = (
        'trip__trip_code',
        'trip__customer__name',
        'reference_number',
    )

    ordering = (
        '-payment_date',
        '-id',
    )