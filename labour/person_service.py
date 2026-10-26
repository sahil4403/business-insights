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
    LabourMinimumEarning,
    LabourOldBalance,
    LabourPerson,
    LabourRozi,
    LabourSettlement,
    LabourTripGroup,
)

MINIMUM_RULE_CATEGORIES = ('HYVA_DRIVER', 'JCB_OPERATOR')
DEFAULT_MINIMUM_TRIP_EARNING = Decimal('200')


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

def minimum_amounts():
    """Current per-role minimum trip earning thresholds."""
    return {
        row.category: row.amount
        for row in LabourMinimumEarning.objects.all()
    }


def _person_key(member, combined):
    """Same linked person ke records ko ek key me dedupe karo (combined only)."""
    if combined and member.person_id:
        return ('p', member.person_id)
    return ('l', member.pk)


def day_earnings(members, period_start, period_end, combined=True,
                 minimum_amounts_map=None):
    """Per-day trip, Bhatta, extra, Rozi and minimum-rule breakdown.

    The minimum rule is evaluated per person + role + date, so a linked
    person's same-role records do not get the threshold twice. Cross-role
    records keep their own role threshold. `combined=False` is for the
    section-specific detail rows and preserves the raw member-count split.

    Returned dict keys are dates; each value has raw and payable amounts plus
    `extra_amount` (all extras + Rozi) for existing day-row templates.
    """
    members = list(members)
    if not members:
        return {}

    ids = [m.pk for m in members]
    id_set = set(ids)
    if minimum_amounts_map is not None:
        minimums = minimum_amounts_map
    elif any(m.category in MINIMUM_RULE_CATEGORIES for m in members):
        minimums = minimum_amounts()
    else:
        minimums = {}
    zero = Decimal('0')

    trip_by_group = {}
    trip_items = []
    bhatta_by_group = {}
    bhatta_present = set()
    other_extra_by_date = {}
    rozi_by_date = {}

    def _add(bucket, key, value):
        bucket[key] = bucket.get(key, zero) + value

    groups = LabourTripGroup.objects.filter(
        date__gte=period_start, date__lte=period_end,
        labourers__id__in=ids,
    ).distinct().prefetch_related('labourers')
    for group in groups:
        group_members = list(group.labourers.all())
        in_scope = [m for m in group_members if m.pk in id_set]
        if not in_scope:
            continue

        if combined:
            # Denominator = unique real persons in the group, same as the
            # existing combined salary total. Add this person's share once.
            persons = {_person_key(m, True) for m in group_members}
            n = len(persons)
            if not n:
                continue
            seen = set()
            for member in in_scope:
                key = _person_key(member, True)
                if key in seen:
                    continue
                seen.add(key)
                group_key = (key, member.category, group.date)
                _add(
                    trip_by_group,
                    group_key,
                    group.total_amount / n,
                )
                trip_items.append({
                    'group_key': group_key,
                    'group_id': group.pk,
                    'date': group.date,
                    'category': member.category,
                    'label': group.load_label or 'Trip',
                    'trip_count': group.trip_count,
                    'amount': group.total_amount / n,
                })
        else:
            n = len(group_members)
            if n:
                member = in_scope[0]
                group_key = (('l', member.pk), member.category, group.date)
                _add(
                    trip_by_group,
                    group_key,
                    group.total_amount / n,
                )
                trip_items.append({
                    'group_key': group_key,
                    'group_id': group.pk,
                    'date': group.date,
                    'category': member.category,
                    'label': group.load_label or 'Trip',
                    'trip_count': group.trip_count,
                    'amount': group.total_amount / n,
                })

    for extra in LabourExtraPayment.objects.filter(
        labour_id__in=ids,
        date__gte=period_start,
        date__lte=period_end,
    ).select_related('labour'):
        member = extra.labour
        key = _person_key(member, combined)
        group_key = (key, member.category, extra.date)
        if extra.note == 'Bhatta':
            _add(bhatta_by_group, group_key, extra.amount)
            bhatta_present.add(group_key)
        else:
            _add(other_extra_by_date, extra.date, extra.amount)

    for rozi in LabourRozi.objects.filter(
        labour_id__in=ids,
        date__gte=period_start,
        date__lte=period_end,
    ):
        _add(rozi_by_date, rozi.date, rozi.amount)

    days = {}

    def _day(day):
        if day not in days:
            days[day] = {
                'date': day,
                'trip_total': zero,
                'trip_payable': zero,
                'bhatta_total': zero,
                'other_extra_total': zero,
                'rozi_total': zero,
                'extra_amount': zero,
                'minimum_adjustment': zero,
                'payable_amount': zero,
                'below_minimum': False,
                'trip_items': [],
                'minimum_thresholds': [],
            }
        return days[day]

    for (key, category, day), amount in trip_by_group.items():
        bucket = _day(day)
        bucket['trip_total'] += amount
        threshold = minimums.get(
            category,
            DEFAULT_MINIMUM_TRIP_EARNING,
        )
        has_bhatta = (key, category, day) in bhatta_present
        if (
            category in MINIMUM_RULE_CATEGORIES
            and has_bhatta
            and amount < threshold
        ):
            bucket['minimum_adjustment'] += amount
            bucket['below_minimum'] = True
        else:
            bucket['trip_payable'] += amount

    for item in trip_items:
        key, category, day = item['group_key']
        amount = trip_by_group[item['group_key']]
        threshold = minimums.get(
            category,
            DEFAULT_MINIMUM_TRIP_EARNING,
        )
        has_bhatta = (key, category, day) in bhatta_present
        item['minimum_amount'] = threshold
        item['below_minimum'] = (
            category in MINIMUM_RULE_CATEGORIES
            and has_bhatta
            and amount < threshold
        )
        bucket = _day(day)
        bucket['trip_items'].append(item)
        if item['below_minimum'] and threshold not in bucket['minimum_thresholds']:
            bucket['minimum_thresholds'].append(threshold)

    for (key, category, day), amount in bhatta_by_group.items():
        bucket = _day(day)
        bucket['bhatta_total'] += amount

    for day, amount in other_extra_by_date.items():
        bucket = _day(day)
        bucket['other_extra_total'] += amount
        bucket['extra_amount'] += amount

    for day, amount in rozi_by_date.items():
        bucket = _day(day)
        bucket['rozi_total'] += amount
        bucket['extra_amount'] += amount

    for bucket in days.values():
        bucket['extra_amount'] += bucket['bhatta_total']
        # trip_total - adjustment, kept explicit even if adjustment is zero.
        bucket['payable_amount'] = (
            bucket['trip_payable'] + bucket['extra_amount']
        )

    return days


def salary_totals(labour, period_start, period_end):
    """Trip share + extra + rozi + driver payment across the whole person.

    `trip_total` is always the raw trip figure (so the ledger can still show
    every trip). `trip_payable` is the amount after the Hyva/JCB minimum
    earning rule; `total_salary` uses that payable amount.
    """
    members = person_members(labour)
    minimums = (
        minimum_amounts()
        if any(m.category in MINIMUM_RULE_CATEGORIES for m in members)
        else {}
    )
    days = day_earnings(
        members, period_start, period_end,
        combined=True, minimum_amounts_map=minimums,
    )

    trip_total = sum((d['trip_total'] for d in days.values()), Decimal('0'))
    trip_payable = sum(
        (d['trip_payable'] for d in days.values()), Decimal('0')
    )
    bhatta_total = sum(
        (d['bhatta_total'] for d in days.values()), Decimal('0')
    )
    other_extra_total = sum(
        (d['other_extra_total'] for d in days.values()), Decimal('0')
    )
    rozi_total = sum((d['rozi_total'] for d in days.values()), Decimal('0'))
    minimum_adjustment = sum(
        (d['minimum_adjustment'] for d in days.values()), Decimal('0')
    )

    extra_total = bhatta_total + other_extra_total
    driver_total = LabourDriverPayment.objects.filter(
        labour_id__in=[m.pk for m in members],
        period_start__lte=period_end,
        period_end__gte=period_start,
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    total_salary = (
        trip_payable + extra_total + rozi_total + driver_total
    )
    advance_total_value = advance_total(labour, period_start, period_end)

    return {
        'trip_total': trip_total,
        'trip_payable': trip_payable,
        'bhatta_total': bhatta_total,
        'other_extra_total': other_extra_total,
        'minimum_adjustment': minimum_adjustment,
        'extra_total': extra_total,
        'rozi_total': rozi_total,
        'driver_total': driver_total,
        'total_salary': total_salary,
        'payable_amount': total_salary,
        'advance_total': advance_total_value,
        'days': days,
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
