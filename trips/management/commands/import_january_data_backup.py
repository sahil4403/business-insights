from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Import January historical trips and payments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate import without changing the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: No database changes will be made."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Import logic is not added yet."
                )
            )
