from datetime import date

from django.contrib.auth.decorators import login_required

from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Expense
from master_data.models import ExpenseCategory, PaymentMethod
from vehicles.models import Vehicle
from labour.models import Labour
from trips.models import Trip
from .forms import ExpenseForm

@login_required(login_url='/login/')
def expense_dashboard(request):
    today = timezone.localdate()

    # -----------------------------------
    # BASE QUERYSET
    # -----------------------------------

    expenses = Expense.objects.select_related(
        'category',
        'payment_method',
        'vehicle',
        'labour',
    )

    # -----------------------------------
    # FILTER VALUES
    # -----------------------------------

    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')
    category_id = request.GET.get('category', '')
    payment_method_id = request.GET.get('payment_method', '')
    vehicle_id = request.GET.get('vehicle', '')
    labour_id = request.GET.get('labour', '')

    # -----------------------------------
    # APPLY DATE FILTER
    # -----------------------------------

    if from_date:
        expenses = expenses.filter(
            expense_date__gte=from_date
        )

    if to_date:
        expenses = expenses.filter(
            expense_date__lte=to_date
        )

    # -----------------------------------
    # APPLY CATEGORY FILTER
    # -----------------------------------

    if category_id:
        expenses = expenses.filter(
            category_id=category_id
        )

    # -----------------------------------
    # APPLY PAYMENT METHOD FILTER
    # -----------------------------------

    if payment_method_id:
        expenses = expenses.filter(
            payment_method_id=payment_method_id
        )

    # -----------------------------------
    # APPLY VEHICLE FILTER
    # -----------------------------------

    if vehicle_id:
        expenses = expenses.filter(
            vehicle_id=vehicle_id
        )

    # -----------------------------------
    # APPLY LABOUR FILTER
    # -----------------------------------

    if labour_id:
        expenses = expenses.filter(
            labour_id=labour_id
        )

    # -----------------------------------
    # TOTAL EXPENSE
    # -----------------------------------

    total_expense = (
        expenses.aggregate(
            total=Sum('amount')
        )['total']
        or 0
    )

    # -----------------------------------
    # THIS MONTH
    # -----------------------------------

    this_month_expense = expenses.filter(
        expense_date__year=today.year,
        expense_date__month=today.month,
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # -----------------------------------
    # DIESEL / FUEL
    # -----------------------------------

    diesel_fuel = expenses.filter(
        category__name__in=[
            'Diesel / Fuel',
            'Black Diesel',
            'Fuel',
        ]
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # -----------------------------------
    # LABOUR
    # -----------------------------------

    labour_expense = expenses.filter(
        category__name='Labour'
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # -----------------------------------
    # VEHICLE RELATED
    # -----------------------------------

    vehicle_expense = expenses.filter(
        category__name__in=[
            'Vehicle Maintenance',
            'Vehicle Repair',
        ]
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # -----------------------------------
    # CATEGORY-WISE EXPENSE
    # -----------------------------------

    category_expenses = list(
        expenses
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    for item in category_expenses:

        if total_expense:
            item['percentage'] = round(
                float(item['total'])
                / float(total_expense)
                * 100,
                1
            )
        else:
            item['percentage'] = 0

    # -----------------------------------
    # MONTHLY EXPENSE
    # LAST 6 MONTHS
    # -----------------------------------

    monthly_expenses = []

    for i in range(5, -1, -1):

        month = today.month - i
        year = today.year

        while month <= 0:
            month += 12
            year -= 1

        total = (
            expenses.filter(
                expense_date__year=year,
                expense_date__month=month,
            ).aggregate(
                total=Sum('amount')
            )['total']
            or 0
        )

        month_name = date(
            year,
            month,
            1
        ).strftime('%b %Y')

        monthly_expenses.append({
            'month': month_name,
            'total': total,
        })

    max_monthly_expense = max(
        [
            float(item['total'])
            for item in monthly_expenses
        ],
        default=0
    )

    for item in monthly_expenses:

        if max_monthly_expense:
            item['percentage'] = round(
                float(item['total'])
                / max_monthly_expense
                * 100,
                1
            )
        else:
            item['percentage'] = 0

    # -----------------------------------
    # VEHICLE-WISE EXPENSE
    # -----------------------------------

    vehicle_expenses = list(
        expenses
        .filter(vehicle__isnull=False)
        .values(
            'vehicle_id',
            'vehicle__registration_number',
        )
        .annotate(
            total=Sum('amount')
        )
        .order_by('-total')
    )

    max_vehicle_expense = max(
        [
            float(item['total'])
            for item in vehicle_expenses
        ],
        default=0
    )

    for item in vehicle_expenses:

        if max_vehicle_expense:
            item['percentage'] = round(
                float(item['total'])
                / max_vehicle_expense
                * 100,
                1
            )
        else:
            item['percentage'] = 0

    # -----------------------------------
    # PAYMENT METHOD-WISE EXPENSE
    # -----------------------------------

    payment_expenses = list(
        expenses
        .values('payment_method__name')
        .annotate(
            total=Sum('amount')
        )
        .order_by('-total')
    )

    for item in payment_expenses:

        if total_expense:
            item['percentage'] = round(
                float(item['total'])
                / float(total_expense)
                * 100,
                1
            )
        else:
            item['percentage'] = 0

    # -----------------------------------
    # TRIP-WISE EXPENSE & PROFITABILITY
    # -----------------------------------

    # -----------------------------------
    # TRIP-WISE EXPENSE & PROFITABILITY
    # -----------------------------------

    # -----------------------------------
    # TRIP-WISE EXPENSE & PROFITABILITY
    # ALL TRIPS
    # -----------------------------------

    # Start with all trips
    trips = Trip.objects.select_related(
        'vehicle'
    ).all()

    # Date filter applies to trip date
    if from_date:
        trips = trips.filter(
            trip_date__gte=from_date
        )

    if to_date:
        trips = trips.filter(
            trip_date__lte=to_date
        )

    # Vehicle filter applies to trip vehicle
    if vehicle_id:
        trips = trips.filter(
            vehicle_id=vehicle_id
        )

    trips = trips.order_by(
        '-trip_date',
        '-id'
    )

    # Create expense totals from the already filtered
    # expense queryset.
    filtered_trip_expenses = (
        expenses
        .filter(trip__isnull=False)
        .values('trip_id')
        .annotate(
            expense_total=Sum('amount')
        )
    )

    expense_by_trip = {
        item['trip_id']: item['expense_total']
        for item in filtered_trip_expenses
    }

    trip_expenses = []

    for trip in trips:

        expense_total = (
                expense_by_trip.get(trip.id)
                or 0
        )

        revenue = trip.total_amount or 0

        profit = (
                revenue - expense_total
        )

        if revenue > 0:

            profit_percentage = round(
                (
                        profit / revenue
                ) * 100,
                1
            )

        else:

            profit_percentage = 0

        trip_expenses.append({
            'trip_id': trip.id,
            'trip__trip_code': trip.trip_code,
            'trip__trip_date': trip.trip_date,
            'trip__total_amount': revenue,
            'trip__vehicle__registration_number': (
                trip.vehicle.registration_number
                if trip.vehicle
                else '—'
            ),
            'expense_total': expense_total,
            'profit': profit,
            'profit_percentage': profit_percentage,
        })
    # -----------------------------------
    # TRIP PROFITABILITY SUMMARY
    # -----------------------------------

    total_trip_revenue = sum(
        float(item['trip__total_amount'] or 0)
        for item in trip_expenses
    )

    total_trip_expense = sum(
        float(item['expense_total'] or 0)
        for item in trip_expenses
    )

    total_trip_profit = (
        total_trip_revenue
        - total_trip_expense
    )

    if total_trip_revenue > 0:

        overall_profit_margin = round(
            (
                total_trip_profit
                / total_trip_revenue
            ) * 100,
            1
        )

    else:

        overall_profit_margin = 0

    # -----------------------------------
    # BUSINESS REVENUE VS EXPENSE
    # -----------------------------------

    total_revenue = sum(
        float(item['trip__total_amount'] or 0)
        for item in trip_expenses
    )

    total_business_expense = float(
        total_expense or 0
    )

    total_profit_expense = float(
        expenses
        .filter(include_in_profit=True)
        .aggregate(
            total=Sum('amount')
        )['total'] or 0
    )

    net_profit = (
            total_revenue
            - total_profit_expense
    )

    if total_revenue > 0:

        net_profit_margin = round(
            (
                    net_profit
                    / total_revenue
            ) * 100,
            1
        )

    else:

        net_profit_margin = 0



    # -----------------------------------
    # MONTHLY BUSINESS PERFORMANCE
    # -----------------------------------

    monthly_business = []

    for i in range(5, -1, -1):

        month = today.month - i
        year = today.year

        while month <= 0:
            month += 12
            year -= 1

        # Revenue from trips
        month_trips = Trip.objects.filter(
            trip_date__year=year,
            trip_date__month=month,
        )

        if from_date:
            month_trips = month_trips.filter(
                trip_date__gte=from_date
            )

        if to_date:
            month_trips = month_trips.filter(
                trip_date__lte=to_date
            )

        if vehicle_id:
            month_trips = month_trips.filter(
                vehicle_id=vehicle_id
            )

        month_revenue = (
            month_trips.aggregate(
                total=Sum('total_amount')
            )['total'] or 0
        )

        # Included expenses only
        month_expenses = expenses.filter(
            expense_date__year=year,
            expense_date__month=month,
            include_in_profit=True,
        )

        month_expense = (
            month_expenses.aggregate(
                total=Sum('amount')
            )['total'] or 0
        )

        month_profit = (
            month_revenue - month_expense
        )

        if month_revenue:

            month_margin = round(
                (
                    float(month_profit)
                    / float(month_revenue)
                ) * 100,
                1
            )

        else:

            month_margin = 0

        monthly_business.append({
            'month': date(
                year,
                month,
                1
            ).strftime('%b %Y'),

            'revenue': month_revenue,
            'expense': month_expense,
            'profit': month_profit,
            'margin': month_margin,
        })

    # -----------------------------------
    # RECENT EXPENSES
    # -----------------------------------

    recent_expenses = expenses.order_by(
        '-expense_date',
        '-id',
    )[:10]

    # -----------------------------------
    # FILTER OPTIONS
    # -----------------------------------

    categories = ExpenseCategory.objects.filter(
        is_active=True
    ).order_by('name')

    payment_methods = PaymentMethod.objects.filter(
        is_active=True
    ).order_by('name')

    vehicles = Vehicle.objects.order_by(
        'registration_number'
    )

    labours = Labour.objects.order_by(
        'name'
    )

    # -----------------------------------
    # CONTEXT
    # -----------------------------------

    context = {


        'total_expense': total_expense,
        'this_month': this_month_expense,
        'diesel_fuel': diesel_fuel,
        'labour_expense': labour_expense,
        'vehicle_expense': vehicle_expense,

        'category_expenses': category_expenses,
        'monthly_expenses': monthly_expenses,
        'monthly_business': monthly_business,
        'vehicle_expenses': vehicle_expenses,
        'payment_expenses': payment_expenses,
        'trip_expenses': trip_expenses,

        'total_trip_revenue': total_trip_revenue,
        'total_trip_expense': total_trip_expense,
        'total_trip_profit': total_trip_profit,
        'overall_profit_margin': overall_profit_margin,

        'total_revenue': total_revenue,
        'total_profit_expense': total_profit_expense,
        'total_business_expense': total_business_expense,
        'net_profit': net_profit,
        'net_profit_margin': net_profit_margin,

        'recent_expenses': recent_expenses,
        'categories': categories,
        'payment_methods': payment_methods,
        'vehicles': vehicles,
        'labours': labours,

        'from_date': from_date,
        'to_date': to_date,
        'selected_category': category_id,
        'selected_payment_method': payment_method_id,
        'selected_vehicle': vehicle_id,
        'selected_labour': labour_id,

    }



    return render(
        request,
        'expenses/dashboard.html',
        context,
    )

@login_required(login_url='/login/')
def expense_create(request):

    if request.method == 'POST':
        form = ExpenseForm(request.POST)

        if form.is_valid():
            form.save()

            return redirect(
                'expenses:dashboard'
            )

    else:
        form = ExpenseForm()

    context = {
        'form': form,
        'page_title': 'Add Expense',
    }

    return render(
        request,
        'expenses/expense_create.html',
        context
    )

@login_required(login_url='/login/')
def expense_list(request):

    expenses = Expense.objects.select_related(
        'category',
        'payment_method',
        'vehicle',
        'trip',
        'labour',
    ).order_by(
        '-expense_date',
        '-id',
    )

    context = {
        'expenses': expenses,
    }

    return render(
        request,
        'expenses/expense_list.html',
        context
    )

@login_required(login_url='/login/')
def expense_edit(request, expense_id):

    expense = get_object_or_404(
        Expense,
        pk=expense_id
    )

    if request.method == 'POST':
        form = ExpenseForm(
            request.POST,
            instance=expense
        )

        if form.is_valid():
            form.save()

            return redirect(
                'expenses:list'
            )

    else:
        form = ExpenseForm(
            instance=expense
        )

    context = {
        'form': form,
        'expense': expense,
        'page_title': 'Edit Expense',
    }

    return render(
        request,
        'expenses/expense_edit.html',
        context
    )

@login_required(login_url='/login/')
def expense_delete(request, expense_id):

    expense = get_object_or_404(
        Expense,
        pk=expense_id
    )

    if request.method == 'POST':
        expense.delete()

        return redirect(
            'expenses:list'
        )

    context = {
        'expense': expense,
    }

    return render(
        request,
        'expenses/expense_delete.html',
        context
    )