from django.core.management.base import BaseCommand
from customers.models import Customer
from master_data.models import CustomerType
import re


MISSING = [
    "Aakash", "Aaro Water Filter", "Ajju Balki", "Amar Avde", "Anil Narule",
    "Ankush Bhau", "Aszar", "Baburao Weilding", "Bhai Miya", "Chaada Transport",
    "Chaure Welder", "Chhabu Sahare ( Raj Dad )", "Deshkar ( Raj Dad )",
    "Dewagan", "Dodlani", "Dump", "Durge", "Ganesh Surje", "Gedam Raj",
    "Golu Operator", "hiwakar", "HP Gas ( Mahendra )", "Jadish Yadav",
    "JI Sav ( Roshan )", "Joyti Bai", "Kade", "Kamlesh Chidate ( Raj Dad )",
    "Khare Uncle ( Raj Dad )", "Kishor Buratkar", "Kunal ( Roshan Order",
    "Langda ( Mahendra )", "Mahendra  CCTV", "Mohan Lonbole", "Morey Cycle",
    "Navel Bhaiya", "Near Yenurkar House", "Nishu Bhaiya", "Noor Garage ( Mahendra )",
    "Omdas", "Papa Order", "Pari Doctor", "Pawar", "Police Station", "Prasahant",
    "Preet Friend", "Puncture Wala", "Rahish ( Mahendra )", "Railway Bridge",
    "Rakesh", "Rakesh Aagat ( Raj )", "Rasses Order", "Raut", "Roshan",
    "Roshan Raj Dad", "RTO", "RVF Railway", "Sahil Derkar", "Sainaith Jungure",
    "Sandeep Borkhute", "Sanju", "Sanju Ghate", "Santosh", "Santosh Bhaiya Order",
    "Santosh Order", "Sarda Angency ( Raj Dad )", "Sham Builder", "Shende",
    "Shera Bhaiya", "Shiv Mandir", "Sonware", "Stock -  Ramp", "Sukhdev",
    "Tukum", "Turankar ( Raj )", "Tyre Wala", "Ujjawala Marketing",
    "Unknown ( Raj )", "vaman Shende", "Yergude", "Ankush Topase",
    "Anuraj  ( Golu )", "Fateing ( Mamaji )", "Gorkar", "Lalita", "Manthan",
    "Maroti Gotkar", "Naresh Kaka. Order", "Pani Puri Wala", "Raj Patil",
    "Sangham Palliwar", "Sardarji", "Shukla", "Surendra magar", "Vishal",
    "Raj Kamdi Stock", "Manoj",
]

SKIP = {
    "ji sav ( roshan )",
    "lalita",
    "kade",
    "naresh kaka. order",
    "kunal ( roshan order",
    "rakesh",
    "vishal",
}


def core(name):
    return re.sub(r"\s*\(.*?\)\s*$", "", name).strip().lower()


class Command(BaseCommand):
    help = "Add missing customers and re-number all customer codes by name (A-Z)."

    def handle(self, *args, **options):
        existing = {c.name.strip().lower(): c for c in Customer.objects.all()}
        existing_core = {}
        for name, cust in existing.items():
            existing_core.setdefault(core(name), cust)

        customer_type = CustomerType.objects.filter(code="CUSTOMER").first()
        if not customer_type:
            customer_type = CustomerType.objects.first()
        if not customer_type:
            customer_type = CustomerType.objects.create(code="CUSTOMER", name="Customer")

        added, skipped = [], []
        for name in MISSING:
            if name.strip().lower() in SKIP:
                skipped.append(name)
                continue
            key = name.strip().lower()
            if key in existing or core(key) in existing_core:
                continue
            cust = Customer.objects.create(
                customer_code="TMP-" + str(len(added) + 1).zfill(3),
                name=name.strip(),
                customer_type=customer_type,
                is_active=True,
            )
            added.append(cust.name)
            existing_core.setdefault(core(key), cust)

        self.stdout.write(f"Added: {len(added)} new customers")
        for n in added:
            self.stdout.write("  + " + n)
        self.stdout.write(f"Skipped (user asked): {len(skipped)}")

        removed = []
        for cust in Customer.objects.all():
            if cust.name.strip().lower() in SKIP:
                removed.append(cust.name)
                cust.delete()
        self.stdout.write(f"Removed (skip list): {removed}")

        customers = list(Customer.objects.all().order_by("name"))
        customers.sort(key=lambda c: c.name.strip().lower())
        for i, cust in enumerate(customers, start=1):
            cust.customer_code = f"TMP-{i:04d}"
            cust.save(update_fields=["customer_code"])
        for i, cust in enumerate(customers, start=1):
            cust.customer_code = f"CUST-{i:03d}"
            cust.save(update_fields=["customer_code"])
        self.stdout.write(self.style.SUCCESS(
            f"Done. Total customers: {len(customers)}. Codes CUST-001..CUST-{len(customers):03d} in name order."
        ))