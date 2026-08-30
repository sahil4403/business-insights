"""
Labour views — flexible per-trip groups, extras, advances, driver payments,
old balance tracking & settlement.

All views require login. Mobile-first styling. Date filters use the same
"from / to" pattern as the rest of the app.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from openpyxl import Workbook
from openpyxl.styles import Font
from io import BytesIO

from .forms import (
    LabourForm,
    LabourTripGroupForm,
    LabourExtraPaymentForm,
    LabourAdvanceForm,
    LabourAdvanceMultiForm,
    LabourDriverPaymentForm,
    LabourSettlementForm,
)
from .models import (
    Labour,
    LabourTripGroup,
    LabourExtraPayment,
    LabourAdvance,
    LabourDriverPayment,
    LabourOldBalance,
    LabourSettlement,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _parse_date(s, default=None):
    if not s:
        return default
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return default


def _ensure_old_balance(labour):
    ob, _ = LabourOldBalance.objects.get_or_create(labour=labour, defaults={'amount': Decimal('0')})
    return ob


def _per_labour_trip_share(labour, period_start, period_end):
    """
    Return total trip-share for this labour between period_start..period_end.
    Each trip group splits total_amount across its labourers.
    """
    total = Decimal('0')
    for grp in LabourTripGroup.objects.filter(
        date__gte=period_start, date__lte=period_end
    ).prefetch_related('labourers'):
        n = grp.labourers.count()
        if n and grp.labourers.filter(pk=labour.pk).exists():
            total += grp.total_amount / n
    return total


def _day_aggregates_for_labour(labour, period_start, period_end):
    """
    Build per-day rows: Date | Trips amount | Extra | Total | Advance.
    Returns list of dicts.
    """
    # Build a per-date map of all values
    days = {}

    def _ensure(d):
        if d not in days:
            days[d] = {
                'date': d,
                'trips_amount': Decimal('0'),
                'extra_amount': Decimal('0'),
                'advance_amount': Decimal('0'),
            }
        return days[d]

    # Trips: walk groups in range
    for grp in LabourTripGroup.objects.filter(
        date__gte=period_start, date__lte=period_end
    ).prefetch_related('labourers'):
        n = grp.labourers.count()
        if n and grp.labourers.filter(pk=labour.pk).exists():
            _ensure(grp.date)['trips_amount'] += grp.total_amount / n

    # Extras
    for ep in LabourExtraPayment.objects.filter(
        labour=labour, date__gte=period_start, date__lte=period_end
    ):
        _ensure(ep.date)['extra_amount'] += ep.amount

    # Advances
    for ad in LabourAdvance.objects.filter(
        labour=labour, date__gte=period_start, date__lte=period_end
    ):
        _ensure(ad.date)['advance_amount'] += ad.amount

    # Sort by date desc
    rows = list(days.values())
    rows.sort(key=lambda r: r['date'], reverse=True)
    return rows


# ----------------------------------------------------------------------------
# List
# ----------------------------------------------------------------------------

@login_required(login_url='/login/')
def labour_list(request):
    labours = Labour.objects.filter(is_active=True).order_by('name')

    # Pre-compute outstanding per labour
    ob_map = {ob.labour_id: ob.amount for ob in LabourOldBalance.objects.all()}

    # Count trip groups this month for context
    today = timezone.localdate()
    month_start = today.replace(day=1)

    cards = []
    for l in labours:
        cards.append({
            'obj': l,
            'old_balance': ob_map.get(l.id, Decimal('0')),
            'month_trip_groups': l.trip_groups.filter(date__gte=month_start).count(),
        })

    total_outstanding = sum((c['old_balance'] for c in cards), Decimal('0'))

    # -----------------------------------
    # EXPORTS — labour summary (list)
    # -----------------------------------

    export = request.GET.get('export')
    if export in ('pdf', 'pdf_preview'):
        response = HttpResponse(content_type='application/pdf')

        from core.pdf_utils import (
            get_registered_font,
            build_pdf_header_elements,
            get_indian_current_time_str,
            apply_data_table_style,
            finish_document,
        )
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph

        font_name = get_registered_font()

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=25,
            leftMargin=25,
            topMargin=25,
            bottomMargin=25,
        )

        styles = getSampleStyleSheet()
        header_style = ParagraphStyle(
            'HeaderStyle', parent=styles['Normal'],
            fontName=font_name, fontSize=9, leading=11, textColor=colors.white,
        )
        header_right = ParagraphStyle('HeaderRight', parent=header_style, alignment=2)
        header_center = ParagraphStyle('HeaderCenter', parent=header_style, alignment=1)
        body_style = ParagraphStyle(
            'BodyStyle', parent=styles['Normal'],
            fontName=font_name, fontSize=8.5, leading=11,
            textColor=colors.HexColor('#0F172A'),
        )
        right_body = ParagraphStyle('RightBody', parent=body_style, alignment=2)
        center_body = ParagraphStyle('CenterBody', parent=body_style, alignment=1)

        elements = build_pdf_header_elements(
            font_name=font_name,
            report_title="Labour Wise Summary Report",
            report_subtitle="All labour — driver status, monthly trip entries and outstanding",
            extra_meta=f"Generated on: {get_indian_current_time_str()}",
        )

        data = [
            [
                Paragraph('<b>Labour</b>', header_style),
                Paragraph('<b>Driver</b>', header_center),
                Paragraph('<b>Mobile</b>', header_center),
                Paragraph('<b>Trip Entries (Month)</b>', header_center),
                Paragraph('<b>Outstanding (₹)</b>', header_right),
            ]
        ]

        total_trips = 0
        for c in cards:
            l = c['obj']
            data.append([
                Paragraph(str(l.name or '—'), body_style),
                Paragraph('Yes' if l.is_driver else 'No', center_body),
                Paragraph(str(l.mobile or '—'), center_body),
                Paragraph(str(c.get('month_trip_groups', 0)), center_body),
                Paragraph(f"₹{c['old_balance']:,.2f}", right_body),
            ])
            total_trips += c.get('month_trip_groups', 0)

        data.append([
            Paragraph('<b>TOTAL</b>', body_style),
            Paragraph('', center_body),
            Paragraph('', center_body),
            Paragraph(f'<b>{total_trips}</b>', center_body),
            Paragraph(f'<b>₹{total_outstanding:,.2f}</b>', right_body),
        ])

        table = Table(data, repeatRows=1, colWidths=[180, 70, 130, 150, 150])
        apply_data_table_style(table, total_row=True)
        elements.append(table)
        finish_document(document, elements, font_name=font_name)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        disposition = 'inline' if request.GET.get('preview') == 'true' or export == 'pdf_preview' else 'attachment'
        response['Content-Disposition'] = f'{disposition}; filename="labour_report.pdf"'
        return response

    if export == 'excel':
        from openpyxl import Workbook
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = 'Labour Report'
        worksheet.append(['Labour', 'Driver', 'Mobile', 'Trip Entries (Month)', 'Outstanding (₹)'])
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
        for c in cards:
            l = c['obj']
            worksheet.append([
                l.name,
                'Yes' if l.is_driver else 'No',
                l.mobile or '',
                c.get('month_trip_groups', 0),
                float(c['old_balance']),
            ])
        worksheet.append(['TOTAL', '', '', sum(c.get('month_trip_groups', 0) for c in cards), float(total_outstanding)])
        for row in worksheet.iter_rows(min_row=2, max_col=5):
            for cell in row:
                if cell.column == 5:
                    cell.number_format = '₹#,##0.00'
        worksheet.column_dimensions['A'].width = 24
        worksheet.column_dimensions['C'].width = 16
        worksheet.column_dimensions['D'].width = 22
        worksheet.column_dimensions['E'].width = 18
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="labour_report.xlsx"'
        workbook.save(response)
        return response

    if export == 'csv':
        import csv as _csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="labour_report.csv"'
        writer = _csv.writer(response)
        writer.writerow(['Labour', 'Driver', 'Mobile', 'Trip Entries (Month)', 'Outstanding (₹)'])
        for c in cards:
            l = c['obj']
            writer.writerow([
                l.name,
                'Yes' if l.is_driver else 'No',
                l.mobile or '',
                c.get('month_trip_groups', 0),
                c['old_balance'],
            ])
        return response

    context = {
        'cards': cards,
        'labour_count': len(cards),
        'total_outstanding': total_outstanding,
        'driver_count': sum(1 for c in cards if c['obj'].is_driver),
    }
    return render(request, 'labour/labour_list.html', context)


@login_required(login_url='/login/')
def labour_create(request):
    if request.method == 'POST':
        form = LabourForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'Labour "{obj.name}" added.')
            return redirect('labour:list')
    else:
        form = LabourForm()

    return render(request, 'labour/labour_form.html', {
        'form': form,
        'page_title': 'Add Labour',
    })


@login_required(login_url='/login/')
def labour_edit(request, labour_id):
    labour = get_object_or_404(Labour, pk=labour_id)
    if request.method == 'POST':
        form = LabourForm(request.POST, instance=labour)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'Labour "{obj.name}" updated.')
            return redirect('labour:detail', labour_id=obj.id)
    else:
        form = LabourForm(instance=labour)

    return render(request, 'labour/labour_form.html', {
        'form': form,
        'page_title': f'Edit {labour.name}',
    })


# ----------------------------------------------------------------------------
# Detail
# ----------------------------------------------------------------------------

@login_required(login_url='/login/')
@require_POST
def labour_deactivate(request, labour_id):
    """Soft-delete: hide labour from list/details by setting is_active=False.
    Historical records (trips, advances, settlements) stay safe in the DB."""
    labour = get_object_or_404(Labour, pk=labour_id)
    labour.is_active = False
    labour.status = 'INACTIVE'
    labour.save(update_fields=['is_active', 'status', 'updated_at'])
    messages.success(request, f'"{labour.name}" has been removed. Historical data is preserved.')
    return redirect('labour:list')


@login_required(login_url='/login/')
def labour_detail(request, labour_id):
    labour = get_object_or_404(Labour, pk=labour_id)
    ob = _ensure_old_balance(labour)

    # Date range filter (default: current month)
    today = timezone.localdate()
    default_start = today.replace(day=1)
    period_start = _parse_date(request.GET.get('from_date'), default_start)
    period_end = _parse_date(request.GET.get('to_date'), today)

    rows = _day_aggregates_for_labour(labour, period_start, period_end)

    # Summary block
    trip_total = sum((r['trips_amount'] for r in rows), Decimal('0'))
    extra_total = sum((r['extra_amount'] for r in rows), Decimal('0'))
    advance_total = sum((r['advance_amount'] for r in rows), Decimal('0'))

    # Driver payment for the period (overlapping ranges)
    driver_qs = LabourDriverPayment.objects.filter(labour=labour).filter(
        period_start__lte=period_end, period_end__gte=period_start
    )
    driver_total = driver_qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    total_salary = trip_total + extra_total + driver_total
    payment = total_salary - advance_total
    # Excel formula: Final Amount = Payment − Old Balance
    final_amount = payment - ob.amount

    # Settlements within range
    settlements = LabourSettlement.objects.filter(
        labour=labour, settlement_date__gte=period_start, settlement_date__lte=period_end
    )

    # Pending settlements before this period
    pending_settlements = LabourSettlement.objects.filter(
        labour=labour
    ).order_by('-settlement_date')[:5]

    latest_settlement = LabourSettlement.objects.filter(labour=labour).order_by(
        '-settlement_date', '-id'
    ).first()

    context = {
        'labour': labour,
        'old_balance': ob,
        'rows': rows,
        'period_start': period_start,
        'period_end': period_end,
        'trip_total': trip_total,
        'extra_total': extra_total,
        'driver_total': driver_total,
        'advance_total': advance_total,
        'total_salary': total_salary,
        'payment': payment,
        'latest_settlement_id': latest_settlement.id if latest_settlement else None,
        'final_amount': final_amount,
        'settlements': settlements,
        'pending_settlements': pending_settlements,
        'driver_payments': driver_qs,
    }
    return render(request, 'labour/labour_detail.html', context)


# ----------------------------------------------------------------------------
# Trip Group
# ----------------------------------------------------------------------------

@login_required(login_url='/login/')
def trip_group_create(request):
    """Create a new trip-group entry. Supports 'add_another' flow."""
    add_another = request.GET.get('next') == 'add_another' or \
        request.POST.get('add_another') == '1'

    if request.method == 'POST':
        form = LabourTripGroupForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(
                request,
                f'Trip entry saved · {obj.trip_count} trips · ₹{obj.total_amount}.',
            )
            if request.POST.get('add_another') == '1':
                return redirect(f"{request.path}?next=add_another&date={obj.date.isoformat()}")
            return redirect('labour:list')
    else:
        initial_date = _parse_date(request.GET.get('date'), timezone.localdate())
        form = LabourTripGroupForm(initial={'date': initial_date})

    context = {
        'form': form,
        'page_title': 'Add Trip Entry',
        'show_add_another': True,
    }
    return render(request, 'labour/trip_group_form.html', context)


# ----------------------------------------------------------------------------
# Trip entry edit / delete / list — fix a wrong entry, shares recalculate
# automatically (total = trips × rate, split across the group).
# ----------------------------------------------------------------------------

@login_required(login_url='/login/')
def trip_group_edit(request, group_id):
    try:
        group = LabourTripGroup.objects.get(pk=group_id)
    except LabourTripGroup.DoesNotExist:
        messages.info(request, 'Entry already changed/deleted — page fresh kar ke dekho.')
        return redirect('labour:trips')

    if request.method == 'POST':
        form = LabourTripGroupForm(request.POST, instance=group)
        if form.is_valid():
            obj = form.save()
            messages.success(
                request,
                f'Trip entry updated · {obj.trip_count} trips · ₹{obj.total_amount}.',
            )
            return redirect('labour:list')
    else:
        form = LabourTripGroupForm(instance=group)

    return render(request, 'labour/trip_group_form.html', {
        'form': form,
        'page_title': 'Edit Trip Entry',
        'show_add_another': False,
        'editing_group': group,
        'selected_labourer_ids': set(
            group.labourers.values_list('id', flat=True)
        ),
    })


@login_required(login_url='/login/')
@require_POST
def trip_group_delete(request, group_id):
    try:
        group = LabourTripGroup.objects.get(pk=group_id)
    except LabourTripGroup.DoesNotExist:
        messages.info(request, 'Ye entry pehle se delete ho chuki hai.')
        return redirect('labour:list')
    messages.warning(request, f"Trip entry deleted · {group.date:%d-%b-%Y} · ₹{group.total_amount} (entry paise ab split nahi honge).")
    group.delete()
    return redirect('labour:list')


@login_required(login_url='/login/')
def trip_group_list(request):
    groups = LabourTripGroup.objects.prefetch_related('labourers').order_by(
        '-date', '-id'
    )[:40]
    rows = []
    for g in groups:
        labourers = list(g.labourers.order_by('name'))
        rows.append({
            'group': g,
            'labourers': labourers,
            'per_head': g.per_labour_share if labourers else Decimal('0'),
        })
    return render(request, 'labour/trip_group_list.html', {
        'rows': rows,
        'page_title': 'Trip Entries',
    })


# ----------------------------------------------------------------------------
# Extra payment
# ----------------------------------------------------------------------------

@login_required(login_url='/login/')
def extra_create(request, labour_id=None):
    labour = None
    if labour_id:
        labour = get_object_or_404(Labour, pk=labour_id)

    if request.method == 'POST':
        form = LabourExtraPaymentForm(request.POST, labour=labour)
        if form.is_valid():
            obj = form.save(commit=False)
            if labour is not None:
                obj.labour = labour
            obj.save()
            messages.success(request, f'Extra payment of ₹{obj.amount} saved.')
            if labour is not None:
                return redirect('labour:detail', labour_id=labour.id)
            return redirect('labour:list')
    else:
        form = LabourExtraPaymentForm(labour=labour)

    return render(request, 'labour/extra_form.html', {
        'form': form,
        'page_title': 'Add Extra Payment',
        'labour': labour,
    })


# ----------------------------------------------------------------------------
# Advance
# ----------------------------------------------------------------------------

@login_required(login_url='/login/')
def advance_create(request, labour_id=None):
    """Single-labour advance form."""
    labour = None
    if labour_id:
        labour = get_object_or_404(Labour, pk=labour_id)

    if request.method == 'POST':
        form = LabourAdvanceForm(request.POST, labour=labour)
        if form.is_valid():
            obj = form.save(commit=False)
            if labour is not None:
                obj.labour = labour
            try:
                obj.save()
            except Exception as e:  # unique constraint
                messages.error(request, f'Already an advance for this labour on that date.')
                return render(request, 'labour/advance_form.html', {
                    'form': form, 'page_title': 'Add Advance', 'labour': labour,
                })
            messages.success(request, f'Advance ₹{obj.amount} saved.')
            if labour is not None:
                return redirect('labour:detail', labour_id=labour.id)
            return redirect('labour:list')
    else:
        form = LabourAdvanceForm(labour=labour)

    return render(request, 'labour/advance_form.html', {
        'form': form,
        'page_title': 'Add Advance',
        'labour': labour,
    })


@login_required(login_url='/login/')
def advance_multi(request):
    """
    Day-view quick entry: pick a date, then enter amount for whichever
    labourers took advance. Only those with a value > 0 are saved.
    """
    today = timezone.localdate()
    selected_date = _parse_date(request.POST.get('date') or request.GET.get('date'), today)

    labours = list(Labour.objects.filter(is_active=True).order_by('name'))
    # Existing advances for selected_date, to pre-fill
    existing = {
        a.labour_id: a
        for a in LabourAdvance.objects.filter(date=selected_date)
    }
    # After a save, clear the amount inputs (reset) so it doesn't feel stuck,
    # but keep the ✓ marker for labourers who already have an advance that day.
    reset = request.GET.get('reset') == '1'
    # Flatten to (labour, existing_amount, has_existing) tuples for easy template iteration
    labour_rows = [
        (l,
         None if reset else (existing[l.id].amount if l.id in existing else None),
         l.id in existing)
        for l in labours
    ]

    if request.method == 'POST':
        saved = 0
        for l in labours:
            raw = request.POST.get(f'amount_{l.id}', '').strip()
            if not raw:
                continue
            try:
                amount = Decimal(raw)
            except Exception:
                continue
            if amount <= 0:
                continue
            # Upsert: only one advance per labour per day
            obj, created = LabourAdvance.objects.update_or_create(
                labour=l, date=selected_date,
                defaults={'amount': amount, 'note': request.POST.get(f'note_{l.id}', '').strip()},
            )
            saved += 1
        if saved:
            messages.success(request, f'{saved} advance(s) saved for {selected_date}.')
        else:
            messages.info(request, 'No advance amounts entered.')
        # After saving, jump back to the current date so the old-date screen
        # doesn't linger blank while entries already exist for it.
        return redirect(f"{request.path}?date={today.isoformat()}")

    context = {
        'page_title': 'Quick Advances',
        'selected_date': selected_date,
        'labours': labours,
        'existing': existing,
        'labour_rows': labour_rows,
    }
    return render(request, 'labour/advance_multi.html', context)


# ----------------------------------------------------------------------------
# Driver payment
# ----------------------------------------------------------------------------

@login_required(login_url='/login/')
def driver_payment_create(request, labour_id=None):
    labour = None
    if labour_id:
        labour = get_object_or_404(Labour, pk=labour_id)
        if not labour.is_driver:
            messages.warning(request, f'{labour.name} is not marked as driver.')

    if request.method == 'POST':
        form = LabourDriverPaymentForm(request.POST, labour=labour)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'Driver payment ₹{obj.amount} saved for {obj.labour.name}.')
            if labour is not None:
                return redirect('labour:detail', labour_id=labour.id)
            return redirect('labour:list')
    else:
        form = LabourDriverPaymentForm(labour=labour)

    return render(request, 'labour/driver_payment_form.html', {
        'form': form,
        'page_title': 'Add Driver Payment',
        'labour': labour,
    })


# ----------------------------------------------------------------------------
# Settlement
# ----------------------------------------------------------------------------

@login_required(login_url='/login/')
@require_POST
def labour_set_outstanding(request, labour_id):
    """Directly set the running old balance (outstanding) for a labour.
    Positive amount = labour owes owner. Use for prior dues / manual adjust."""
    labour = get_object_or_404(Labour, pk=labour_id)
    ob = _ensure_old_balance(labour)
    raw = request.POST.get('outstanding_amount', '').strip()
    try:
        new_amount = Decimal(raw or '0')
    except Exception:
        messages.error(request, 'Please enter a valid amount.')
        return redirect('labour:detail', labour_id=labour.id)
    if new_amount < 0:
        messages.error(request, 'Amount cannot be negative. Use 0 to clear dues.')
        return redirect('labour:detail', labour_id=labour.id)
    ob.amount = new_amount
    ob.save()
    messages.success(request, f'Outstanding for {labour.name} set to ₹{new_amount:.2f}.')
    return redirect('labour:detail', labour_id=labour.id)


@login_required(login_url='/login/')
@transaction.atomic
def settlement_create(request, labour_id):
    labour = get_object_or_404(Labour, pk=labour_id)
    ob = _ensure_old_balance(labour)
    today = timezone.localdate()

    if request.method == 'POST':
        form = LabourSettlementForm(request.POST)
        if form.is_valid():
            settlement = form.save(commit=False)
            settlement.labour = labour
            settlement.old_balance_before = ob.amount
            settlement.recalculate()
            settlement.save()
            # Update labour's old balance
            ob.amount = settlement.final_old_balance
            ob.save()
            messages.success(
                request,
                f'Settlement saved for {labour.name}. New old balance: ₹{ob.amount}.',
            )
            return redirect('labour:detail', labour_id=labour.id)
    else:
        form = LabourSettlementForm()

    # GET: compute live preview based on GET params or default period
    period_start = _parse_date(
        request.GET.get('period_start') or request.POST.get('period_start'),
        today.replace(day=1),
    )
    period_end = _parse_date(
        request.GET.get('period_end') or request.POST.get('period_end'),
        today,
    )

    # Recompute a preview object (not saved)
    preview = LabourSettlement(
        labour=labour,
        period_start=period_start,
        period_end=period_end,
        old_balance_before=ob.amount,
    )
    preview.recalculate()

    context = {
        'form': form,
        'page_title': 'Settle Payment',
        'labour': labour,
        'old_balance': ob,
        'preview': preview,
    }
    return render(request, 'labour/settlement_form.html', context)


# ----------------------------------------------------------------------------
# Settlement edit / revert — sirf sabse recent settlement pe, taaki old-balance
# chain sahi rahe. Revert: record delete + old balance (before) restore.
# ----------------------------------------------------------------------------

def _latest_settlement(labour):
    return LabourSettlement.objects.filter(labour=labour).order_by(
        '-settlement_date', '-id'
    ).first()


@login_required(login_url='/login/')
@transaction.atomic
def settlement_edit(request, settlement_id):
    settlement = get_object_or_404(LabourSettlement, pk=settlement_id)
    latest = _latest_settlement(settlement.labour)
    if latest is None or settlement.pk != latest.pk:
        messages.info(request, 'Sirf sabse recent settlement edit ho sakti hai — pahle baad waali revert karo.')
        return redirect('labour:detail', labour_id=settlement.labour_id)

    if request.method == 'POST':
        form = LabourSettlementForm(request.POST, instance=settlement)
        if form.is_valid():
            s = form.save(commit=False)
            # Period + old_balance_before locked — sirf amount/date/note badlo
            s.period_start = settlement.period_start
            s.period_end = settlement.period_end
            s.old_balance_before = settlement.old_balance_before
            s.recalculate()
            s.save()
            ob = _ensure_old_balance(settlement.labour)
            ob.amount = s.final_old_balance
            ob.save()
            messages.success(
                request,
                f'Settlement updated for {settlement.labour.name}. New old balance: ₹{ob.amount}.',
            )
            return redirect('labour:detail', labour_id=settlement.labour_id)
    else:
        form = LabourSettlementForm(instance=settlement)

    return render(request, 'labour/settlement_form.html', {
        'form': form,
        'page_title': 'Edit Settlement',
        'labour': settlement.labour,
        'old_balance': {'amount': settlement.old_balance_before},
        'preview': settlement,
        'editing': True,
        'settlement': settlement,
    })


@login_required(login_url='/login/')
@require_POST
def settlement_revert(request, settlement_id):
    settlement = get_object_or_404(LabourSettlement, pk=settlement_id)
    latest = _latest_settlement(settlement.labour)
    if latest is None or settlement.pk != latest.pk:
        messages.info(request, 'Sirf sabse recent settlement revert ho sakti hai.')
        return redirect('labour:detail', labour_id=settlement.labour_id)

    ob = _ensure_old_balance(settlement.labour)
    ob.amount = settlement.old_balance_before
    ob.save()
    messages.warning(
        request,
        f'Settlement {settlement.settlement_date:%d-%b-%Y} revert kar diya. '
        f'Old balance restore: ₹{ob.amount}.',
    )
    settlement.delete()
    return redirect('labour:detail', labour_id=settlement.labour_id)


# ----------------------------------------------------------------------------
# Labour Book — saare labour ke period statements ek hi PDF/Excel me
# ----------------------------------------------------------------------------

def _labour_statement_for_period(labour, period_start, period_end):
    """Full statement data for one labour in a period (mirrors labour_detail)."""
    ob, _ = LabourOldBalance.objects.get_or_create(
        labour=labour, defaults={'amount': Decimal('0')}
    )

    rows = _day_aggregates_for_labour(labour, period_start, period_end)

    trip_total = sum((r['trips_amount'] for r in rows), Decimal('0'))
    extra_total = sum((r['extra_amount'] for r in rows), Decimal('0'))
    advance_total = sum((r['advance_amount'] for r in rows), Decimal('0'))

    driver_qs = LabourDriverPayment.objects.filter(labour=labour).filter(
        period_start__lte=period_end, period_end__gte=period_start
    )
    driver_total = driver_qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    total_salary = trip_total + extra_total + driver_total
    payment = total_salary - advance_total
    final_amount = payment - ob.amount

    settlements = list(LabourSettlement.objects.filter(
        labour=labour,
        settlement_date__gte=period_start,
        settlement_date__lte=period_end,
    ))

    return {
        'labour': labour,
        'old_balance': ob.amount,
        'rows': rows,
        'trip_total': trip_total,
        'extra_total': extra_total,
        'driver_total': driver_total,
        'advance_total': advance_total,
        'total_salary': total_salary,
        'payment': payment,
        'final_amount': final_amount,
        'settlements': settlements,
        'driver_payments': list(driver_qs),
    }


@login_required(login_url='/login/')
def labour_book(request):
    today = timezone.localdate()
    period_start = _parse_date(request.GET.get('from_date'), today.replace(day=1))
    period_end = _parse_date(request.GET.get('to_date'), today)
    if period_start and period_end and period_start > period_end:
        period_start, period_end = period_end, period_start

    export = request.GET.get('export')

    labours = list(Labour.objects.filter(is_active=True).order_by('name'))
    statements = [
        _labour_statement_for_period(labour, period_start, period_end)
        for labour in labours
    ]

    if export == 'excel':
        return _labour_book_excel(statements, period_start, period_end)

    return _labour_book_pdf(statements, period_start, period_end)


@login_required(login_url='/login/')
def labour_statement_export(request, labour_id):
    """Ek single labour ka statement PDF/Excel — detail page se."""
    labour = get_object_or_404(Labour, pk=labour_id)
    today = timezone.localdate()
    period_start = _parse_date(request.GET.get('from_date'), today.replace(day=1))
    period_end = _parse_date(request.GET.get('to_date'), today)
    if period_start and period_end and period_start > period_end:
        period_start, period_end = period_end, period_start

    export = request.GET.get('export', 'pdf')
    st = _labour_statement_for_period(labour, period_start, period_end)

    safe_name = re.sub(r'[^A-Za-z0-9_-]+', '_', (labour.name or 'labour')).strip('_')

    from core.pdf_utils import get_indian_current_time_str
    period_label = (
        f"{period_start:%d-%b-%Y} to {period_end:%d-%b-%Y}"
        if period_start and period_end else 'All Transactions'
    )

    if export == 'excel':
        return _labour_book_excel(
            [st], period_start, period_end,
            filename=f'labour_statement_{safe_name}.xlsx',
        )

    return _labour_book_pdf(
        [st], period_start, period_end,
        filename=f'labour_statement_{safe_name}.pdf',
        report_title="Labour Account Statement",
        report_subtitle=(
            f"{labour.name} · {period_label} · "
            f"Generated on {get_indian_current_time_str()}"
        ),
        include_grand_summary=False,
    )


def _labour_book_excel(statements, period_start, period_end, filename='labour_book.xlsx'):
    from openpyxl.styles import PatternFill as _PF, Font as _F, Alignment as _A
    from openpyxl.utils import get_column_letter as gcl

    workbook = Workbook()
    workbook.remove(workbook.active)

    header_fill = _PF(start_color='16665A', end_color='16665A', fill_type='solid')
    header_font = _F(color='FFFFFF', bold=True)
    total_font = _F(bold=True)
    total_fill = _PF(start_color='EEF7F5', end_color='EEF7F5', fill_type='solid')

    if not statements:
        ws = workbook.create_sheet(title='No Data')
        ws.cell(row=1, column=1, value='No active labour found.').font = _F(bold=True)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        workbook.save(response)
        return response

    period_label = (
        f"{period_start:%d-%b-%Y} to {period_end:%d-%b-%Y}"
        if period_start and period_end else 'All Transactions'
    )

    for st in statements:
        labour = st['labour']
        sheet_name = ''.join(
            c for c in labour.name if c not in r'[]:*?/\\'
        )[:31] or 'Labour'

        ws = workbook.create_sheet(title=sheet_name)

        ws.cell(row=1, column=2, value='LABOUR ACCOUNT STATEMENT').font = _F(bold=True, size=13)

        for r, label, val in [
            (2, 'Labour', labour.name or '—'),
            (3, 'Type', 'Driver' if labour.is_driver else 'Labour'),
            (4, 'Mobile', labour.mobile or '—'),
            (5, 'Period', period_label),
        ]:
            ws.cell(row=r, column=1, value=label).font = _F(bold=True)
            ws.cell(row=r, column=2, value=val)

        # Summary block (mirrors detail page)
        summary_row = 7
        summary_items = [
            ('Total Trip Wages', st['trip_total']),
            ('Total Extra', st['extra_total']),
            ('Driver Payment', st['driver_total']),
            ('Total Salary', st['total_salary']),
            ('Total Advance', st['advance_total']),
            ('Payment (Salary − Adv)', st['payment']),
            ('Old Balance (owed to owner)', st['old_balance']),
            ('Final Amount', st['final_amount']),
        ]
        for i, (label, value) in enumerate(summary_items):
            col = 1 + i * 2
            cell = ws.cell(row=summary_row, column=col, value=label)
            cell.font = _F(bold=True, color='2563EB')
            ws.cell(row=summary_row, column=col + 1, value=f"₹{value:,.2f}")

        # Daily activity table
        head_row = 9
        headers = ['Date', 'Trips Amount', 'Extra', 'Total (T+E)', 'Advance']
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=head_row, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = _A(horizontal='center', vertical='center')

        r = head_row + 1
        for row in st['rows']:
            ws.cell(row=r, column=1, value=row['date'].strftime('%d-%b-%Y'))
            ws.cell(row=r, column=2, value=float(row['trips_amount']))
            ws.cell(row=r, column=3, value=float(row['extra_amount']))
            ws.cell(row=r, column=4, value=float(row['trips_amount'] + row['extra_amount']))
            ws.cell(row=r, column=5, value=float(row['advance_amount']))
            r += 1

        ws.cell(row=r, column=1, value='TOTAL').font = total_font
        ws.cell(row=r, column=2, value=float(st['trip_total'])).font = total_font
        ws.cell(row=r, column=3, value=float(st['extra_total'])).font = total_font
        ws.cell(row=r, column=4, value=float(st['total_salary'] - st['driver_total'])).font = total_font
        ws.cell(row=r, column=5, value=float(st['advance_total'])).font = total_font
        for col in range(1, 6):
            ws.cell(row=r, column=col).fill = total_fill

        # Settlements within range
        if st['settlements']:
            r += 2
            ws.cell(row=r, column=1, value='Settlements in Range').font = _F(bold=True)
            r += 1
            ws.cell(row=r, column=1, value='Date')
            ws.cell(row=r, column=2, value='Period')
            ws.cell(row=r, column=3, value='Cash Paid')
            ws.cell(row=r, column=4, value='New Old Balance')
            for cell in ws[r]:
                if cell.value:
                    cell.font = _F(bold=True)
            r += 1
            for s in st['settlements']:
                ws.cell(row=r, column=1, value=s.settlement_date.strftime('%d-%b-%Y'))
                ws.cell(row=r, column=2, value=f"{s.period_start:%d-%b} → {s.period_end:%d-%b}")
                ws.cell(row=r, column=3, value=float(s.cash_paid))
                ws.cell(row=r, column=4, value=float(s.final_old_balance))
                r += 1

        for col, width in {'A': 16, 'B': 14, 'C': 14, 'D': 15, 'E': 14}.items():
            ws.column_dimensions[col].width = width

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    workbook.save(response)
    return response


def _labour_book_pdf(statements, period_start, period_end, filename='labour_book.pdf', report_title='Labour Statements Book', report_subtitle=None, include_grand_summary=True):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    from core.pdf_utils import (
        get_registered_font,
        build_pdf_header_elements,
        get_indian_current_time_str,
        build_summary_cards,
        apply_data_table_style,
        finish_document,
        build_thankyou_note,
        get_pdf_styles,
        BRAND,
        BRAND_DARK,
    )
    font_name = get_registered_font()

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=9 * mm,
        leftMargin=9 * mm,
        topMargin=11 * mm,
        bottomMargin=11 * mm,
    )

    styles = get_pdf_styles(font_name)

    def _wrapped_style(name, **kw):
        return ParagraphStyle(
            name, parent=getSampleStyleSheet()['Normal'],
            fontName=font_name, **kw,
        )

    if period_start and period_end:
        book_period = f"{period_start:%d-%b-%Y} to {period_end:%d-%b-%Y}"
    else:
        book_period = 'All Transactions'

    elements = build_pdf_header_elements(
        font_name=font_name,
        report_title=report_title,
        report_subtitle=(
            report_subtitle
            if report_subtitle is not None
            else (
                f"All labour · {book_period} · "
                f"Generated on {get_indian_current_time_str()}"
            )
        ),
    )

    total_salary = Decimal('0')
    total_advance = Decimal('0')
    total_opening = Decimal('0')
    total_final = Decimal('0')

    for i, st in enumerate(statements):
        labour = st['labour']

        # ---------- 1. IDENTITY BAND (clean, boxed, professional) ----------
        name_style = _wrapped_style('LName', fontSize=13, leading=17, textColor=BRAND_DARK)
        field_lbl = _wrapped_style('LFieldLbl', fontSize=6.5, leading=8.5, textColor=colors.HexColor('#94a3b8'))
        field_val = _wrapped_style('LFieldVal', fontSize=9, leading=12, textColor=colors.HexColor('#0f172a'))

        field_rows = []
        for lbl, val in [
            ('Type', 'Driver' if labour.is_driver else 'Labour'),
            ('Mobile', labour.mobile or '—'),
            ('Period', book_period),
        ]:
            field_rows.append([
                Paragraph(lbl.upper(), field_lbl),
                Paragraph(f'<b>{val}</b>', field_val),
            ])
        fields = Table(field_rows, colWidths=[22 * mm, 48 * mm])
        fields.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))

        identity = Table(
            [[Paragraph(f'<b>{labour.name}</b>', name_style), fields]],
            colWidths=['58%', '42%'],
        )
        identity.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fbfcfd')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#e2e8f0')),
            ('LINEAFTER', (0, 0), (0, 0), 0.8, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 16),
            ('RIGHTPADDING', (1, 0), (1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))

        head_block = [identity, Spacer(1, 10)]

        # ---------- 2. KPI CARDS (4 + 4, readable) ----------
        earnings_cards = build_summary_cards(
            [
                {'label': 'Total Trip Wages', 'value': f"₹{st['trip_total']:,.2f}", 'color': '#16665a'},
                {'label': 'Total Extra', 'value': f"₹{st['extra_total']:,.2f}", 'color': '#2563eb'},
                {'label': 'Driver Payment', 'value': f"₹{st['driver_total']:,.2f}", 'color': '#7c3aed'},
                {'label': 'Total Salary', 'value': f"₹{st['total_salary']:,.2f}", 'color': '#0f766e'},
            ],
            font_name=font_name,
        )

        settlement_cards = build_summary_cards(
            [
                {'label': 'Total Advance', 'value': f"₹{st['advance_total']:,.2f}", 'color': '#dc2626'},
                {'label': 'Payment (Salary - Adv)', 'value': f"₹{st['payment']:,.2f}", 'color': '#075985'},
                {'label': 'Old Balance', 'value': f"₹{st['old_balance']:,.2f}", 'color': '#b45309'},
                {
                    'label': 'Final Amount',
                    'value': (
                        f"₹{st['final_amount']:,.2f}"
                        if st['final_amount'] >= 0
                        else f"Outstanding ₹{abs(st['final_amount']):,.2f}"
                    ),
                    'color': '#dc2626' if st['final_amount'] < 0 else '#059669',
                    'sub': (
                        'Labour owes owner' if st['final_amount'] < 0
                        else 'To pay labour'
                    ),
                },
            ],
            font_name=font_name,
        )

        head_block.append(earnings_cards)
        head_block.append(Spacer(1, 6))
        head_block.append(settlement_cards)
        head_block.append(Spacer(1, 8))

        elements.append(KeepTogether(head_block))

        # ---------- 3. DAILY ACTIVITY TABLE ----------
        daily_data = [
            [
                Paragraph('<b>Date</b>', styles['header']),
                Paragraph('<b>Trips (₹)</b>', styles['header_r']),
                Paragraph('<b>Extra (₹)</b>', styles['header_r']),
                Paragraph('<b>Total (₹)</b>', styles['header_r']),
                Paragraph('<b>Advance (₹)</b>', styles['header_r']),
            ]
        ]
        for row in st['rows']:
            daily_data.append([
                Paragraph(row['date'].strftime('%d-%b-%Y'), styles['body']),
                Paragraph(f"₹{row['trips_amount']:,.2f}", styles['body_r']),
                Paragraph(f"₹{row['extra_amount']:,.2f}", styles['body_r']),
                Paragraph(f"₹{(row['trips_amount'] + row['extra_amount']):,.2f}", styles['body_r']),
                Paragraph(f"₹{row['advance_amount']:,.2f}", styles['body_r']),
            ])
        if len(daily_data) > 1:
            daily_data.append([
                Paragraph('<b>TOTAL</b>', styles['body']),
                Paragraph(f"<b>₹{st['trip_total']:,.2f}</b>", styles['body_r']),
                Paragraph(f"<b>₹{st['extra_total']:,.2f}</b>", styles['body_r']),
                Paragraph(f"<b>₹{(st['total_salary'] - st['driver_total']):,.2f}</b>", styles['body_r']),
                Paragraph(f"<b>₹{st['advance_total']:,.2f}</b>", styles['body_r']),
            ])

        daily_table = Table(
            daily_data,
            repeatRows=1,
            colWidths=[32 * mm, 40 * mm, 40 * mm, 40 * mm, 40 * mm],
        )
        apply_data_table_style(daily_table, total_row=True)
        elements.append(daily_table)

        # ---------- 4. SETTLEMENTS IN RANGE ----------
        if st['settlements']:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph('<b>Settlements in this period</b>', _wrapped_style('SettleHead', fontSize=9.5, leading=12, textColor=BRAND_DARK)))
            s_data = [
                [
                    Paragraph('<b>Date</b>', styles['header']),
                    Paragraph('<b>Period</b>', styles['header']),
                    Paragraph('<b>Cash Paid (₹)</b>', styles['header_r']),
                    Paragraph('<b>New Old Balance (₹)</b>', styles['header_r']),
                ]
            ]
            for s in st['settlements']:
                s_data.append([
                    Paragraph(s.settlement_date.strftime('%d-%b-%Y'), styles['body']),
                    Paragraph(f"{s.period_start:%d-%b} to {s.period_end:%d-%b}", styles['body']),
                    Paragraph(f"₹{s.cash_paid:,.2f}", styles['body_r']),
                    Paragraph(f"₹{s.final_old_balance:,.2f}", styles['body_r']),
                ])
            s_table = Table(s_data, repeatRows=1, colWidths=[34 * mm, 44 * mm, 56 * mm, 58 * mm])
            apply_data_table_style(s_table, total_row=False)
            elements.append(s_table)

        total_salary += st['total_salary']
        total_advance += st['advance_total']
        total_opening += st['old_balance']
        total_final += st['final_amount']

        if i < len(statements) - 1:
            elements.append(Spacer(1, 22))
            elements.append(PageBreak())

    if include_grand_summary:
        grand_cards = build_summary_cards(
            [
                {'label': 'Total Salary', 'value': f"₹{total_salary:,.2f}", 'color': '#0f766e'},
                {'label': 'Total Advance', 'value': f"₹{total_advance:,.2f}", 'color': '#dc2626'},
                {'label': 'Total Old Balance', 'value': f"₹{total_opening:,.2f}", 'color': '#b45309'},
                {
                    'label': 'Total Final Amount',
                    'value': (
                        f"₹{total_final:,.2f}"
                        if total_final >= 0 else f"Outstanding ₹{abs(total_final):,.2f}"
                    ),
                    'color': '#dc2626' if total_final < 0 else '#059669',
                },
            ],
            font_name=font_name,
        )
        elements.append(Spacer(1, 10))
        elements.append(Paragraph('<b>GRAND SUMMARY — All Labour</b>', _wrapped_style('GrandHead', fontSize=9.5, leading=12, textColor=BRAND_DARK)))
        elements.append(grand_cards)

    elements.extend(build_thankyou_note(
        "Books prepared from the labour ledger. For any query, contact us.",
        font_name=font_name,
    ))

    finish_document(document, elements, font_name=font_name)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
