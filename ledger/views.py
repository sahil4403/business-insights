from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.utils import timezone

from django.db.models.functions import Coalesce
from django.db.models import Q
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

    context = {
        'customer': customer,
        'transactions': transactions,
        'total_sales': total_sales,
        'total_received': total_received,
        'opening_balance': opening_balance,
        'closing_balance': closing_balance,
        'from_date': from_date,
        'to_date': to_date,
        'unpaid_trips': unpaid_trips,
        'payment_methods': payment_methods,
        'is_admin_user': is_admin_user,
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
        previous_sales = customer_trips.filter(
            trip_date__lt=from_date
        )

        previous_payments = customer_payments.filter(
            effective_date__lt=from_date
        )

        opening_sales = sum(
            trip.total_amount
            for trip in previous_sales
        )

        opening_received = sum(
            payment.amount
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

    for trip in period_trips:
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
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()

    from core.pdf_utils import get_registered_font, build_pdf_header_elements, get_indian_current_time_str
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
        fontSize=8,
        leading=10,
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

    summary_data = [
        [
            Paragraph('<b>Opening Balance</b>', header_center),
            Paragraph('<b>Period Sales</b>', header_center),
            Paragraph('<b>Period Received</b>', header_center),
            Paragraph('<b>Closing Balance</b>', header_center),
        ],
        [
            Paragraph(f"<b>₹{opening_balance:,.2f}</b>", center_body),
            Paragraph(f"<b>₹{total_sales:,.2f}</b>", center_body),
            Paragraph(f"<b>₹{total_received:,.2f}</b>", center_body),
            Paragraph(f"<b>₹{closing_balance:,.2f}</b>", center_body),
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[46 * mm, 46 * mm, 46 * mm, 46 * mm]
    )

    summary_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F1F5F9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ])
    )

    elements.append(summary_table)
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
            Paragraph(str(transaction['description']), body_style),
            Paragraph(str(transaction.get('destination') or '—'), body_style),
            Paragraph(f"₹{transaction['debit']:,.2f}" if transaction['debit'] else '-', right_body),
            Paragraph(f"₹{transaction['credit']:,.2f}" if transaction['credit'] else '-', right_body),
            Paragraph(f"₹{transaction['balance']:,.2f}", right_body),
        ])

    statement_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[
            24 * mm,
            18 * mm,
            48 * mm,
            24 * mm,
            24 * mm,
            24 * mm,
            24 * mm,
        ]
    )

    statement_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ])
    )

    elements.append(statement_table)
    document.build(elements)

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
            customer.opening_balance = balance
            customer.save()
            from django.contrib import messages
            messages.success(request, f"Opening balance updated to ₹{balance:,.2f} successfully!")
        except (InvalidOperation, ValueError):
            from django.contrib import messages
            messages.error(request, "Invalid opening balance amount.")

    return redirect(next_url)