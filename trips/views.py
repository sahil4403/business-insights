from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.db.models.functions import ExtractYear, Coalesce
from django.db.models import (
    Case,
    CharField,
    DecimalField,
    F,
    Q,
    Sum,
    Value,
    When,
)
from decimal import Decimal
from .models import Trip, TripPayment
from .forms import TripForm, TripPaymentForm

from master_data.models import Material
from core.utils import get_safe_next

@login_required(login_url='/login/')
def trip_list(request):
    trips = Trip.objects.select_related(
        'customer',
        'vehicle',
        'material',
    ).prefetch_related(
        'drivers',
        'payments',
    ).annotate(
        calculated_received=Coalesce(
            Sum('payments__amount'),
            Value(Decimal('0')),
            output_field=DecimalField(max_digits=15, decimal_places=2),
        ),
    ).annotate(
        calculated_status=Case(
            When(
                Q(calculated_received__isnull=True) | Q(calculated_received__lte=0),
                then=Value('UNPAID'),
            ),
            When(
                calculated_received__lt=F('total_amount'),
                then=Value('PARTIAL'),
            ),
            default=Value('PAID'),
            output_field=CharField(),
        ),
    )

    category = request.GET.get('category', '').strip().lower()

    if category == 'tractor':
        trips = trips.filter(
            Q(vehicle__vehicle_type__code='TRACTOR') |
            Q(vehicle__vehicle_type__name__iexact='Tractor') |
            Q(vehicle__registration_number__icontains='Tractor')
        )
    elif category == 'halfton':
        trips = trips.filter(
            Q(vehicle__vehicle_type__code='HALFTON') |
            Q(vehicle__vehicle_type__name__iexact='Halfton') |
            Q(vehicle__registration_number__icontains='Halfton')
        )
    elif category == 'hyva':
        trips = trips.filter(
            Q(vehicle__vehicle_type__code='HYVA') |
            Q(vehicle__vehicle_type__name__iexact='Hyva') |
            Q(vehicle__registration_number__icontains='Hyva')
        )

    search = request.GET.get('search', '').strip()

    if search:
        trips = trips.filter(
            trip_code__icontains=search
        ) | trips.filter(
            customer__name__icontains=search
        ) | trips.filter(
            vehicle__registration_number__icontains=search
        )

    trip_status = request.GET.get('trip_status', '')

    if trip_status:
        trips = trips.filter(
            trip_status=trip_status
        )

    payment_status = request.GET.get(
        'payment_status',
        ''
    )

    if payment_status:
        trips = trips.filter(
            calculated_status=payment_status
        )

    material_id = request.GET.get('material', '').strip()
    if material_id:
        trips = trips.filter(material_id=material_id)

    transaction_type = request.GET.get('transaction_type', 'CUSTOMER_DELIVERY').strip()

    if transaction_type == 'CUSTOMER_DELIVERY':
        trips = trips.filter(transaction_type='CUSTOMER_DELIVERY')
    elif transaction_type == 'INTERNAL_STOCK':
        trips = trips.filter(transaction_type='INTERNAL_STOCK')
    elif transaction_type == 'ALL':
        pass
    else:
        transaction_type = 'CUSTOMER_DELIVERY'
        trips = trips.filter(transaction_type='CUSTOMER_DELIVERY')

    year = request.GET.get('year', '').strip()
    month = request.GET.get('month', '').strip()
    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()

    if year:
        trips = trips.filter(trip_date__year=int(year))
    if month:
        trips = trips.filter(trip_date__month=int(month))
    if from_date:
        trips = trips.filter(trip_date__gte=from_date)
    if to_date:
        trips = trips.filter(trip_date__lte=to_date)

    materials_list = Material.objects.filter(is_active=True).order_by('name')

    available_years = list(
        Trip.objects.annotate(y=ExtractYear('trip_date'))
        .values_list('y', flat=True)
        .distinct()
        .order_by('-y')
    )
    current_year = timezone.localdate().year
    if current_year not in available_years:
        available_years.insert(0, current_year)

    month_choices = [
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ]

    trips_list = list(trips)
    summary = {
        'total_count': int(sum((t.quantity or 0) for t in trips_list)) if trips_list else 0,
        'total_revenue': sum(t.total_amount for t in trips_list) if trips_list else Decimal('0'),
        'total_received': sum((t.calculated_received or Decimal('0')) for t in trips_list) if trips_list else Decimal('0'),
        'total_pending': sum((t.outstanding_amount or Decimal('0')) for t in trips_list) if trips_list else Decimal('0'),
        'paid_count': int(sum((t.quantity or 0) for t in trips_list if t.calculated_status == 'PAID')),
        'pending_count': int(sum((t.quantity or 0) for t in trips_list if t.calculated_status in ['UNPAID', 'PARTIAL'])),
    }

    context = {
        'trips': trips_list,
        'summary': summary,
        'search': search,
        'selected_trip_status': trip_status,
        'selected_payment_status': payment_status,
        'selected_transaction_type': transaction_type,
        'selected_material': material_id,
        'materials_list': materials_list,
        'selected_year': year,
        'selected_month': month,
        'from_date': from_date,
        'to_date': to_date,
        'available_years': available_years,
        'month_choices': month_choices,
        'trip_status_choices': Trip.TRIP_STATUS_CHOICES,
        'payment_status_choices': Trip.PAYMENT_STATUS_CHOICES,
        'category': category,
    }

    return render(
        request,
        'trips/trip_list.html',
        context
    )
from django.contrib import messages

@login_required(login_url='/login/')
def trip_create(request):
    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            trip = form.save()

            # Save driver trip counts breakdown
            driver_counts = {}
            for d in trip.drivers.all():
                param_name = f'driver_count_{d.id}'
                if param_name in request.POST:
                    val = request.POST.get(param_name, '').strip()
                    if val:
                        try:
                            driver_counts[str(d.id)] = float(val) if '.' in val else int(val)
                        except ValueError:
                            pass
            trip.driver_trip_counts = driver_counts
            trip.save(update_fields=['driver_trip_counts'])

            messages.success(request, f"Trip {trip.trip_code} created successfully!")

            if request.POST.get('save_and_view_statement') == '1' and trip.customer:
                return redirect('ledger:customer_statement', customer_id=trip.customer.id)

            return redirect(
                'trips:detail',
                trip_id=trip.id
            )
        else:
            err_list = [f"{field}: {', '.join(errs)}" for field, errs in form.errors.items()]
            messages.error(request, f"Failed to create trip: {'; '.join(err_list)}")
    else:
        form = TripForm()

    context = {
        'form': form,
        'page_title': 'Add Trip',
    }

    return render(
        request,
        'trips/trip_create.html',
        context
    )

@login_required(login_url='/login/')
def trip_edit(request, trip_id):
    trip = get_object_or_404(
        Trip,
        pk=trip_id
    )

    if request.method == 'POST':
        form = TripForm(
            request.POST,
            instance=trip
        )
        if form.is_valid():
            trip = form.save()

            # Save driver trip counts breakdown
            driver_counts = {}
            for d in trip.drivers.all():
                param_name = f'driver_count_{d.id}'
                if param_name in request.POST:
                    val = request.POST.get(param_name, '').strip()
                    if val:
                        try:
                            driver_counts[str(d.id)] = float(val) if '.' in val else int(val)
                        except ValueError:
                            pass
            trip.driver_trip_counts = driver_counts
            trip.save(update_fields=['driver_trip_counts'])

            messages.success(request, f"Trip {trip.trip_code} updated successfully!")

            if request.POST.get('save_and_view_statement') == '1' and trip.customer:
                return redirect('ledger:customer_statement', customer_id=trip.customer.id)

            return redirect(
                'trips:detail',
                trip_id=trip.id
            )
        else:
            err_list = [f"{field}: {', '.join(errs)}" for field, errs in form.errors.items()]
            messages.error(request, f"Failed to update trip: {'; '.join(err_list)}")
    else:
        form = TripForm(
            instance=trip
        )

    context = {
        'form': form,
        'trip': trip,
        'page_title': 'Edit Trip',
    }

    return render(
        request,
        'trips/trip_edit.html',
        context
    )

@login_required(login_url='/login/')
def trip_delete(request, trip_id):

    trip = get_object_or_404(
        Trip,
        pk=trip_id
    )

    if request.method == 'POST':
        try:
            code = trip.trip_code
            trip.delete()
            messages.success(request, f"Trip {code} deleted successfully!")
            return redirect('trips:list')
        except ProtectedError:
            context = {
                'trip': trip,
                'delete_error': (
                    'This trip cannot be deleted because '
                    'expenses or other records are linked to it.'
                ),
            }
            return render(
                request,
                'trips/trip_delete.html',
                context
            )

    context = {
        'trip': trip,
    }

    return render(
        request,
        'trips/trip_delete.html',
        context
    )


@login_required(login_url='/login/')
def trip_payment_create(request, trip_id):
    trip = get_object_or_404(
        Trip,
        pk=trip_id
    )
    next_url = get_safe_next(request, f'/trips/{trip.id}/')

    if request.method == 'POST':
        payment_instance = TripPayment(
            trip=trip
        )
        form = TripPaymentForm(
            request.POST,
            instance=payment_instance,
            trip=trip
        )
        if form.is_valid():
            form.save()
            messages.success(request, f"Payment of ₹{payment_instance.amount} added to trip {trip.trip_code}!")
            if next_url:
                return redirect(next_url)
            return redirect(
                'trips:detail',
                trip_id=trip.id
            )
    else:
        payment_instance = TripPayment(
            trip=trip
        )
        form = TripPaymentForm(
            instance=payment_instance,
            trip=trip
        )

    context = {
        'form': form,
        'trip': trip,
        'next_url': next_url,
    }
    return render(
        request,
        'trips/trip_payment_create.html',
        context
    )

@login_required(login_url='/login/')
def trip_payment_edit(request, payment_id):
    payment = get_object_or_404(
        TripPayment.objects.select_related('trip', 'customer'),
        pk=payment_id
    )
    trip = payment.trip
    next_url = get_safe_next(
        request,
        f'/trips/{trip.id}/' if trip else '/trips/',
    )

    if request.method == 'POST':
        form = TripPaymentForm(
            request.POST,
            instance=payment,
            trip=trip
        )
        if form.is_valid():
            form.save()
            messages.success(request, f"Payment updated successfully!")
            if next_url:
                return redirect(next_url)
            if trip:
                return redirect('trips:detail', trip_id=trip.id)
            elif payment.customer:
                return redirect('ledger:customer_statement', customer_id=payment.customer.id)
            return redirect('trips:list')
    else:
        form = TripPaymentForm(
            instance=payment,
            trip=trip
        )

    context = {
        'form': form,
        'trip': trip,
        'payment': payment,
        'page_title': 'Edit Payment',
        'next_url': next_url,
    }
    return render(
        request,
        'trips/trip_payment_edit.html',
        context
    )

@login_required(login_url='/login/')
def trip_payment_delete(request, payment_id):
    payment = get_object_or_404(
        TripPayment.objects.select_related('trip', 'customer'),
        pk=payment_id
    )
    trip = payment.trip
    next_url = get_safe_next(
        request,
        f'/trips/{trip.id}/' if trip else '/trips/',
    )

    if request.method == 'POST':
        customer = payment.customer
        payment.delete()
        messages.success(request, f"Payment removed successfully!")
        if next_url:
            return redirect(next_url)
        if trip:
            return redirect('trips:detail', trip_id=trip.id)
        elif customer:
            return redirect('ledger:customer_statement', customer_id=customer.id)
        return redirect('trips:list')

    context = {
        'payment': payment,
        'trip': trip,
        'next_url': next_url,
    }
    return render(
        request,
        'trips/trip_payment_delete.html',
        context
    )

@login_required(login_url='/login/')
def trip_detail(request, trip_id):

    trip = get_object_or_404(
        Trip.objects.select_related(
            'customer',
            'vehicle',
            'material',
        ).prefetch_related(
            'drivers',
            'payments__payment_method',
        ),
        pk=trip_id,
    )

    context = {
        'trip': trip,
        'payments': trip.payments.all(),
    }

    return render(
        request,
        'trips/trip_detail.html',
        context
    )