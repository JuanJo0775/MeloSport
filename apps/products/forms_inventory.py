# apps/products/forms_inventory.py
from django import forms
from decimal import Decimal
from .models import InventoryMovement, ProductVariant, Product

class InventoryMovementForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = [
            "product",
            "variant",
            "movement_type",
            "quantity",
            "unit_price",
            "discount_percentage",
            "notes",
        ]

    def __init__(self, *args, product_id=None, **kwargs):
        """
        Si product_id es provisto (cuando abrimos form desde el listado para un producto),
        filtramos variantes solo de ese producto y, si no tiene variantes, removemos el campo.
        """
        super().__init__(*args, **kwargs)

        # For UX: product field readonly/hidden if product_id is supplied (we'll hide it in template)
        if product_id:
            # limitar queryset de variantes al producto indicado
            self.fields["variant"].queryset = ProductVariant.objects.filter(product_id=product_id)
            # si el producto no tiene variantes -> quitar campo variant
            if not self.fields["variant"].queryset.exists():
                self.fields.pop("variant")
            # opcional: preselect product (we keep the field to let backend see product id)
            self.initial.setdefault("product", product_id)
        else:
            # Si no hay producto seleccionado, no mostramos variantes (evitar que el usuario elija una variante global)
            self.fields["variant"].queryset = ProductVariant.objects.none()

    def clean(self):
        cleaned = super().clean()
        # validaciones adicionales ya cubiertas en model.clean(), pero defensivamente:
        movement_type = cleaned.get("movement_type")
        qty = cleaned.get("quantity")
        if movement_type in ("in", "out") and (qty is None or qty <= 0):
            raise forms.ValidationError("Para entradas/salidas la cantidad debe ser un entero positivo.")
        if movement_type == "adjust" and (qty is None or int(qty) == 0):
            raise forms.ValidationError("Para ajustes la cantidad no puede ser 0.")
        # normalizar discount
        if cleaned.get("discount_percentage") is None:
            cleaned["discount_percentage"] = Decimal("0.00")
        return cleaned


class BulkAddStockForm(forms.Form):
    """
    Acción masiva para productos (NO admite productos con variantes).
    Envia lista de product_ids y la cantidad a agregar (movement_type='in').
    """
    product_ids = forms.CharField(widget=forms.HiddenInput)  # csv de ids
    quantity = forms.IntegerField(min_value=1)
    movement_type = forms.ChoiceField(choices=[("in", "Entrada"), ("adjust", "Ajuste")], initial="in")

    def clean_product_ids(self):
        raw = self.cleaned_data["product_ids"]
        try:
            ids = [int(x) for x in raw.split(",") if x.strip()]
        except Exception:
            raise forms.ValidationError("IDs inválidos.")
        if not ids:
            raise forms.ValidationError("Debe seleccionar al menos un producto.")
        # check no tengan variantes: caller should validate, but double-check here
        from .models import ProductVariant
        from .models import Product
        products_with_variants = ProductVariant.objects.filter(product_id__in=ids).values_list("product_id", flat=True).distinct()
        if products_with_variants:
            raise forms.ValidationError("Algunos productos seleccionados tienen variantes. Remuévelos de la selección o use la acción por variantes.")
        return ids


class BulkVariantsStockForm(forms.Form):
    """
    Acción masiva sobre variantes de un único producto.
    product_id se envía separadamente.
    variant_ids: CSV
    """
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    variant_ids = forms.CharField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(min_value=1)
    movement_type = forms.ChoiceField(choices=[("in", "Entrada"), ("adjust", "Ajuste")], initial="in")

    def clean_variant_ids(self):
        raw = self.cleaned_data["variant_ids"]
        try:
            ids = [int(x) for x in raw.split(",") if x.strip()]
        except Exception:
            raise forms.ValidationError("IDs de variantes inválidos.")
        if not ids:
            raise forms.ValidationError("Debe seleccionar al menos una variante.")
        return ids
