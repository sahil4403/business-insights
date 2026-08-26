from django import forms

from .models import VehicleDocument


class VehicleDocumentForm(forms.ModelForm):

    class Meta:
        model = VehicleDocument
        fields = [
            'vehicle',
            'doc_type',
            'document_number',
            'issue_date',
            'expiry_date',
            'file',
            'notes',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = self.fields['vehicle'].queryset.order_by('registration_number')
        self.fields['document_number'].required = False
        self.fields['issue_date'].required = False
        self.fields['file'].required = False
        self.fields['notes'].required = False
        self.fields['vehicle'].widget.attrs.update({'onchange': ''})
