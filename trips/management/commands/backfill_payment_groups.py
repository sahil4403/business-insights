"""Backfill payment_group on legacy lumpsum payment rows.

Before the ``payment_group`` field existed, a single recorded customer lumpsum
payment was split (FIFO) into several TripPayment rows, one per trip it cleared,
plus an optional on-account leftover row. Those rows had no way to be tied back
together, so statements/reports had to *guess* which rows belonged to one payment
using fragile date/notes heuristics.

This command stamps a shared ``payment_group`` UUID onto each set of legacy rows
that originated from the same recorded payment, so they display and edit/delete
as ONE clean entry going forward.

Grouping key: (customer, payment_date, payment_method, reference_number).
The FIFO allocator wrote all rows of one payment with identical values for those
four fields, so this reliably reconstructs a payment. The per-trip rows and the
on-account leftover row carry *different* auto-notes, so notes is deliberately
NOT part of the key (otherwise the leftover would split off on its own).

LIMITATION (unavoidable for legacy data): if the same customer had two separate
lumpsum payments on the same day, same method, and same/blank reference, the
original per-payment boundary is lost and they will merge into one group. Use
--dry-run to review before committing, and pass an explicit --reference-required
if you want to skip blank-reference rows.

Usage on PythonAnywhere (bash console, inside the project venv):
    python manage.py backfill_payment_groups --dry-run     # preview, no writes
    python manage.py backfill_payment_groups               # apply
"""

import uuid
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from trips.models import TripPayment

# Notes historically written by the auto-allocation path. Kept in sync with
# ledger/views.py LEGACY_LUMPSUM_NOTES.
LUMPSUM_NOTE = 'Customer lumpsum / on-account payment'
LUMPSUM_OPENING_NOTE = 'Customer lumpsum / opening balance payment'
LEGACY_LUMPSUM_NOTES = (LUMPSUM_NOTE, LUMPSUM_OPENING_NOTE)


class Command(BaseCommand):
    help = (
        "Assign a shared payment_group to legacy auto-allocated lumpsum payment "
        "rows so each original payment shows as ONE entry. Run --dry-run first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Show what would change without writing to the database.",
        )
        parser.add_argument(
            '--include-singletons',
            action='store_true',
            help=(
                "Also stamp single-row legacy payments (default: only rows that "
                "were actually split into 2+ rows). Singletons already display "
                "as one line; tagging them just routes edit/delete through the "
                "group handler for consistency."
            ),
        )
        parser.add_argument(
            '--reference-required',
            action='store_true',
            help=(
                "Skip rows with a blank reference_number. Safer when you fear "
                "same-day/same-method payments getting merged, at the cost of "
                "leaving reference-less legacy payments un-grouped."
            ),
        )

    def _customer_id(self, row):
        """Owning customer id for a payment row (trip-linked or on-account)."""
        if row.customer_id:
            return row.customer_id
        if row.trip_id and row.trip and row.trip.customer_id:
            return row.trip.customer_id
        return None

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        include_singletons = options['include_singletons']
        reference_required = options['reference_required']

        # Only untouched legacy auto-allocated rows (no group id yet).
        no_group = Q(payment_group__isnull=True) | Q(payment_group='')
        qs = (
            TripPayment.objects
            .filter(no_group)
            .filter(notes__in=LEGACY_LUMPSUM_NOTES)
            .select_related('trip')
            .order_by('payment_date', 'id')
        )

        buckets = defaultdict(list)
        skipped_no_customer = 0
        skipped_no_reference = 0

        for row in qs:
            cid = self._customer_id(row)
            if cid is None:
                skipped_no_customer += 1
                continue

            reference = (row.reference_number or '').strip()
            if reference_required and not reference:
                skipped_no_reference += 1
                continue

            key = (cid, row.payment_date, row.payment_method_id, reference)
            buckets[key].append(row)

        # Decide which buckets to stamp.
        target_buckets = []
        singletons_left = 0
        for key, rows in buckets.items():
            if len(rows) >= 2 or include_singletons:
                target_buckets.append((key, rows))
            else:
                singletons_left += 1

        total_rows = sum(len(rows) for _, rows in target_buckets)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Backfill payment_group — plan"))
        self.stdout.write(
            f"  Legacy lumpsum rows scanned : {qs.count()}"
        )
        self.stdout.write(
            f"  Payments to tag (groups)    : {len(target_buckets)}"
        )
        self.stdout.write(
            f"  Rows to tag                 : {total_rows}"
        )
        if singletons_left:
            self.stdout.write(
                f"  Single-row payments skipped : {singletons_left} "
                f"(pass --include-singletons to tag)"
            )
        if skipped_no_customer:
            self.stdout.write(
                self.style.WARNING(
                    f"  Rows with no customer skip. : {skipped_no_customer}"
                )
            )
        if skipped_no_reference:
            self.stdout.write(
                f"  Blank-reference rows skipped: {skipped_no_reference}"
            )
        self.stdout.write("")

        if not target_buckets:
            self.stdout.write(self.style.SUCCESS("Nothing to backfill. Done."))
            return

        # Show a short sample so the operator can sanity-check the grouping.
        sample = sorted(target_buckets, key=lambda kr: -len(kr[1]))[:8]
        self.stdout.write("Sample of groups that will be created:")
        for (cid, pdate, method_id, reference), rows in sample:
            total = sum((r.amount for r in rows), 0)
            self.stdout.write(
                f"  • customer#{cid}  {pdate}  method#{method_id or '-'}  "
                f"ref={reference or '(none)'}  -> {len(rows)} rows  ₹{total}"
            )
        self.stdout.write("")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN — no changes written. Re-run without --dry-run "
                    "to apply."
                )
            )
            return

        groups_written = 0
        rows_written = 0
        with transaction.atomic():
            for key, rows in target_buckets:
                group_id = uuid.uuid4().hex
                ids = [r.id for r in rows]
                TripPayment.objects.filter(id__in=ids).update(
                    payment_group=group_id
                )
                groups_written += 1
                rows_written += len(ids)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Tagged {rows_written} rows into {groups_written} "
                f"payment groups."
            )
        )
