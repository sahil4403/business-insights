from django.core.management.base import BaseCommand

from master_data.models import ExpenseCategory


class Command(BaseCommand):
    help = "Create default expense categories"

    categories = [
        ("DIESEL", "Diesel / Fuel"),
        ("BLACK_DIESEL", "Black Diesel"),
        ("VEHICLE_REPAIR", "Vehicle Repair"),
        ("VEHICLE_MAINTENANCE", "Vehicle Maintenance"),
        ("LABOUR", "Labour"),
        ("LOADING_UNLOADING", "Loading / Unloading"),
        ("OFFICE", "Office"),
        ("RENT", "Rent"),
        ("ELECTRICITY", "Electricity"),
        ("TRANSPORT", "Transport"),
        ("MISCELLANEOUS", "Miscellaneous"),
        ("OTHER", "Other"),
    ]

    def handle(self, *args, **options):

        created_count = 0
        existing_count = 0

        for code, name in self.categories:

            category, created = ExpenseCategory.objects.get_or_create(
                name=name,
                defaults={
                    "code": code,
                    "is_active": True,
                }
            )

            if created:
                created_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created: {name}"
                    )
                )

            else:
                existing_count += 1

                self.stdout.write(
                    f"Already exists: {name}"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created_count}, "
                f"Already existed: {existing_count}"
            )
        )