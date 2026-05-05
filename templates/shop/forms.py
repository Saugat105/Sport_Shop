from django import forms
from .models import Product, Category, Supplier


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'category', 'supplier', 'price',
            'cost_price', 'stock_quantity', 'low_stock_threshold', 'description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'placeholder': 'Rs.'}),
        }
