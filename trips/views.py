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
from core.audit import log_action

from master_data.models import Material, VehicleType
from vehicles.models import Vehicle
from labour.models import Labour
from customers.models import Customer
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
    elif category == 'jcb':
        trips = trips.filter(
            Q(vehicle__vehicle_type__code='JCB') |
            Q(vehicle__vehicle_type__name__iexact='Jcb') |
            Q(vehicle__registration_number__icontains='Jcb')
        )

    search = request.GET.get('search', '').strip()

    if search:
        trips = trips.filter(
            Q(trip_code__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(vehicle__registration_number__icontains=search) |
            Q(destination__icontains=search) |
            Q(drivers__name__icontains=search)
        ).distinct()

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

    vehicle_type_code = request.GET.get('vehicle', '').strip().upper()
    if vehicle_type_code:
        trips = trips.filter(
            Q(vehicle__vehicle_type__code=vehicle_type_code) |
            Q(vehicle__vehicle_type__name__iexact=vehicle_type_code) |
            Q(vehicle__registration_number__icontains=vehicle_type_code)
        )

    destination = request.GET.get('destination', '').strip()
    if destination:
        trips = trips.filter(destination__iexact=destination)

    driver_id = request.GET.get('driver', '').strip()
    if driver_id:
        trips = trips.filter(drivers__id=driver_id).distinct()

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

    vehicles_list = VehicleType.objects.filter(is_active=True).order_by('name')

    destinations_list = list(
        Trip.objects.exclude(destination__isnull=True)
        .exclude(destination='')
        .values_list('destination', flat=True)
        .distinct()
        .order_by('destination')
    )

    drivers_list = Labour.objects.filter(is_active=True).order_by('name')

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
        'selected_vehicle': vehicle_type_code,
        'vehicles_list': vehicles_list,
        'destinations_list': destinations_list,
        'selected_destination': destination,
        'drivers_list': drivers_list,
        'selected_driver': driver_id,
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

            # Inward (VENDOR_SUPPLY) → redirect to link customer page
            if trip.transaction_type == 'VENDOR_SUPPLY':
                return redirect('trips:link_customer', trip_id=trip.id)

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

            # Jahan se aaya tha (statement/detail) wahin wapas — ?next= chain
            nxt = request.POST.get('next') or request.GET.get('next')
            if nxt and nxt.startswith('/') and not nxt.startswith('//'):
                return redirect(nxt)

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

    from core.utils import get_safe_next, get_safe_next_or_referer
    from django.urls import reverse

    if request.method == 'POST':
        try:
            code = trip.trip_code
            deleted_amount = trip.total_amount
            trip.delete()
            log_action(
                request,
                'TRIP_DELETE',
                model_name='Trip',
                object_repr=code,
                details=f"Deleted trip of \u20B9{deleted_amount}",
            )
            messages.success(request, f"Trip {code} deleted successfully!")
            # Return to where the user came from (e.g. customer statement),
            # passed through the form's hidden 'next' field.
            target = get_safe_next(request, reverse('trips:list'))
            # Never return to the pages of the trip we just deleted
            if f"/trips/{trip_id}/" in target or f"/trips/{trip_id}/" in target + "/":
                target = reverse('trips:list')
            return redirect(target)
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

    # Where the user came from (statement / trip detail), for Cancel + post-delete return
    back_url = get_safe_next_or_referer(request, reverse('trips:list'))

    context = {
        'trip': trip,
        'back_url': back_url,
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
            log_action(
                request,
                'PAYMENT_CREATE',
                obj=form.instance,
                details=f"Trip {trip.trip_code} | Amount \u20B9{form.instance.amount} | Date {form.instance.payment_date}",
            )
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
            log_action(
                request,
                'PAYMENT_EDIT',
                obj=form.instance,
                details=f"Trip {trip.trip_code if trip else '-'} | Amount \u20B9{form.instance.amount} | Date {form.instance.payment_date}",
            )
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
        deleted_amount = payment.amount
        payment.delete()
        log_action(
            request,
            'PAYMENT_DELETE',
            model_name='TripPayment',
            object_repr=f"{payment.payment_code or ''} {deleted_amount}".strip(),
            details=f"Deleted payment of \u20B9{deleted_amount} (trip {trip.trip_code if trip else '-'})",
        )
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

    from core.utils import get_safe_next_or_referer
    from django.urls import reverse

    # Smart back: return to where the user came from (e.g. customer statement),
    # falling back to the trips list only when there is no internal referrer.
    back_url = get_safe_next_or_referer(
        request,
        reverse('trips:list'),
    )

    context = {
        'trip': trip,
        'payments': trip.payments.all(),
        'back_url': back_url,
    }

    return render(
        request,
        'trips/trip_detail.html',
        context
    )

@login_required(login_url='/login/')
def trip_link_customer(request, trip_id):
    """
    Inward (VENDOR_SUPPLY) trip se Outward (Customer Delivery) trip create karta hai.
    Sirf VENDOR_SUPPLY trips ke liye available.
    """
    from decimal import Decimal, InvalidOperation

    trip = get_object_or_404(Trip, pk=trip_id)

    if trip.transaction_type != 'VENDOR_SUPPLY':
        messages.error(request, "Sirf Inward (Vendor Supply) trips customer se link ho sakti hain.")
        return redirect('trips:detail', trip_id=trip.id)

    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        rate_str = request.POST.get('rate', '').strip()

        if not customer_id or not rate_str:
            messages.error(request, "Customer aur Rate dono required hain.")
            return redirect('trips:link_customer', trip_id=trip.id)

        try:
            rate_val = Decimal(rate_str)
            if rate_val <= 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            messages.error(request, "Rate valid positive number hona chahiye.")
            return redirect('trips:link_customer', trip_id=trip.id)

        customer = get_object_or_404(Customer, pk=customer_id, is_active=True)

        # Outward trip create
        outward = Trip(
            transaction_type='CUSTOMER_DELIVERY',
            customer=customer,
            material=trip.material,
            quantity=trip.quantity,
            rate=rate_val,
            vehicle=trip.vehicle,
            destination=trip.destination,
            trip_date=trip.trip_date,
            driver_bhatta=Decimal('0.00'),  # sale amount pure
            notes=f"Outward sale of inward {trip.trip_code}",
            linked_inward_trip=trip,
        )
        outward.save()
        # Copy drivers and their trip counts
        outward.drivers.set(trip.drivers.all())
        outward.driver_trip_counts = trip.driver_trip_counts
        outward.save(update_fields=['driver_trip_counts'])

        messages.success(request, f"Outward trip {outward.trip_code} created for {customer.name}!")
        return redirect('ledger:customer_statement', customer_id=customer.id)

    # GET: form
    customers = Customer.objects.filter(is_active=True).order_by('name')
    default_rate = round((trip.total_amount or 0) / (trip.quantity or 1), 2)

    context = {
        'inward': trip,
        'customers': customers,
        'default_rate': default_rate,
    }
    return render(request, 'trips/trip_link_customer.html', context)


@login_required(login_url='/login/')
def trip_link_customer(request, trip_id):
    """
    Inward (VENDOR_SUPPLY) trip se Outward (Customer Delivery) trip create karta hai.
    Sirf VENDOR_SUPPLY trips ke liye available.
    """
    from decimal import Decimal, InvalidOperation

    trip = get_object_or_404(Trip, pk=trip_id)

    if trip.transaction_type != 'VENDOR_SUPPLY':
        messages.error(request, "Sirf Inward (Vendor Supply) trips customer se link ho sakti hain.")
        return redirect('trips:detail', trip_id=trip.id)

    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        rate_str = request.POST.get('rate', '').strip()

        if not customer_id or not rate_str:
            messages.error(request, "Customer aur Rate dono required hain.")
            return redirect('trips:link_customer', trip_id=trip.id)

        try:
            rate_val = Decimal(rate_str)
            if rate_val <= 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            messages.error(request, "Rate valid positive number hona chahiye.")
            return redirect('trips:link_customer', trip_id=trip.id)

        customer = get_object_or_404(Customer, pk=customer_id, is_active=True)

        # Outward trip create
        outward = Trip(
            transaction_type='CUSTOMER_DELIVERY',
            customer=customer,
            material=trip.material,
            quantity=trip.quantity,
            rate=rate_val,
            vehicle=trip.vehicle,
            destination=trip.destination,
            trip_date=trip.trip_date,
            driver_bhatta=Decimal('0.00'),  # sale amount pure
            notes=f"Outward sale of inward {trip.trip_code}",
            linked_inward_trip=trip,
        )
        outward.save()
        # Copy drivers and their trip counts
        outward.drivers.set(trip.drivers.all())
        outward.driver_trip_counts = trip.driver_trip_counts
        outward.save(update_fields=['driver_trip_counts'])

        messages.success(request, f"Outward trip {outward.trip_code} created for {customer.name}!")
        return redirect('ledger:customer_statement', customer_id=customer.id)

    # GET: form
    customers = Customer.objects.filter(is_active=True).order_by('name')
    default_rate = round((trip.total_amount or 0) / (trip.quantity or 1), 2)

    context = {
        'inward': trip,
        'customers': customers,
        'default_rate': default_rate,
    }
    return render(request, 'trips/trip_link_customer.html', context)


@login_required(login_url='/login/')
def trip_quickfill(request):
    from django.http import JsonResponse

    customer_id = request.GET.get('customer', '').strip()
    material_id = request.GET.get('material', '').strip()

    if not customer_id.isdigit():
        return JsonResponse({'found': False})

    qs = Trip.objects.filter(customer_id=int(customer_id))

    if material_id.isdigit():
        match = (
            qs.filter(material_id=int(material_id))
            .order_by('-trip_date', '-id')
            .values('rate', 'quantity', 'vehicle_id', 'destination')
            .first()
        )
        if match:
            return JsonResponse({'found': True, 'matched_on': 'material', **match})

    last_any = (
        qs.order_by('-trip_date', '-id')
        .values('rate', 'quantity', 'vehicle_id', 'destination', 'material_id')
        .first()
    )
    if last_any:
        return JsonResponse({'found': True, 'matched_on': 'customer', **last_any})

    return JsonResponse({'found': False})
