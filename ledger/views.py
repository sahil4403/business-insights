from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.utils import timezone

from django.db.models.functions import Coalesce
from django.db.models import Q
from core.audit import log_action
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from customers.models import Customer
from trips.models import Trip, TripPayment

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

from django.conf import settings
from core.utils import get_safe_next, get_safe_next_or_referer

LUMPSUM_NOTE = 'Customer lumpsum / on-account payment'


def _payment_transactions(period_payments, today_date):
    """Build statement transaction dicts for payments.

    Rows created by lumpsum auto-allocation share the same default note;
    when several land on the SAME day they are merged into ONE credit line
    showing the full amount actually received that day.
    """
    def pdate(p):
        return p.payment_date or (p.trip.trip_date if p.trip else today_date)

    splits = {}
    items = []
    for payment in period_payments:
        if payment.trip_id and (payment.notes or '') == LUMPSUM_NOTE:
            splits.setdefault(pdate(payment), []).append(payment)
        else:
            items.append((pdate(payment), 'single', payment))

    for pdate_key, group in splits.items():
        if len(group) > 1:
            items.append((pdate_key, 'merged', group))
        else:
            items.append((pdate_key, 'single', group[0]))

    items.sort(key=lambda item: item[0])

    transactions = []
    for p_date, kind, payload in items:
        if kind == 'merged':
            methods = [p.payment_method for p in payload if p.payment_method]
            method_name = methods[0].name if methods else None
            codes = [p.trip.trip_code for p in payload if p.trip and p.trip.trip_code]
            shown = ', '.join(codes[:3])
            if len(codes) > 3:
                shown += f' +{len(codes) - 3} more'
            total = sum((p.amount for p in payload), Decimal('0'))
            desc = (
                f"Lumpsum Payment - {method_name} ({len(payload)} trips: {shown})"
                if method_name
                else f"Lumpsum Payment Received ({len(payload)} trips: {shown})"
            )
            transactions.append({
                'date': p_date,
                'type': 'PAYMENT',
                'description': desc,
                'debit': Decimal('0'),
                'credit': total,
                'reference': codes[0] if codes else 'On-Account',
                'destination': '',
                'trip_id': None,
                'payment_id': None,
                'merged_payments': [
                    {'id': p.id, 'amount': p.amount,
                     'trip_code': p.trip.trip_code if p.trip else '',
                     'payment_date': p.payment_date}
                    for p in payload
                ],
            })
        else:
            payment = payload
            p_ref = payment.trip.trip_code if payment.trip else (payment.reference_number or "On-Account")
            p_trip_id = payment.trip.id if payment.trip else None
            p_destination = (payment.trip.destination or '') if payment.trip else ''
            p_type = getattr(payment, 'payment_type', 'RECEIVED')

            if p_type == 'PAID':
                p_desc = f"💸 Payment Paid - {payment.payment_method.name}" if payment.payment_method else "Payment Paid to Party"
                transactions.append({
                    'date': p_date,
                    'type': 'PAYMENT_PAID',
                    'description': p_desc,
                    'debit': payment.amount,
                    'credit': Decimal('0'),
                    'reference': p_ref,
                    'destination': p_destination,
                    'trip_id': p_trip_id,
                    'payment_id': payment.id,
                })
            elif p_type == 'CONTRA':
                transactions.append({
                    'date': p_date,
                    'type': 'CONTRA',
                    'description': "🔄 Contra Settlement (Mutual Netting Off)",
                    'debit': Decimal('0'),
                    'credit': payment.amount,
                    'reference': p_ref,
                    'destination': p_destination,
                    'trip_id': p_trip_id,
                    'payment_id': payment.id,
                })
            else:
                p_desc = f"Payment - {payment.payment_method.name}" if payment.payment_method else "Payment Received"
                transactions.append({
                    'date': p_date,
                    'type': 'PAYMENT',
                    'description': p_desc,
                    'debit': Decimal('0'),
                    'credit': payment.amount,
                    'reference': p_ref,
                    'destination': p_destination,
                    'trip_id': p_trip_id,
                    'payment_id': payment.id,
                })
    return transactions


@login_required(login_url='/login/')
def customer_statement(request, customer_id):
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    today = datetime.today().date()

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if from_date:
        try:
            from_date = datetime.strptime(
                from_date,
                '%Y-%m-%d'
            ).date()
        except ValueError:
            from_date = None

    if to_date:
        try:
            to_date = datetime.strptime(
                to_date,
                '%Y-%m-%d'
            ).date()
        except ValueError:
            to_date = None

    if not from_date:
        from_date = None

    if not to_date:
        to_date = today

    # All customer trips
    customer_trips = Trip.objects.filter(
        customer=customer
    ).prefetch_related(
        'payments',
        'drivers'
    ).select_related(
        'material',
        'vehicle'
    )

    # All customer payments (both trip-linked payments and direct on-account payments)
    customer_payments = TripPayment.objects.filter(
        Q(customer=customer) | Q(trip__customer=customer)
    ).annotate(
        effective_date=Coalesce('payment_date', 'trip__trip_date')
    ).select_related(
        'trip',
        'payment_method'
    )

    # Opening balance starts from the customer's manually-entered value
    opening_balance = customer.opening_balance or Decimal('0')

    if from_date:
        previous_trips = customer_trips.filter(
            trip_date__lt=from_date
        )

        previous_payments = customer_payments.filter(
            effective_date__lt=from_date
        )

        opening_sales = sum(
            trip.total_amount if trip.transaction_type != 'VENDOR_SUPPLY' else -trip.total_amount
            for trip in previous_trips
        )

        opening_payments = sum(
            payment.amount if getattr(payment, 'payment_type', 'RECEIVED') != 'PAID' else -payment.amount
            for payment in previous_payments
        )

        opening_balance += (
            opening_sales - opening_payments
        )

    # Period transactions
    transactions = []

    period_trips = customer_trips

    if from_date:
        period_trips = period_trips.filter(
            trip_date__gte=from_date
        )

    if to_date:
        period_trips = period_trips.filter(
            trip_date__lte=to_date
        )

    period_payments = customer_payments

    if from_date:
        period_payments = period_payments.filter(
            effective_date__gte=from_date
        )

    if to_date:
        period_payments = period_payments.filter(
            effective_date__lte=to_date
        )

    # -----------------------------
    # MATERIAL FILTER + SUMMARY
    # -----------------------------
    from django.db.models import Sum, Count as AggCount

    raw_material = (request.GET.get('material') or '').strip()
    # Multi-select supported: comma separated ids e.g. ?material=3,7
    raw_mat_ids = [p.strip() for p in raw_material.split(',') if p.strip().isdigit()]
    valid_mat_ids = set()
    if raw_mat_ids:
        valid_mat_ids = set(
            customer_trips.filter(
                material_id__in=[int(i) for i in raw_mat_ids]
            ).values_list('material_id', flat=True)
        )
    selected_material_ids = [int(i) for i in raw_mat_ids if int(i) in valid_mat_ids]
    selected_material_param = ','.join(str(i) for i in selected_material_ids)

    raw_vtype = (request.GET.get('vehicle_type') or '').strip()
    selected_vtype_id = None
    if raw_vtype.isdigit():
        candidate = int(raw_vtype)
        if customer_trips.filter(vehicle__vehicle_type_id=candidate).exists():
            selected_vtype_id = candidate

    # Material-wise summary for the date period.
    # Outward sales and inward vendor supply are shown as separate rows
    # (is_inward flag drives the badge in the template) so vendor-supplied
    # materials like Crushed Stone also appear here.
    material_summary = list(
        period_trips
        .values('material_id', 'material__name', 'transaction_type')
        .annotate(
            total_qty=Sum('quantity'),
            trip_count=AggCount('id'),
            total_amount=Sum('total_amount'),
        )
        .order_by('material__name', 'transaction_type')
    )
    for row in material_summary:
        row['is_inward'] = row['transaction_type'] == 'VENDOR_SUPPLY'

    # Multi-select helpers: each chip toggles its own id in/out of the
    # comma-separated ?material= list.
    sel_set = set(selected_material_ids)

    def _material_toggle_param(mid):
        if mid in sel_set:
            remaining = [i for i in selected_material_ids if i != mid]
        else:
            remaining = selected_material_ids + [mid]
        return ','.join(str(i) for i in remaining)

    for row in material_summary:
        row['is_selected'] = row['material_id'] in sel_set
        row['toggle_param'] = _material_toggle_param(row['material_id'])

    # Vehicle-type-wise summary for the date period (same inward/outward split)
    vtype_summary = list(
        period_trips
        .filter(vehicle__isnull=False)
        .values(
            'vehicle__vehicle_type_id',
            'vehicle__vehicle_type__name',
            'vehicle__vehicle_type__code',
            'transaction_type',
        )
        .annotate(
            total_qty=Sum('quantity'),
            trip_count=AggCount('id'),
            total_amount=Sum('total_amount'),
        )
        .order_by('vehicle__vehicle_type__name', 'transaction_type')
    )
    for row in vtype_summary:
        row['is_inward'] = row['transaction_type'] == 'VENDOR_SUPPLY'

    # Materials this customer has ever ordered OR received (for filter chips)
    materials_list = [
        {
            'id': mid,
            'name': mname,
            'is_selected': mid in sel_set,
            'toggle_param': _material_toggle_param(mid),
        }
        for mid, mname in (
            customer_trips.exclude(material__isnull=True)
            .values_list('material_id', 'material__name')
            .distinct()
            .order_by('material__name')
        )
    ]

    # Vehicle types this customer has used (for filter chips)
    vtypes_list = list(
        customer_trips.filter(vehicle__isnull=False)
        .exclude(vehicle__vehicle_type__isnull=True)
        .values_list('vehicle__vehicle_type_id', 'vehicle__vehicle_type__name', 'vehicle__vehicle_type__code')
        .distinct()
        .order_by('vehicle__vehicle_type__name')
    )

    if selected_material_ids:
        period_trips = period_trips.filter(material_id__in=selected_material_ids)

    if selected_vtype_id:
        period_trips = period_trips.filter(vehicle__vehicle_type_id=selected_vtype_id)

    # Trips (Outward Customer Delivery vs Inward Vendor Supply)
    for trip in period_trips:
        if trip.transaction_type == 'VENDOR_SUPPLY':
            # Inward supply from vendor to us -> Credit (increases what we owe him or reduces receivable)
            transactions.append({
                'date': trip.trip_date,
                'type': 'VENDOR_SUPPLY',
                'description': (
                    f"📦 Inward Supply ({trip.material.name} - "
                    f"{trip.quantity} × ₹{trip.rate})"
                ),
                'debit': Decimal('0'),
                'credit': trip.total_amount,
                'reference': trip.trip_code,
                'destination': trip.destination or '',
                'trip_id': trip.id,
                'outstanding': trip.outstanding_amount,
            })
        else:
            # Outward supply to customer -> Debit (increases receivable)
            transactions.append({
                'date': trip.trip_date,
                'type': 'SALE',
                'description': (
                    f"{trip.material.name} - "
                    f"{trip.quantity} × ₹{trip.rate}"
                ),
                'debit': trip.total_amount,
                'credit': Decimal('0'),
                'reference': trip.trip_code,
                'destination': trip.destination or '',
                'trip_id': trip.id,
                'outstanding': trip.outstanding_amount,
            })

    # Payments (Received vs Paid vs Contra)
    # Same-day lumpsum auto-allocation rows merge into ONE full-amount credit line.
    transactions.extend(
        _payment_transactions(period_payments, timezone.localdate())
    )

    transactions.sort(
        key=lambda transaction: (
            transaction['date'],
            transaction['type'] == 'PAYMENT'
        )
    )

    # Running balance
    running_balance = opening_balance

    for transaction in transactions:
        running_balance += (
            transaction['debit']
            - transaction['credit']
        )

        transaction['balance'] = running_balance

    total_sales = sum(
        transaction['debit']
        for transaction in transactions
    )

    total_received = sum(
        transaction['credit']
        for transaction in transactions
    )

    closing_balance = (
        opening_balance
        + total_sales
        - total_received
    )

    unpaid_trips = [
        t for t in customer_trips if t.outstanding_amount > 0
    ]

    from master_data.models import PaymentMethod
    payment_methods = PaymentMethod.objects.filter(is_active=True)

    is_admin_user = request.user.is_authenticated and request.user.is_superuser

    # WhatsApp share text — short summary (poori detail PDF attachment me jati hai)
    if from_date and to_date:
        period_label = f"{from_date.strftime('%d %b %Y')} - {to_date.strftime('%d %b %Y')}"
    elif from_date:
        period_label = f"From {from_date.strftime('%d %b %Y')}"
    elif to_date:
        period_label = f"Till {to_date.strftime('%d %b %Y')}"
    else:
        period_label = "All time"

    if closing_balance > 0:
        dues_line = f"*Pending: ₹{closing_balance:,.0f}*"
    else:
        dues_line = "Account Cleared ✅"

    whatsapp_text = (
        f"Hello {customer.name} ji 👋\n"
        f"*Statement of Account* ({period_label})\n"
        f"Total Billed: ₹{total_sales:,.0f}\n"
        f"Total Received: ₹{total_received:,.0f}\n"
        f"{dues_line}\n"
        f"(Statement PDF attached hai 📎)\n"
        f"Thank You"
    )

    context = {
        'customer': customer,
        'transactions': transactions,
        'total_sales': total_sales,
        'total_received': total_received,
        'opening_balance': opening_balance,
        'closing_balance': closing_balance,
        'whatsapp_text': whatsapp_text,
        'from_date': from_date,
        'to_date': to_date,
        'unpaid_trips': unpaid_trips,
        'payment_methods': payment_methods,
        'is_admin_user': is_admin_user,
        'material_summary': material_summary,
        'materials_list': materials_list,
        'selected_material_ids': selected_material_ids,
        'selected_material_param': selected_material_param,
        'vtype_summary': vtype_summary,
        'vtypes_list': vtypes_list,
        'selected_vtype_id': selected_vtype_id,
        'qs_dates': (
            f"from_date={from_date.isoformat()}" if from_date else ''
        ) + (
            f"{'&' if from_date else ''}to_date={to_date.isoformat()}" if to_date else ''
        ),
    }

    return render(
        request,
        'ledger/customer_statement.html',
        context
    )

@login_required(login_url='/login/')
def customer_statement_pdf(request, customer_id):
    customer = get_object_or_404(
        Customer,
        pk=customer_id
    )

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if from_date:
        try:
            from_date = datetime.strptime(
                from_date,
                '%Y-%m-%d'
            ).date()
        except ValueError:
            from_date = None

    if to_date:
        try:
            to_date = datetime.strptime(
                to_date,
                '%Y-%m-%d'
            ).date()
        except ValueError:
            to_date = None

    customer_trips = Trip.objects.filter(
        customer=customer
    ).select_related(
        'material',
        'vehicle'
    )

    customer_payments = TripPayment.objects.filter(
        Q(customer=customer) | Q(trip__customer=customer)
    ).annotate(
        effective_date=Coalesce('payment_date', 'trip__trip_date')
    ).select_related(
        'trip',
        'payment_method'
    )

    opening_balance = customer.opening_balance or Decimal('0')

    if from_date:
        previous_trips = customer_trips.filter(
            trip_date__lt=from_date
        )

        previous_payments = customer_payments.filter(
            effective_date__lt=from_date
        )

        opening_sales = sum(
            trip.total_amount if trip.transaction_type != 'VENDOR_SUPPLY' else -trip.total_amount
            for trip in previous_trips
        )

        opening_received = sum(
            payment.amount if payment.payment_type != 'PAID' else -payment.amount
            for payment in previous_payments
        )

        opening_balance += (
            opening_sales - opening_received
        )

    transactions = []

    period_trips = customer_trips

    if from_date:
        period_trips = period_trips.filter(
            trip_date__gte=from_date
        )

    if to_date:
        period_trips = period_trips.filter(
            trip_date__lte=to_date
        )

    period_payments = customer_payments

    if from_date:
        period_payments = period_payments.filter(
            effective_date__gte=from_date
        )

    if to_date:
        period_payments = period_payments.filter(
            effective_date__lte=to_date
        )

    # Optional material / vehicle-type filters (validated against this customer's trips)
    # Material supports multi-select: comma separated ids e.g. ?material=3,7
    raw_material = (request.GET.get('material') or '').strip()
    raw_mat_ids = [p.strip() for p in raw_material.split(',') if p.strip().isdigit()]
    valid_mat_ids = set()
    if raw_mat_ids:
        valid_mat_ids = set(
            customer_trips.filter(
                material_id__in=[int(i) for i in raw_mat_ids]
            ).values_list('material_id', flat=True)
        )
    selected_material_ids = [int(i) for i in raw_mat_ids if int(i) in valid_mat_ids]

    raw_vtype = (request.GET.get('vehicle_type') or '').strip()
    selected_vtype_id = None
    if raw_vtype.isdigit() and customer_trips.filter(vehicle__vehicle_type_id=int(raw_vtype)).exists():
        selected_vtype_id = int(raw_vtype)

    if selected_material_ids:
        period_trips = period_trips.filter(material_id__in=selected_material_ids)

    if selected_vtype_id:
        period_trips = period_trips.filter(vehicle__vehicle_type_id=selected_vtype_id)

    for trip in period_trips:
        material_name = trip.material.name if trip.material else '—'

        if trip.transaction_type == 'VENDOR_SUPPLY':
            # Inward supply from vendor -> Credit (same as HTML statement)
            transactions.append({
                'date': trip.trip_date,
                'type': 'INWARD',
                'description': (
                    f"Inward Supply ({material_name} - "
                    f"{trip.quantity} × ₹{trip.rate})"
                ),
                'debit': Decimal('0'),
                'credit': trip.total_amount,
                'reference': trip.trip_code,
                'destination': trip.destination or '',
            })
        else:
            # Outward supply to customer -> Debit
            transactions.append({
                'date': trip.trip_date,
                'type': 'SALE',
                'description': (
                    f"{material_name} - "
                    f"{trip.quantity} × ₹{trip.rate}"
                ),
                'debit': trip.total_amount,
                'credit': Decimal('0'),
                'reference': trip.trip_code,
                'destination': trip.destination or '',
            })

    transactions.extend(
        _payment_transactions(period_payments, timezone.localdate())
    )

    transactions.sort(
        key=lambda transaction: (
            transaction['date'],
            transaction['type'] == 'PAYMENT'
        )
    )

    running_balance = opening_balance

    for transaction in transactions:
        running_balance += (
            transaction['debit']
            - transaction['credit']
        )

        transaction['balance'] = running_balance

    total_sales = sum(
        transaction['debit']
        for transaction in transactions
    )

    total_received = sum(
        transaction['credit']
        for transaction in transactions
    )

    closing_balance = (
        opening_balance
        + total_sales
        - total_received
    )

    buffer = BytesIO()

    font_path = os.path.join(
        settings.BASE_DIR,
        'ledger',
        'fonts',
        'NotoSans-Regular.ttf'
    )

    pdfmetrics.registerFont(
        TTFont(
            'NotoSans',
            font_path
        )
    )
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=9 * mm,
        leftMargin=9 * mm,
        topMargin=11 * mm,
        bottomMargin=11 * mm,
    )

    styles = getSampleStyleSheet()

    from core.pdf_utils import (
        get_registered_font,
        build_pdf_header_elements,
        get_indian_current_time_str,
        build_summary_cards,
        apply_data_table_style,
        finish_document,
        build_thankyou_note,
    )
    font_name = get_registered_font()

    if from_date:
        period_text = (
            f"{from_date.strftime('%d-%b-%Y')} "
            f"to "
            f"{to_date.strftime('%d-%b-%Y') if to_date else 'Present'}"
        )
    else:
        period_text = "All Transactions"

    meta_info = f"Customer: <b>{customer.name}</b> (Code: {customer.customer_code}) | Statement Period: <b>{period_text}</b>"

    filter_labels = []
    if selected_material_ids:
        from master_data.models import Material
        mat_names = list(
            Material.objects.filter(id__in=selected_material_ids)
            .values_list('name', flat=True)
        )
        if len(mat_names) == 1:
            filter_labels.append(f"Material: {mat_names[0]}")
        else:
            filter_labels.append(f"Materials: {', '.join(mat_names)}")
    if selected_vtype_id:
        try:
            from master_data.models import VehicleType
            filter_labels.append(f"Vehicle Type: {VehicleType.objects.get(pk=selected_vtype_id).name}")
        except Exception:
            pass
    if filter_labels:
        meta_info += " | " + " | ".join(filter_labels)

    elements = build_pdf_header_elements(
        font_name=font_name,
        report_title="Customer Account Statement",
        report_subtitle=f"Generated on: {get_indian_current_time_str()}",
        extra_meta=meta_info
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=8.5,
        leading=10,
        textColor=colors.white,
    )

    header_center = ParagraphStyle(
        'HeaderCenter',
        parent=header_style,
        alignment=1,
    )

    header_right = ParagraphStyle(
        'HeaderRight',
        parent=header_style,
        alignment=2,
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0F172A'),
    )

    right_body = ParagraphStyle(
        'RightBody',
        parent=body_style,
        alignment=2,
    )

    center_body = ParagraphStyle(
        'CenterBody',
        parent=body_style,
        alignment=1,
    )

    summary_cards = build_summary_cards(
        [
            {'label': 'Opening Balance', 'value': f"₹{opening_balance:,.2f}", 'color': '#2563eb'},
            {'label': 'Period Sales', 'value': f"₹{total_sales:,.2f}", 'color': '#16665a'},
            {'label': 'Period Received', 'value': f"₹{total_received:,.2f}", 'color': '#059669'},
            {
                'label': 'Closing Balance',
                'value': f"₹{closing_balance:,.2f}",
                'color': '#dc2626' if closing_balance > 0 else '#059669',
                'sub': 'Amount Payable' if closing_balance > 0 else 'Settled / Advance',
            },
        ],
        font_name=font_name,
    )

    elements.append(summary_cards)
    elements.append(Spacer(1, 12))

    table_data = [
        [
            Paragraph('<b>Date</b>', header_style),
            Paragraph('<b>Type</b>', header_center),
            Paragraph('<b>Description</b>', header_style),
            Paragraph('<b>Destination</b>', header_style),
            Paragraph('<b>Debit (₹)</b>', header_right),
            Paragraph('<b>Credit (₹)</b>', header_right),
            Paragraph('<b>Balance (₹)</b>', header_right),
        ]
    ]

    for transaction in transactions:
        table_data.append([
            Paragraph(transaction['date'].strftime('%d-%b-%Y'), body_style),
            Paragraph(str(transaction['type']), center_body),
            # Payment rows: keep Description & Destination blank (clean ledger look)
            Paragraph('' if transaction['type'] == 'PAYMENT' else str(transaction['description']), body_style),
            Paragraph('' if transaction['type'] == 'PAYMENT' else str(transaction.get('destination') or '—'), body_style),
            Paragraph(f"₹{transaction['debit']:,.2f}" if transaction['debit'] else '-', right_body),
            Paragraph(f"₹{transaction['credit']:,.2f}" if transaction['credit'] else '-', right_body),
            Paragraph(f"₹{transaction['balance']:,.2f}", right_body),
        ])

    # TOTALS FOOTER ROW
    table_data.append([
        Paragraph('<b>TOTAL</b>', body_style),
        Paragraph('', center_body),
        Paragraph('', body_style),
        Paragraph('', body_style),
        Paragraph(f"<b>₹{total_sales:,.2f}</b>", right_body),
        Paragraph(f"<b>₹{total_received:,.2f}</b>", right_body),
        Paragraph(f"<b>₹{closing_balance:,.2f}</b>", right_body),
    ])

    statement_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[
            21 * mm,
            17 * mm,
            65 * mm,
            26 * mm,
            21 * mm,
            21 * mm,
            21 * mm,
        ]
    )

    apply_data_table_style(statement_table, total_row=True)

    elements.append(statement_table)
    elements.extend(build_thankyou_note(
        "Thank you for your business! For any queries regarding this statement, please contact us.",
        font_name=font_name,
    ))
    finish_document(document, elements, font_name=font_name)

    buffer.seek(0)

    response = HttpResponse(
        buffer,
        content_type='application/pdf'
    )

    filename = (
        f"customer_statement_"
        f"{customer.customer_code}.pdf"
    )

    disposition_type = 'inline' if request.GET.get('preview') == 'true' or request.GET.get('action') == 'preview' else 'attachment'
    response[
        'Content-Disposition'
    ] = f'{disposition_type}; filename="{filename}"'

    return response


@login_required(login_url='/login/')
def customer_record_payment(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    next_url = (
        get_safe_next(request, f"/ledger/customer/{customer.id}/")
        or f"/ledger/customer/{customer.id}/"
    )

    if request.method == 'POST':
        raw_amount = request.POST.get('amount', '').strip()
        trip_id = request.POST.get('trip_id', '').strip()
        raw_payment_date = request.POST.get('payment_date', '').strip()
        payment_method_id = request.POST.get('payment_method', '').strip()
        reference_number = request.POST.get('reference_number', '').strip()
        notes = request.POST.get('notes', '').strip()

        try:
            amount = Decimal(raw_amount)
            if amount <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            return redirect(next_url)

        if raw_payment_date:
            try:
                payment_date = datetime.strptime(raw_payment_date, '%Y-%m-%d').date()
            except ValueError:
                payment_date = timezone.localdate()
        else:
            payment_date = timezone.localdate()

        payment_method = None
        if payment_method_id:
            from master_data.models import PaymentMethod
            payment_method = PaymentMethod.objects.filter(
                pk=payment_method_id,
                is_active=True
            ).first()

        # Case 1: Specific Trip Selected
        if trip_id and trip_id.isdigit():
            trip = get_object_or_404(Trip, pk=int(trip_id), customer=customer)
            outstanding = trip.outstanding_amount
            pay_amount = min(amount, outstanding)
            if pay_amount > 0:
                TripPayment.objects.create(
                    trip=trip,
                    amount=pay_amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    notes=notes,
                )
        # Case 2: Lumpsum / Auto-allocate across pending trips (Oldest first)
        else:
            pending_trips = (
                Trip.objects.filter(customer=customer)
                .prefetch_related('payments')
                .order_by('trip_date', 'id')
            )

            remaining_to_allocate = amount
            for trip in pending_trips:
                if remaining_to_allocate <= 0:
                    break
                outstanding = trip.outstanding_amount
                if outstanding <= 0:
                    continue
                pay_amount = min(remaining_to_allocate, outstanding)
                TripPayment.objects.create(
                    trip=trip,
                    customer=None,
                    amount=pay_amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    notes=notes or "Customer lumpsum / on-account payment",
                )
                remaining_to_allocate -= pay_amount

            # If there is remaining payment (or 0 pending trips exist), record as direct customer payment against Opening Balance
            if remaining_to_allocate > 0:
                TripPayment.objects.create(
                    trip=None,
                    customer=customer,
                    amount=remaining_to_allocate,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    notes=notes or "Customer lumpsum / opening balance payment",
                )

        log_action(
            request,
            'PAYMENT_CREATE',
            model_name='Customer',
            object_repr=str(customer),
            details=f"Record Payment \u20B9{amount} | Date {payment_date} | "
                    f"{'Trip ' + trip_id if trip_id and trip_id.isdigit() else 'Lumpsum auto-allocate'}",
        )

        return redirect(next_url)

    return redirect(next_url)


@login_required(login_url='/login/')
def update_customer_opening_balance(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    next_url = (
        get_safe_next_or_referer(
            request,
            f"/ledger/customer/{customer.id}/",
        )
    )

    if not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, "Permission Denied: Only Admin users can edit the opening balance / outstanding amount.")
        return redirect(next_url)

    if request.method == 'POST':
        raw_balance = request.POST.get('opening_balance', '').strip()
        try:
            balance = Decimal(raw_balance)
            if balance < 0:
                balance = Decimal('0')
            old_balance = customer.opening_balance
            customer.opening_balance = balance
            customer.save()
            log_action(
                request,
                'OPENING_BALANCE_UPDATE',
                obj=customer,
                details=f"Opening balance changed \u20B9{old_balance} -> \u20B9{balance}",
            )
            from django.contrib import messages
            messages.success(request, f"Opening balance updated to ₹{balance:,.2f} successfully!")
        except (InvalidOperation, ValueError):
            from django.contrib import messages
            messages.error(request, "Invalid opening balance amount.")

    return redirect(next_url)