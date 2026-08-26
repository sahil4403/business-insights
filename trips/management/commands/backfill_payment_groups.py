"""Backfill payment_group on legacy lumpsum payment rows.

Before the ``payment_group`` field existed, a single recorded customer lumpsum
payment was split (FIFO) into several TripPayment rows, one per trip it cleared,
plus an optional on-account leftover row. Those rows had no way to be tied back
together, so statements/reports had to *guess* which rows belonged to one payment
using fragile date/notes heuristics.

This command stamps a shared ``payment_group`` UUID onto each set of legacy rows
that originated from the same recorded payment, so they display and edit/delete
as ONE clean entry going forward.

Grouping key: (customer, payment_date, payment_method, reference_number, note).
The FIFO allocator wrote all rows of one payment with identical values for those
fields, so this reliably reconstructs a payment. The `note` part is normalised:
the two default auto-notes (per-trip vs on-account leftover) collapse to a single
sentinel so a payment's leftover row stays with its trip rows, while a *custom*
note the user typed (e.g. a project name like "Vidarbha Homes") is kept as-is so
it identifies its own payment. Rows with a blank note are treated as individual
manual payments and are never auto-grouped.

Why note is in the key: real legacy data (e.g. customer "Raj Sir") recorded two
same-day, same-method, blank-reference lumpsum payments distinguished ONLY by a
custom project note. Without note in the key they would wrongly merge into one
line; with it they correctly stay as two payments.

LIMITATION (unavoidable for legacy data): if the same customer had two separate
lumpsum payments on the same day, same method, same/blank reference AND the same
(or both-default) note, the original per-payment boundary is lost and they will
merge into one group. Use --dry-run to review before committing, and pass an
explicit --reference-required if you want to skip blank-reference rows.

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

    # Sentinel used to collapse the two default auto-notes into one bucket so a
    # payment's per-trip rows and its on-account leftover row group together.
    LUMPSUM_SENTINEL = '\x00__lumpsum__'

    def _note_key(self, notes):
        """Normalise a row's note into a grouping token.

        Returns:
          * ``LUMPSUM_SENTINEL`` for the default auto-notes (per-trip / leftover)
          * the trimmed custom note for anything else non-blank
          * ``''`` (falsy) for a blank note -> caller must NOT group these
        """
        note = (notes or '').strip()
        if note in LEGACY_LUMPSUM_NOTES:
            return self.LUMPSUM_SENTINEL
        return note

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        include_singletons = options['include_singletons']
        reference_required = options['reference_required']

        # Only untouched rows (no group id yet). We no longer restrict to the
        # default lumpsum notes — legacy auto-split rows may carry a custom note
        # (a project name). Auto-split candidates are identified structurally:
        # rows that share (customer, date, method, reference, note) in a bucket
        # of 2+. Blank-note rows are excluded below as manual single payments.
        no_group = Q(payment_group__isnull=True) | Q(payment_group='')
        qs = (
            TripPayment.objects
            .filter(no_group)
            .select_related('trip')
            .order_by('payment_date', 'id')
        )

        buckets = defaultdict(list)
        skipped_no_customer = 0
        skipped_no_reference = 0
        skipped_blank_note = 0

        for row in qs:
            cid = self._customer_id(row)
            if cid is None:
                skipped_no_customer += 1
                continue

            note_key = self._note_key(row.notes)
            if not note_key:
                # Blank-note rows are individual manual payments, never grouped.
                skipped_blank_note += 1
                continue

            reference = (row.reference_number or '').strip()
            if reference_required and not reference:
                skipped_no_reference += 1
                continue

            key = (cid, row.payment_date, row.payment_method_id, reference, note_key)
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
            f"  Un-grouped rows scanned     : {qs.count()}"
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
        if skipped_blank_note:
            self.stdout.write(
                f"  Blank-note rows skipped     : {skipped_blank_note} "
                f"(treated as individual manual payments)"
            )
        self.stdout.write("")

        if not target_buckets:
            self.stdout.write(self.style.SUCCESS("Nothing to backfill. Done."))
            return

        # Show a short sample so the operator can sanity-check the grouping.
        sample = sorted(target_buckets, key=lambda kr: -len(kr[1]))[:8]
        self.stdout.write("Sample of groups that will be created:")
        for (cid, pdate, method_id, reference, note_key), rows in sample:
            total = sum((r.amount for r in rows), 0)
            note_label = (
                '(lumpsum)' if note_key == self.LUMPSUM_SENTINEL else note_key
            )
            self.stdout.write(
                f"  • customer#{cid}  {pdate}  method#{method_id or '-'}  "
                f"ref={reference or '(none)'}  note={note_label!r}  "
                f"-> {len(rows)} rows  ₹{total}"
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
