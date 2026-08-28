from django.core.management.base import BaseCommand
from customers.models import Customer


class Command(BaseCommand):
    help = 'Re-arrange all customer codes alphabetically by name (CUST-001, CUST-002, ...)'

    def handle(self, *args, **options):
        customers = list(Customer.objects.filter(is_active=True).order_by('name'))
        total = len(customers)
        self.stdout.write(f"Found {total} active customers. Re-arranging codes...\n")

        # Step 1: Assign temp codes to avoid UNIQUE conflicts
        for i, customer in enumerate(customers, start=1):
            temp_code = f"TEMP-{i:05d}"
            Customer.objects.filter(pk=customer.pk).update(customer_code=temp_code)

        # Step 2: Assign real alphabetical codes
        count = 0
        for i, customer in enumerate(customers, start=1):
            new_code = f"CUST-{i:03d}"
            Customer.objects.filter(pk=customer.pk).update(customer_code=new_code)
            self.stdout.write(f"  {new_code}  ({customer.name})")
            count += 1

        self.stdout.write(self.style.SUCCESS(f"\nDone! {count} customers re-arranged alphabetically."))
