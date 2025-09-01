from django import forms
from .models import Product, ProductVariant, ProductImage
from django.forms import BaseInlineFormSet, ValidationError

class ProductForm(forms.ModelForm):
    """
    Formulario de Producto
    - Si tiene variantes, el stock manual se fuerza a 0
    - Si no tiene variantes, se exige un stock manual
    """

    # Campo "visible" que se mapea a _stock del modelo
    stock = forms.IntegerField(
        required=False,
        min_value=0,
        label="Stock",
        help_text="Solo se usa si el producto no tiene variantes",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "cost",
            "tax_percentage",
            "markup_percentage",
            "price",
            "stock",          # 👈 usamos este alias en vez de "_stock"
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
            "min_stock": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "placeholder": "Ej: 5"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "categories": forms.CheckboxSelectMultiple(),
            "absolute_category": forms.Select(attrs={"class": "form-select"}),
            "has_variants": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # inicializamos el alias "stock" con el valor real de _stock
        if self.instance and self.instance.pk:
            self.fields["stock"].initial = self.instance._stock

    def clean(self):
        cleaned_data = super().clean()
        has_variants = cleaned_data.get("has_variants")
        stock = cleaned_data.get("stock")

        if has_variants:
            # Si tiene variantes, stock manual no aplica
            if stock and stock > 0:
                self.add_error("stock", "Si el producto tiene variantes, el stock manual no se puede asignar aquí.")
            cleaned_data["stock"] = 0
        else:
            # Si no tiene variantes, exigir stock válido
            if stock is None or stock < 0:
                self.add_error("stock", "Debes asignar un stock válido cuando el producto no tiene variantes.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Mapear campo visible al real en BD
        instance._stock = self.cleaned_data.get("stock", 0)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


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
            "image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "is_main": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1"}),
        }

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is not None and order < 0:
            raise forms.ValidationError("El orden debe ser un número positivo.")
        return order

class BaseProductImageFormSet(BaseInlineFormSet):
    def clean(self):
        """
        Garantiza que exista al menos una imagen (ya sea existente o subida en el POST).
        """
        super().clean()
        has_image = False

        for form in self.forms:
            # Ignorar forms vacíos o marcados para borrar
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            # Si hay imagen nueva subida o una ya guardada en BD
            if form.cleaned_data.get("image") or (form.instance and form.instance.pk):
                has_image = True
                break

        if not has_image:
            raise ValidationError("Debes agregar al menos una imagen para el producto.")

class ConfirmDeleteForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirma tu contraseña"}),
        label="Contraseña",
    )