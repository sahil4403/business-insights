from django.contrib import admin
from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle_code',
        'registration_number',
        'vehicle_type',
        'capacity_cft',
        'ownership_type',
        'status',
        'is_active',
        'created_at',
    )

    list_filter = (
        'vehicle_type',
        'ownership_type',
        'status',
        'is_active',
    )

    search_fields = (
        'vehicle_code',
        'registration_number',
        'owner_name',
    )

    ordering = (
        'registration_number',
    )