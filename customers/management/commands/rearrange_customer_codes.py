from django.core.management.base import BaseCommand
from customers.models import Customer


class Command(BaseCommand):
    help = 'Re-arrange all customer codes alphabetically by name (CUST-001, CUST-002, ...)'

    def handle(self, *args, **options):
        customers = Customer.objects.filter(is_active=True).order_by('name')

        self.stdout.write(f"Found {customers.count()} active customers. Re-arranging codes...\n")

        for i, customer in enumerate(customers, start=1):
            new_code = f"CUST-{i:03d}"
            if customer.customer_code != new_code:
                old_code = customer.customer_code
                customer.customer_code = new_code
                customer.save(update_fields=['customer_code'])
                self.stdout.write(f"  {old_code} → {new_code}  ({customer.name})")
            else:
                self.stdout.write(f"  {new_code}  ({customer.name}) [already correct]")

        self.stdout.write(self.style.SUCCESS(f"\nDone! {customers.count()} customers re-arranged alphabetically."))
