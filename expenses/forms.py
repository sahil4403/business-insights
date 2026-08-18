from django import forms

from .models import Expense


class ExpenseForm(forms.ModelForm):

    class Meta:
        model = Expense

        fields = [
            'expense_date',
            'category',
            'description',
            'amount',
            'payment_method',
            'vehicle',
            'labour',
            'paid_to',
            'reference_number',
            'notes',
            'include_in_profit',
        ]

        widgets = {
            'expense_date': forms.DateInput(
                attrs={
                    'type': 'date',
                }
            ),

            'description': forms.TextInput(
                attrs={
                    'placeholder': 'Enter expense description',
                }
            ),

            'amount': forms.NumberInput(
                attrs={
                    'step': '0.01',
                    'min': '0.01',
                    'placeholder': '0.00',
                }
            ),

            'paid_to': forms.TextInput(
                attrs={
                    'placeholder': 'Paid to',
                }
            ),

            'reference_number': forms.TextInput(
                attrs={
                    'placeholder': 'Reference number',
                }
            ),

            'notes': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Optional notes',
                }
            ),
        }
