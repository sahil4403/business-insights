from django.core.management.base import BaseCommand
from django.db import transaction

from labour.models import Labour


LABOUR_NAMES = [
    "Dhanraj",
    "Krishna",
    "Mangesh",
    "Pravin Sapate",
    "Rishab Driver",
    "Santosh",
    "Saurabh",
    "Shiva Driver",
    "Shubham",
]


class Command(BaseCommand):

    help = "Import missing February-December historical labour records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the labour import without changing the database.",
        )

    def handle(self, *args, **options):

        dry_run = options["dry_run"]

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("FEBRUARY - DECEMBER LABOUR IMPORT")
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN - NO DATABASE CHANGES WILL BE MADE"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "LIVE IMPORT - DATABASE WILL BE CHANGED"
                )
            )

        existing = {
            labour.name.strip().lower(): labour
            for labour in Labour.objects.all()
        }

        new_names = []

        for name in LABOUR_NAMES:

            key = name.strip().lower()

            if key in existing:
                self.stdout.write(
                    f"SKIP - Already exists: {name}"
                )
            else:
                new_names.append(name)

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("LABOUR IMPORT SUMMARY")
        self.stdout.write("=" * 70)

        self.stdout.write(
            f"Labour currently in DB : {len(existing)}"
        )

        self.stdout.write(
            f"New labour to create    : {len(new_names)}"
        )

        self.stdout.write("")
        self.stdout.write("NEW LABOUR")
        self.stdout.write("-" * 70)

        for name in new_names:
            self.stdout.write(name)

        if dry_run:

            self.stdout.write("")
            self.stdout.write("=" * 70)
            self.stdout.write(
                f"DRY RUN PASSED - {len(new_names)} labour "
                "records would be created."
            )
            self.stdout.write(
                "NO DATABASE CHANGES WERE MADE."
            )
            self.stdout.write("=" * 70)

            return

        # ---------------------------------------------------------
        # LIVE IMPORT
        # ---------------------------------------------------------

        created = []

        with transaction.atomic():

            for name in new_names:

                labour = Labour.objects.create(
                    name=name,
                    status="ACTIVE",
                    is_active=True,
                )

                created.append(labour)

        # ---------------------------------------------------------
        # POST-IMPORT VERIFICATION
        # ---------------------------------------------------------

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("LABOUR IMPORT COMPLETE")
        self.stdout.write("=" * 70)

        self.stdout.write(
            f"Labour created : {len(created)}"
        )

        verification_errors = []

        for name in new_names:

            exists = Labour.objects.filter(
                name__iexact=name
            ).exists()

            if not exists:
                verification_errors.append(name)

        if verification_errors:

            self.stdout.write(
                self.style.ERROR(
                    "LABOUR POST-IMPORT VERIFICATION FAILED."
                )
            )

            for name in verification_errors:
                self.stdout.write(
                    f"- {name}"
                )

            raise RuntimeError(
                "Some labour records could not be verified."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "LABOUR POST-IMPORT VERIFICATION PASSED."
            )
        )