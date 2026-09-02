from django import forms
from django.utils import timezone

from .models import (
    Labour,
    LabourTripGroup,
    LabourExtraPayment,
    LabourAdvance,
    LabourDriverPayment,
    LabourSettlement,
    LabourRozi,
)


class DateInput(forms.DateInput):
    input_type = 'date'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.setdefault('class', 'input')


class LabourForm(forms.ModelForm):
    class Meta:
        model = Labour
        fields = ['name', 'category', 'sub_category', 'base_daily_rate', 'is_driver']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Labour full name',
            }),
            'category': forms.Select(attrs={
                'class': 'input',
                'id': 'id_category',
            }),
            'sub_category': forms.Select(attrs={
                'class': 'input',
                'id': 'id_sub_category',
            }),
            'base_daily_rate': forms.NumberInput(attrs={
                'class': 'input',
                'min': 0,
                'step': '0.01',
                'placeholder': 'Full day rate (₹)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # sub_category stays hidden unless category is MISTRI (toggled by JS)
        self.fields['sub_category'].required = False
        self.fields['base_daily_rate'].required = False
        if self.instance and self.instance.pk and self.instance.category != 'MISTRI':
            self.fields['sub_category'].widget.attrs['disabled'] = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.base_daily_rate is None:
            instance.base_daily_rate = instance._meta.get_field('base_daily_rate').default
        if instance.category == 'HYVA_DRIVER':
            instance.is_driver = True
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class LabourTripGroupForm(forms.ModelForm):
    """Form for adding a new trip-group entry."""

    RATE_CHOICES = [100, 400, 450, 500]

    rate_preset = forms.ChoiceField(
        choices=[('', 'Custom')] + [(str(r), f'₹{r}') for r in RATE_CHOICES],
        required=False,
        widget=forms.Select(attrs={
            'class': 'input',
            'id': 'rate-preset',
        }),
    )

    class Meta:
        model = LabourTripGroup
        fields = ['date', 'trip_count', 'rate_per_trip', 'fill_type', 'labourers', 'note']
        widgets = {
            'date': DateInput(),
            'trip_count': forms.NumberInput(attrs={
                'class': 'input',
                'min': 1,
                'placeholder': 'No. of trips',
            }),
            'rate_per_trip': forms.NumberInput(attrs={
                'class': 'input',
                'min': 0,
                'step': '0.01',
                'id': 'rate-input',
            }),
            'fill_type': forms.Select(attrs={'class': 'input'}),
            'note': forms.Textarea(attrs={
                'class': 'input',
                'rows': 2,
                'placeholder': 'Optional note (e.g. material, location)',
            }),
        }
        labels = {
            'trip_count': 'Trip Count',
            'rate_per_trip': 'Rate per Trip (₹)',
        }

    def __init__(self, *args, category=None, keep_labourers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].initial = timezone.localdate()
        self.fields['labourers'].widget.attrs.update({
            'class': 'labour-multiselect',
            'size': 6,
        })
        qs = Labour.objects.filter(is_active=True).exclude(is_vendor=True)
        if category:
            qs = qs.filter(category=category)
        if keep_labourers:
            qs = qs | Labour.objects.filter(pk__in=keep_labourers)
        self.fields['labourers'].queryset = qs.distinct().order_by('name')
        # ensure labourers checkbox list has class
        self.fields['labourers'].widget.attrs.setdefault('data-searchable', '1')


class LabourHyvaTripForm(forms.Form):
    """Hyva Driver trip entry.

    Supports MULTIPLE load types on one day — the user adds rows, each row
    being a (load type, trip count) line. Each line becomes its own
    LabourTripGroup on save (one group per load type, shared date+workers),
    plus an optional daily bhatta (₹200) per selected labourer.

    The repeating rows are parsed in the view; this form validates the
    shared fields (date, labourers, bhatta, note).
    """

    BHATTA_AMOUNT = 200

    date = forms.DateField(
        widget=DateInput(),
        label='Date',
    )
    labourers = forms.ModelMultipleChoiceField(
        queryset=Labour.objects.none(),
        label='Hyva Drivers',
    )
    bhatta = forms.BooleanField(
        required=False,
        label=f'Bhatta (₹{BHATTA_AMOUNT}/day per labour)',
        help_text='Daily allowance — chaahithe ek behatta lagana ho toh check karo',
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'input',
            'rows': 2,
            'placeholder': 'Optional note (material, location)',
        }),
        label='Note (optional)',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].initial = timezone.localdate()
        self.fields['labourers'].queryset = Labour.objects.filter(
            category='HYVA_DRIVER', is_active=True
        ).exclude(is_vendor=True).order_by('name')


class LabourExtraPaymentForm(forms.ModelForm):
    class Meta:
        model = LabourExtraPayment
        fields = ['labour', 'date', 'amount', 'note']
        widgets = {
            'labour': forms.Select(attrs={'class': 'input'}),
            'date': DateInput(),
            'amount': forms.NumberInput(attrs={
                'class': 'input',
                'min': 0,
                'step': '0.01',
                'placeholder': 'Amount in ₹',
            }),
            'note': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'What was the extra work? (optional)',
            }),
        }

    def __init__(self, *args, labour=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].initial = timezone.localdate()
        self.fields['labour'].queryset = Labour.objects.filter(is_active=True).exclude(is_vendor=True).order_by('name')
        if labour is not None:
            self.fields['labour'].initial = labour
            self.fields['labour'].disabled = True


class LabourAdvanceForm(forms.ModelForm):
    """Single-labour advance form."""
    class Meta:
        model = LabourAdvance
        fields = ['labour', 'date', 'amount', 'note']
        widgets = {
            'labour': forms.Select(attrs={'class': 'input'}),
            'date': DateInput(),
            'amount': forms.NumberInput(attrs={
                'class': 'input',
                'min': 0,
                'step': '0.01',
                'placeholder': 'Advance amount',
            }),
            'note': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Note (optional)',
            }),
        }

    def __init__(self, *args, labour=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].initial = timezone.localdate()
        self.fields['labour'].queryset = Labour.objects.filter(is_active=True).exclude(is_vendor=True).order_by('name')
        if labour is not None:
            self.fields['labour'].initial = labour
            self.fields['labour'].disabled = True


class LabourAdvanceMultiForm(forms.Form):
    """
    Quick multi-entry form: one date, list of (labour, amount) rows.
    Handled as a formset of (labour_id, amount) pairs in the view.
    """
    date = forms.DateField(widget=DateInput())


class LabourDriverPaymentForm(forms.ModelForm):
    class Meta:
        model = LabourDriverPayment
        fields = ['labour', 'period_start', 'period_end', 'amount', 'note']
        widgets = {
            'labour': forms.Select(attrs={'class': 'input'}),
            'period_start': DateInput(),
            'period_end': DateInput(),
            'amount': forms.NumberInput(attrs={
                'class': 'input',
                'min': 0,
                'step': '0.01',
                'placeholder': 'Driver payment amount',
            }),
            'note': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Note (optional)',
            }),
        }

    def __init__(self, *args, labour=None, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields['period_end'].initial = today
        # period start default = first of current month
        self.fields['period_start'].initial = today.replace(day=1)
        self.fields['labour'].queryset = Labour.objects.filter(is_driver=True, is_active=True).exclude(is_vendor=True).order_by('name')
        if labour is not None:
            self.fields['labour'].initial = labour


class LabourSettlementForm(forms.ModelForm):
    class Meta:
        model = LabourSettlement
        fields = [
            'settlement_date', 'period_start', 'period_end',
            'old_balance_deducted', 'cash_paid', 'note',
        ]
        widgets = {
            'settlement_date': DateInput(),
            'period_start': DateInput(),
            'period_end': DateInput(),
            'old_balance_deducted': forms.NumberInput(attrs={
                'class': 'input',
                'min': 0,
                'step': '0.01',
                'id': 'id_old_balance_deducted',
            }),
            'cash_paid': forms.NumberInput(attrs={
                'class': 'input',
                'min': 0,
                'step': '0.01',
                'id': 'id_cash_paid',
            }),
            'note': forms.Textarea(attrs={
                'class': 'input',
                'rows': 2,
                'placeholder': 'Settlement note (optional)',
            }),
        }

    def __init__(self, *args, labour=None, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields['settlement_date'].initial = today
        self.fields['period_start'].initial = today.replace(day=1)
        self.fields['period_end'].initial = today


class LabourRoziForm(forms.ModelForm):
    """Add daily rozi — full / one & half / half day.

    Amount is auto-computed from the labourer's base_daily_rate in the model.
    """

    class Meta:
        model = LabourRozi
        fields = ['labour', 'date', 'day_type', 'note']
        widgets = {
            'labour': forms.Select(attrs={'class': 'input'}),
            'date': DateInput(),
            'day_type': forms.Select(attrs={'class': 'input'}),
            'note': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Note (optional)',
            }),
        }
        labels = {
            'labour': 'Labourer',
            'day_type': 'Rozi (Day Type)',
        }

    def __init__(self, *args, labour=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].initial = timezone.localdate()
        self.fields['labour'].queryset = Labour.objects.filter(is_active=True).exclude(is_vendor=True).order_by('name')
        if labour is not None:
            self.fields['labour'].initial = labour
            self.fields['labour'].disabled = True

