# apps/products/forms.py
from django import forms
from .models import Product, ProductVariant

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "description",
            "price",
            "cost",
            "tax_percentage",
            "markup_percentage",
            "stock",
            "min_stock",
            "status",
            "categories",
            "absolute_category",
            "has_variants",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del producto"}),
            "sku": forms.TextInput(attrs={"class": "form-control", "placeholder": "SKU único"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Descripción"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cost": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "tax_percentage": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "markup_percentage": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": "form-control"}),
            "min_stock": forms.NumberInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "categories": forms.SelectMultiple(attrs={"class": "form-select"}),
            "absolute_category": forms.Select(attrs={"class": "form-select"}),
            "has_variants": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ["sku", "size", "color", "price_modifier", "stock", "is_active"]
        widgets = {
            "sku": forms.TextInput(attrs={"class": "form-control", "placeholder": "SKU variante"}),
            "size": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: M, L, XL"}),
            "color": forms.TextInput(attrs={"class": "form-control", "placeholder": "Color"}),
            "price_modifier": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
