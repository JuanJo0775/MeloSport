from django import forms
from .models import Product, ProductVariant, ProductImage


class ProductForm(forms.ModelForm):
    """
    Formulario de Producto
    - Si tiene variantes, el stock manual se fuerza a 0
    - Si no tiene variantes, se exige un stock manual
    """

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "cost",
            "tax_percentage",
            "markup_percentage",
            "price",
            "_stock",  # 👈 siempre usamos _stock (campo real en BD)
            "min_stock",
            "status",
            "categories",
            "absolute_category",
            "has_variants",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del producto"}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Descripción del producto"}
            ),
            "cost": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "tax_percentage": forms.Select(
                choices=[(0, "0%"), (10, "10%"), (15, "15%"), (19, "19%"), (25, "25%")],
                attrs={"class": "form-select"}
            ),
            "markup_percentage": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "placeholder": "% ganancia"}
            ),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "_stock": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "min_stock": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "placeholder": "Ej: 5"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "categories": forms.CheckboxSelectMultiple(),
            "absolute_category": forms.Select(attrs={"class": "form-select"}),
            "has_variants": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        has_variants = cleaned_data.get("has_variants")
        stock = cleaned_data.get("_stock")

        if has_variants:
            # Si tiene variantes, forzamos stock manual a 0
            if stock and stock > 0:
                self.add_error("_stock", "Si el producto tiene variantes, el stock manual no se puede asignar aquí.")
            cleaned_data["_stock"] = 0
        else:
            # Si no tiene variantes, exigir stock manual
            if stock is None or stock < 0:
                self.add_error("_stock", "Debes asignar un stock válido cuando el producto no tiene variantes.")
        return cleaned_data


class ProductVariantForm(forms.ModelForm):
    """Formulario para variantes del producto"""

    class Meta:
        model = ProductVariant
        fields = ["size", "color", "price_modifier", "stock", "is_active"]
        widgets = {
            "size": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: M, L, XL"}),
            "color": forms.TextInput(attrs={"class": "form-control", "placeholder": "Color"}),
            "price_modifier": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["image", "is_main", "order"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),  # 👈 sin multiple
            "is_main": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1"}),
        }

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is not None and order < 0:
            raise forms.ValidationError("El orden debe ser un número positivo.")
        return order
