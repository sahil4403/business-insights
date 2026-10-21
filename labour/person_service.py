"""Person links: one real person across section-specific Labour records.

All shared-advance, shared-old-balance and combined-settlement logic lives
here. Views, forms, templates and PDF/Excel exports must use these helpers so
the same advance is never counted twice and never silently overwritten.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import (
    Labour,
    LabourAdvance,
    LabourDriverPayment,
    LabourExtraPayment,
    LabourOldBalance,
    LabourPerson,
    LabourRozi,
    LabourSettlement,
    LabourTripGroup,
)


# ---------------------------------------------------------------------------
# Person identity
# ---------------------------------------------------------------------------

def normalise_name(name):
    """Case + extra spaces ignore karke name compare karne ke liye."""
    return ' '.join((name or '').split()).casefold()


def person_members(labour):
    """All Labour records of this real person (self when unlinked)."""
    if not labour.person_id:
        return [labour]
    cached = getattr(labour, '_person_members_cache', None)
    if cached is not None:
        return cached
    members = list(Labour.objects.filter(person_id=labour.person_id).order_by('id'))
    labour._person_members_cache = members
    return members


def scope_ids(labour):
    return [m.pk for m in person_members(labour)]


def is_linked(labour):
    return len(scope_ids(labour)) > 1


def primary_labour(labour):
    """Lowest-id record of the group — shared old balance is stored here."""
    members = person_members(labour)
    return members[0] if members else labour


def role_label(labour):
    if labour.category == 'MISTRI':
        return 'Mistri Helper' if labour.sub_category == 'HELPER' else 'Mistri'
    return labour.get_category_display()


def also_in_labels(labour):
    """Role labels of the other section records of the same person."""
    if not labour.person_id:
        return []
    labels = []
    for member in Labour.objects.filter(person_id=labour.person_id).exclude(
        pk=labour.pk
    ).order_by('id'):
        label = role_label(member)
        if label not in labels:
            labels.append(label)
    return labels


def combined_label(labour):
    """e.g. 'Tractor + Mistri Helper' — detail cards ke label ke liye."""
    if not labour.person_id:
        return role_label(labour)
    labels = [role_label(member) for member in person_members(labour)]
    return ' + '.join(dict.fromkeys(labels))


def same_name_candidates(labour):
    """Same person suggest karne ke liye (auto-merge nahi — owner confirm kare)."""
    key = normalise_name(labour.name)
    if not key:
        return []
    candidates = []
    qs = (
        Labour.objects.filter(is_active=True)
        .exclude(is_vendor=True)
        .exclude(is_one_day=True)
        .exclude(pk=labour.pk)
        .order_by('name', 'id')
    )
    for other in qs:
        if normalise_name(other.name) != key:
            continue
        if labour.person_id and other.person_id == labour.person_id:
            continue
        candidates.append(other)
    return candidates


def unique_person_labours(labours):
    """One row per person (primary record) — book/summary double count rokne ke liye."""
    seen = set()
    out = []
    for labour in labours:
        if labour.person_id:
            if labour.person_id in seen:
                continue
            seen.add(labour.person_id)
            primary = Labour.objects.filter(person_id=labour.person_id).order_by('id').first()
            out.append(primary or labour)
        else:
            out.append(labour)
    return out


# ---------------------------------------------------------------------------
# Old balance (outstanding) — one shared figure per person
# ---------------------------------------------------------------------------

def ensure_old_balance(labour):
    primary = primary_labour(labour)
    ob, _ = LabourOldBalance.objects.get_or_create(
        labour=primary, defaults={'amount': Decimal('0')}
    )
    return ob


def old_balance_amount(labour):
    return ensure_old_balance(labour).amount


def old_balance_map(labours):
    """{labour_id: shared outstanding} for the given records."""
    labours = list(labours)
    amounts = {
        ob.labour_id: ob.amount for ob in LabourOldBalance.objects.all()
    }
    result = {}
    for labour in labours:
        primary = primary_labour(labour)
        result[labour.pk] = amounts.get(primary.pk, Decimal('0'))
    return result


def _merge_old_balance(source, target):
    """Move source record's outstanding into the person's primary record."""
    if source.pk == target.pk:
        return
    source_ob, _ = LabourOldBalance.objects.get_or_create(
        labour=source, defaults={'amount': Decimal('0')}
    )
    target_ob, _ = LabourOldBalance.objects.get_or_create(
        labour=target, defaults={'amount': Decimal('0')}
    )
    if source_ob.amount:
        target_ob.amount += source_ob.amount
        target_ob.save(update_fields=['amount'])
        source_ob.amount = Decimal('0')
        source_ob.save(update_fields=['amount'])


# ---------------------------------------------------------------------------
# Linking / unlinking
# ---------------------------------------------------------------------------

@transaction.atomic
def link_labours(labour, other):
    """Link two records as one person. Merges outstanding into the primary."""
    if labour.pk == other.pk:
        raise ValueError('Ek hi record ko link nahi kar sakte.')
    if labour.person_id and labour.person_id == other.person_id:
        return labour.person

    if labour.person_id:
        target = labour.person
    elif other.person_id:
        target = other.person
    else:
        target = LabourPerson.objects.create(
            name=(labour.name or other.name or '').strip()
        )

    # Dono records + unke purane groups target person me shift honge.
    move_ids = set()
    old_person_ids = set()
    for record in (labour, other):
        if record.person_id:
            if record.person_id != target.pk:
                old_person_ids.add(record.person_id)
                move_ids.update(
                    Labour.objects.filter(person_id=record.person_id)
                    .values_list('pk', flat=True)
                )
        else:
            move_ids.add(record.pk)

    Labour.objects.filter(pk__in=move_ids).update(person=target)
    # Caller ke in-memory objects bhi fresh rakho (warna service calls stale
    # person_id dekh sakti hain jab tak dobara DB se fetch na ho).
    labour.person = target
    other.person = target
    for record in (labour, other):
        if hasattr(record, '_person_members_cache'):
            del record._person_members_cache

    # Purane groups ab khaali hain.
    for old_id in old_person_ids:
        if old_id != target.pk and not Labour.objects.filter(person_id=old_id).exists():
            LabourPerson.objects.filter(pk=old_id).delete()

    members = list(Labour.objects.filter(person=target).order_by('id'))
    if not members:
        return target
    primary = members[0]
    for record in members[1:]:
        _merge_old_balance(record, primary)

    target.name = (primary.name or '').strip()
    target.save(update_fields=['name'])
    return target


@transaction.atomic
def unlink_labour(labour):
    """Detach this record. Shared outstanding remaining person ke paas rehta hai;
    nikalne wala record ₹0 se start karta hai. Settlements record ke saath rehti hain."""
    person = labour.person
    if person is None:
        return False

    members = list(Labour.objects.filter(person=person).order_by('id'))
    remaining = [m for m in members if m.pk != labour.pk]

    if not remaining:
        labour.person = None
        labour.save(update_fields=['person'])
        person.delete()
        return True

    was_primary = members[0].pk == labour.pk
    if was_primary:
        shared = ensure_old_balance(labour)
        if shared.amount:
            new_ob, _ = LabourOldBalance.objects.get_or_create(
                labour=remaining[0], defaults={'amount': Decimal('0')}
            )
            new_ob.amount += shared.amount
            new_ob.save(update_fields=['amount'])
        shared.amount = Decimal('0')
        shared.save(update_fields=['amount'])

    labour.person = None
    labour.save(update_fields=['person'])
    if hasattr(labour, '_person_members_cache'):
        del labour._person_members_cache

    own_ob, _ = LabourOldBalance.objects.get_or_create(
        labour=labour, defaults={'amount': Decimal('0')}
    )
    if own_ob.amount:
        own_ob.amount = Decimal('0')
        own_ob.save(update_fields=['amount'])

    remaining = list(Labour.objects.filter(person=person).order_by('id'))
    if len(remaining) <= 1:
        for record in remaining:
            record.person = None
            record.save(update_fields=['person'])
        person.delete()
    else:
        primary = remaining[0]
        person.name = (primary.name or '').strip()
        person.save(update_fields=['name'])
    return True


# ---------------------------------------------------------------------------
# Advances — combined pool, additive entry, never silent overwrite
# ---------------------------------------------------------------------------

def advance_qs(labour, start=None, end=None):
    qs = LabourAdvance.objects.filter(
        labour_id__in=scope_ids(labour)
    ).select_related('labour')
    if start is not None:
        qs = qs.filter(date__gte=start)
    if end is not None:
        qs = qs.filter(date__lte=end)
    return qs.order_by('-date', '-id')


def advance_total(labour, start=None, end=None):
    total = advance_qs(labour, start, end).aggregate(t=Sum('amount'))['t']
    return total or Decimal('0')


def advance_total_for_date(labour, day):
    return advance_total(labour, day, day)


def advance_rows_for_date(labour, day):
    return list(advance_qs(labour).filter(date=day).order_by('id'))


def add_advance(labour, day, amount, note=''):
    """Add an advance without overwriting another section's entry.

    - Same record + same date already has a row (DB unique constraint):
      amount usi row me ADD hota hai.
    - Warna nayi row banti hai (linked section ki row ko chhua nahi jata),
      aur combined total me dono rows jud jati hain.

    Returns (row, created, previous_amount).
    """
    amount = Decimal(str(amount))
    note = (note or '').strip()
    existing = LabourAdvance.objects.filter(labour=labour, date=day).first()
    if existing is not None:
        previous = existing.amount
        existing.amount = previous + amount
        if note:
            existing.note = f'{existing.note} · {note}' if existing.note else note
        existing.save(update_fields=['amount', 'note'])
        return existing, False, previous
    row = LabourAdvance.objects.create(
        labour=labour, date=day, amount=amount, note=note
    )
    return row, True, Decimal('0')


# ---------------------------------------------------------------------------
# Salary + advance totals (combined for linked person)
# ---------------------------------------------------------------------------

def salary_totals(labour, period_start, period_end):
    """Trip share + extra + rozi + driver payment across the whole person."""
    ids = scope_ids(labour)
    id_set = set(ids)

    trip_total = Decimal('0')
    groups = LabourTripGroup.objects.filter(
        date__gte=period_start, date__lte=period_end,
        labourers__id__in=ids,
    ).distinct().prefetch_related('labourers')
    for group in groups:
        members = list(group.labourers.all())
        if not any(m.pk in id_set for m in members):
            continue
        # Same person ke do records ek hi group me ho to share ek hi baar.
        persons = set()
        for member in members:
            key = ('p', member.person_id) if member.person_id else ('l', member.pk)
            persons.add(key)
        if persons:
            trip_total += group.total_amount / len(persons)

    extra_total = LabourExtraPayment.objects.filter(
        labour_id__in=ids, date__gte=period_start, date__lte=period_end
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    rozi_total = LabourRozi.objects.filter(
        labour_id__in=ids, date__gte=period_start, date__lte=period_end
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    driver_total = LabourDriverPayment.objects.filter(
        labour_id__in=ids,
        period_start__lte=period_end,
        period_end__gte=period_start,
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    advance_total_value = advance_total(labour, period_start, period_end)

    return {
        'trip_total': trip_total,
        'extra_total': extra_total,
        'rozi_total': rozi_total,
        'driver_total': driver_total,
        'total_salary': trip_total + extra_total + rozi_total + driver_total,
        'advance_total': advance_total_value,
    }


# ---------------------------------------------------------------------------
# Settlements — one combined chain per person
# ---------------------------------------------------------------------------

def settlements_qs(labour):
    return LabourSettlement.objects.filter(labour_id__in=scope_ids(labour))


def latest_settlement(labour):
    return settlements_qs(labour).order_by('-settlement_date', '-id').first()


def has_overlapping_settlement(labour, period_start, period_end):
    """Sirf NAYE settlement ke liye check — purani/legacy settlements block na hon."""
    return settlements_qs(labour).filter(
        period_start__lte=period_end,
        period_end__gte=period_start,
    ).exists()
