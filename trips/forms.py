from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum, Q

from .models import Trip, TripPayment
from master_data.models import PaymentMethod, Material
from customers.models import Customer
from vehicles.models import Vehicle
from labour.models import Labour



class TripAdminForm(forms.ModelForm):

    class Meta:
        model = Trip
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['quantity'].label = 'Quantity (Trips / Pieces)'

        self.fields['quantity'].help_text = (
            'Enter number of trips for trip-based material '
            'or number of pieces for piece-based material.'
        )

class LabourChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class TripForm(forms.ModelForm):
    VEHICLE_CATEGORY_CHOICES = [
        ('HYVA', 'Hyva'),
        ('TRACTOR', 'Tractor'),
        ('HALFTON', 'Halfton'),
        ('JCB', 'JCB'),
    ]

    vehicle_category = forms.ChoiceField(
        choices=VEHICLE_CATEGORY_CHOICES,
        label="Vehicle Type / Category",
        initial='HYVA',
        required=False
    )

    drivers = LabourChoiceField(
        queryset=Labour.objects.none(),
        widget=forms.SelectMultiple(
            attrs={
                'class': 'drivers-select-dropdown',
                'style': 'width: 100%; padding: 11px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; background: white; min-height: 120px;',
            }
        ),
        required=False,
        label="Drivers / Labour Assigned"
    )

    class Meta:
        model = Trip

        fields = [
            'trip_date',
            'transaction_type',
            'customer',
            'destination',
            'vehicle',
            'material',
            'drivers',
            'quantity',
            'rate',
            'start_reading',
            'end_reading',
            'total_hours',
            'driver_bhatta',
            'trip_status',
            'notes',
        ]

        widgets = {
            'trip_date': forms.DateInput(
                attrs={
                    'type': 'date',
                }
            ),

            'destination': forms.TextInput(
                attrs={
                    'placeholder': 'Enter destination',
                }
            ),

            'quantity': forms.NumberInput(
                attrs={
                    'step': '0.01',
                    'min': '0.01',
                }
            ),

            'rate': forms.NumberInput(
                attrs={
                    'step': '0.01',
                    'min': '0',
                    'placeholder': 'Per hour / trip rate',
                }
            ),

            'start_reading': forms.NumberInput(
                attrs={
                    'step': '0.1',
                    'placeholder': 'e.g. 1233.2',
                }
            ),

            'end_reading': forms.NumberInput(
                attrs={
                    'step': '0.1',
                    'placeholder': 'e.g. 1235.1',
                }
            ),

            'total_hours': forms.NumberInput(
                attrs={
                    'step': '0.1',
                    'placeholder': 'Auto calculated (e.g. 1.9)',
                }
            ),

            'driver_bhatta': forms.NumberInput(
                attrs={
                    'step': '0.01',
                    'placeholder': '200.00',
                }
            ),

            'notes': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Optional notes',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['trip_status'].initial = 'COMPLETED'
        current_status = self.instance.trip_status if self.instance and self.instance.pk else None
        if current_status and current_status != 'COMPLETED':
            self.fields['trip_status'].choices = [
                ('COMPLETED', 'Completed'),
                (current_status, dict(Trip.TRIP_STATUS_CHOICES).get(current_status, current_status)),
            ]
        else:
            self.fields['trip_status'].choices = [('COMPLETED', 'Completed')]

        self.fields['transaction_type'].label = "Trip Category / Type"
        self.fields['customer'].required = False

        customer_qs = Customer.objects.filter(is_active=True)
        vehicle_qs = Vehicle.objects.filter(is_active=True, status='ACTIVE')
        material_qs = Material.objects.filter(is_active=True)
        
        target_driver_names = ['Gaju Bhau', 'Dinesh Bhaiya', 'Santosh Bhaiya', 'Ankush Bhau', 'Kishan Bhau', 'Shubham Bhau']

        # Nitin Prasad: SIRF Crushed Stone material par Driver Allocation me
        # (naam ka koi bhi variant chale — case/spacing flexible)
        current_material_name = ''
        if self.is_bound:
            _mid = self.data.get('material')
            if _mid:
                _m = Material.objects.filter(pk=_mid).first()
                current_material_name = _m.name if _m else ''
        elif self.instance and self.instance.pk and self.instance.material_id:
            current_material_name = self.instance.material.name or ''

        include_nitin = 'crushed stone' in (current_material_name or '').lower()
        if include_nitin:
            target_driver_names = target_driver_names + ['Nitin Prasad']

        drivers_qs = Labour.objects.filter(
            Q(name__in=target_driver_names, is_active=True, status='ACTIVE')
            | (Q(name__iexact='nitin prasad', is_active=True, status='ACTIVE') if include_nitin else Q(pk=None))
        )

        if self.instance and self.instance.pk:
            if self.instance.customer_id:
                customer_qs = Customer.objects.filter(
                    Q(is_active=True) | Q(pk=self.instance.customer_id)
                )
            if self.instance.vehicle_id:
                vehicle_qs = Vehicle.objects.filter(
                    Q(is_active=True, status='ACTIVE') | Q(pk=self.instance.vehicle_id)
                )
            if self.instance.material_id:
                material_qs = Material.objects.filter(
                    Q(is_active=True) | Q(pk=self.instance.material_id)
                )
            if self.instance.drivers.exists():
                driver_ids = list(self.instance.drivers.values_list('pk', flat=True))
                drivers_qs = Labour.objects.filter(
                    Q(name__in=target_driver_names, is_active=True, status='ACTIVE')
                    | (Q(name__iexact='nitin prasad', is_active=True, status='ACTIVE') if include_nitin else Q(pk=None))
                    | Q(pk__in=driver_ids)
                )

        self.fields['customer'].queryset = customer_qs.order_by('name')
        self.fields['vehicle'].queryset = vehicle_qs.order_by('registration_number')
        self.fields['material'].queryset = material_qs.order_by('name')
        self.fields['drivers'].queryset = drivers_qs.order_by('name')

        self.fields['vehicle'].required = False
        self.fields['vehicle'].empty_label = "-- Select Vehicle (Optional) --"
        self.fields['material'].required = False
        self.fields['material'].empty_label = "-- Select Material (Optional for JCB) --"
        self.fields['drivers'].required = False
        self.fields['destination'].required = False
        self.fields['notes'].required = False
        self.fields['rate'].required = False

    def clean(self):
        cleaned_data = super().clean()
        trans_type = cleaned_data.get('transaction_type')
        customer = cleaned_data.get('customer')
        rate = cleaned_data.get('rate')
        vehicle_cat = cleaned_data.get('vehicle_category')
        vehicle = cleaned_data.get('vehicle')
        material = cleaned_data.get('material')
        drivers = cleaned_data.get('drivers')
        start_reading = cleaned_data.get('start_reading')
        end_reading = cleaned_data.get('end_reading')
        driver_bhatta = cleaned_data.get('driver_bhatta')

        is_jcb = (vehicle_cat == 'JCB') or (vehicle and 'JCB' in str(vehicle).upper()) or (start_reading is not None or end_reading is not None)

        if is_jcb:
            if start_reading is not None and end_reading is not None:
                if end_reading < start_reading:
                    self.add_error('end_reading', 'End reading cannot be less than start reading.')
                else:
                    hrs = end_reading - start_reading
                    cleaned_data['total_hours'] = hrs
                    cleaned_data['quantity'] = hrs
            if not driver_bhatta:
                cleaned_data['driver_bhatta'] = Decimal('200.00')
            jcb_mat, _ = Material.objects.get_or_create(
                name='JCB Work',
                defaults={'unit': 'TRIP', 'description': 'JCB Excavator & Earthmover Work', 'is_active': True}
            )
            cleaned_data['material'] = jcb_mat
        else:
            if not driver_bhatta:
                cleaned_data['driver_bhatta'] = Decimal('0.00')

        if trans_type == 'INTERNAL_STOCK':
            cleaned_data['customer'] = None
        elif not customer:
            self.add_error('customer', 'Customer is required. Please select the customer name.')

        if rate is None:
            cleaned_data['rate'] = Decimal('0')

        if material and not vehicle and trans_type != 'VENDOR_SUPPLY':
            self.add_error(
                'vehicle',
                'Vehicle is required when Material is selected. (Optional for Vendor Supply)'
            )

        if vehicle and not is_jcb and not drivers and trans_type not in ('INTERNAL_STOCK', 'VENDOR_SUPPLY'):
            self.add_error('drivers', 'Driver is required when a Vehicle is selected. (Optional for JCB, Internal Stock and Vendor Supply)')

        if drivers and vehicle_cat:

            tractor_only_names = [
                'Ankush Bhau',
                'Kishan Bhau',
                'Shubham Bhau',
            ]

            if vehicle_cat == 'TRACTOR':

                bad_drivers = [
                    d.name for d in drivers
                    if d.name not in tractor_only_names
                ]

                if bad_drivers:

                    self.add_error(
                        'drivers',
                        'Tractor ke liye sirf Ankush Bhau, Kishan Bhau ya Shubham Bhau chuno.'
                    )

            else:

                bad_drivers = [
                    d.name for d in drivers
                    if d.name in tractor_only_names
                ]

                if bad_drivers:

                    self.add_error(
                        'drivers',
                        'Ankush Bhau, Kishan Bhau & Shubham Bhau sirf Tractor ke liye hain. '
                        'Hyva/Halfton ke liye Gaju Bhau, Dinesh Bhaiya ya Santosh Bhaiya chuno.'
                    )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.temp_category = self.cleaned_data.get('vehicle_category')
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class TripPaymentForm(forms.ModelForm):

    class Meta:
        model = TripPayment

        fields = [
            'payment_date',
            'amount',
            'payment_method',
            'reference_number',
            'notes',
        ]

        widgets = {
            'payment_date': forms.DateInput(
                attrs={
                    'type': 'date',
                }
            ),

            'amount': forms.NumberInput(
                attrs={
                    'step': '0.01',
                    'min': '0.01',
                }
            ),

            'reference_number': forms.TextInput(
                attrs={
                    'placeholder': 'Optional',
                }
            ),

            'notes': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Optional notes',
                }
            ),
        }

    def __init__(self, *args, trip=None, **kwargs):

        super().__init__(*args, **kwargs)

        self.trip = trip

        self.fields['payment_method'].queryset = (
            PaymentMethod.objects.filter(
                is_active=True
            )
        )

        self.fields['reference_number'].required = False
        self.fields['notes'].required = False

        if not self.initial.get('payment_date'):
            self.initial['payment_date'] = (
                timezone.localdate()
            )

    def clean_amount(self):

        amount = self.cleaned_data.get('amount')

        if amount is None:
            return amount

        if amount <= 0:
            raise ValidationError(
                'Payment amount must be greater than zero.'
            )

        if self.trip:

            total_paid = (
                    self.trip.payments
                    .exclude(
                        pk=self.instance.pk
                    )
                    .aggregate(
                        total=Sum('amount')
                    )['total'] or 0
            )

            remaining_amount = (
                    self.trip.total_amount
                    - total_paid
            )

            if amount > remaining_amount:
                raise ValidationError(
                    f'Payment cannot exceed the '
                    f'outstanding amount of '
                    f'₹{remaining_amount}.'
                )

        return amount


class PaymentReportForm(TripPaymentForm):

    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        required=True,
        label='Customer',
        empty_label='-- Select Customer --',
        widget=forms.Select(
            attrs={
                'class': 'customer-select',
            }
        ),
    )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        selected_id = (
            self.data.get('customer')
            if self.data
            else self.initial.get('customer_id')
        )

        customer_qs = Customer.objects.filter(
            is_active=True
        )

        if selected_id:
            customer_qs = Customer.objects.filter(
                Q(is_active=True) | Q(pk=selected_id)
            )

        self.fields['customer'].queryset = (
            customer_qs.order_by('name')
        )

    def clean(self):

        cleaned_data = super().clean()

        customer = cleaned_data.get('customer')

        if customer:
            self.instance.customer = customer
            self.instance.trip = None

        return cleaned_data