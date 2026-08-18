from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.db.models import Q


def populate_default_master_data(sender, **kwargs):
    from master_data.models import PaymentMethod, VehicleType, Material
    from vehicles.models import Vehicle

    Material.objects.get_or_create(
        name='JCB Work',
        defaults={'unit': 'TRIP', 'description': 'JCB Excavator & Earthmover Work', 'is_active': True}
    )

    methods = [
        ('UPI', 'UPI', 'UPI Digital Payment'),
        ('CASH', 'Cash', 'Cash Payment'),
        ('BANK_TRANSFER', 'Bank Transfer', 'NEFT / RTGS / IMPS Bank Transfer'),
        ('CHEQUE', 'Cheque', 'Cheque Payment'),
    ]
    for code, name, desc in methods:
        PaymentMethod.objects.get_or_create(
            code=code,
            defaults={'name': name, 'description': desc, 'is_active': True}
        )

    v_types = [
        ('HYVA', 'Hyva', 'Hyva Dumper Truck'),
        ('TRACTOR', 'Tractor', 'Tractor Trolley'),
        ('HALFTON', 'Halfton', 'Half Ton Light Truck'),
        ('JCB', 'JCB', 'JCB Excavator / Earthmover'),
    ]
    for code, name, desc in v_types:
        vt, _ = VehicleType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'description': desc, 'is_active': True}
        )
        if not Vehicle.objects.filter(Q(vehicle_code=f'VEH-{code}') | Q(registration_number=name)).exists():
            Vehicle.objects.create(
                vehicle_code=f'VEH-{code}',
                vehicle_type=vt,
                registration_number=name,
                ownership_type='OWNED',
                is_active=True
            )


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        post_migrate.connect(populate_default_master_data, sender=self)

