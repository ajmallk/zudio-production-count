from django import forms
from .models import OrderItem, ProductionBatch, ARTICLE_SIZE_MAP

SIZE_CHOICES = [(s, f"Size {s} — Article {ARTICLE_SIZE_MAP[s]}") for s in sorted(ARTICLE_SIZE_MAP.keys())]


class OrderItemForm(forms.Form):
    size = forms.ChoiceField(
        choices=SIZE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'size-select'}),
        label='Size'
    )
    quantity = forms.IntegerField(
        min_value=1,
        max_value=10000,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter quantity', 'min': '1'}),
        label='Quantity'
    )


class BatchNotesForm(forms.ModelForm):
    class Meta:
        model = ProductionBatch
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes...'})
        }


class OCRUploadForm(forms.Form):
    image = forms.ImageField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        label='Upload Image (with Article & Size text)'
    )


class DateRangeFilterForm(forms.Form):
    PERIOD_CHOICES = [
        ('day', 'Today'),
        ('week', 'This Week'),
        ('month', 'This Month'),
        ('year', 'This Year'),
        ('custom', 'Custom Range'),
    ]
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        initial='month'
    )
    date_from = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=False
    )
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=False
    )
