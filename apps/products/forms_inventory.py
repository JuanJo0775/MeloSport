# apps/products/forms_inventory.py
from django import forms
from decimal import Decimal
from typing import Optional
from .models import InventoryMovement, ProductVariant, Product
from django.core.exceptions import ValidationError


def _get_stock(obj) -> int:
    """Helper safe getter for stock (variant or product)."""
    if not obj:
        return 0
    return int(getattr(obj, "stock", getattr(obj, "_stock", 0)) or 0)


class InventoryMovementForm(forms.ModelForm):
    """
    Form personalizado para crear/editar movimientos de inventario.

    - En creación: normalmente se llama con hide_price_fields=True y hide_movement_type=True.
      * Se eliminan unit_price y discount_percentage.
      * Se fuerza movement_type="in".
    - En edición: movement_type puede mostrarse editable y los precios en modo readonly.
    - Si se pasa product_id, el campo product se convierte en HiddenInput
      y se añade product_display (solo lectura).
    - Flags disable_product / disable_variant permiten marcar esos campos como readonly.
    - El widget 'quantity' recibe atributos data-*:
        data-mtype: tipo de movimiento (in/out/adjust)
        data-old: cantidad previa del objeto al editar (0 si crear)
        data-available: stock actual (preferencia variante -> producto)
      Estos atributos facilitan el chequeo/advertencia en tiempo real desde JS.
    """

    product_display = forms.CharField(
        required=False,
        label="Producto",
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-plaintext",
                "readonly": "readonly",
            }
        ),
        help_text="Producto asociado (solo lectura).",
    )

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
        widgets = {
            "product": forms.Select(attrs={"class": "form-select", "data-select": "product"}),
            "variant": forms.Select(attrs={"class": "form-select", "data-select": "variant"}),
            "movement_type": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                    "step": "1",
                    "placeholder": "Cantidad (ej. 5)",
                }
            ),
            "unit_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "placeholder": "Precio unitario (se toma del producto)",
                }
            ),
            "discount_percentage": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "placeholder": "Descuento (%)",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Notas opcionales...",
                }
            ),
        }

    def __init__(
        self,
        *args,
        product_id: Optional[int] = None,
        variant_id: Optional[int] = None,
        hide_price_fields: bool = True,
        disable_product: bool = False,
        disable_variant: bool = False,
        hide_movement_type: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # --- Estilos básicos para campos ---
        for fname in ("product", "variant", "movement_type", "quantity", "notes"):
            if fname in self.fields:
                w = self.fields[fname].widget
                if not w.attrs.get("class"):
                    w.attrs["class"] = "form-select" if fname in ("movement_type", "product", "variant") else "form-control"

        # --- Detectar producto (instancia / product_id / POST) ---
        product_obj = getattr(self.instance, "product", None)

        if product_id and not product_obj:
            product_obj = Product.objects.filter(pk=product_id).first()
            self.initial.setdefault("product", product_id)

        # Caso POST: si el form se envía desde frontend
        if not product_obj and "product" in self.data:
            try:
                pid = self.data.get("product")
                if pid:
                    product_obj = Product.objects.get(pk=pid)
            except Product.DoesNotExist:
                product_obj = None

        # --- Configuración de producto y campo product_display ---
        if product_obj:
            if "product" in self.fields:
                # mantener el campo pero oculto (se envía su valor)
                self.fields["product"].widget = forms.HiddenInput()
                self.fields["product"].disabled = False
            self.fields["product_display"].initial = getattr(product_obj, "name", str(product_obj))
        else:
            # si no hay producto asociado, removemos product_display para evitar campos huérfanos
            self.fields.pop("product_display", None)

        # --- Configuración de variantes según producto ---
        if product_obj:
            variant_qs = ProductVariant.objects.filter(product_id=product_obj.pk)
            if not variant_qs.exists():
                # producto sin variantes -> quitar campo variant
                self.fields.pop("variant", None)
            else:
                self.fields["variant"].queryset = variant_qs
                if variant_id:
                    self.initial.setdefault("variant", variant_id)
                elif "variant" in self.data:
                    self.initial.setdefault("variant", self.data.get("variant"))
        else:
            if "variant" in self.fields:
                self.fields["variant"].queryset = ProductVariant.objects.none()

        # --- Precio / descuento ---
        if hide_price_fields:
            self.fields.pop("unit_price", None)
            self.fields.pop("discount_percentage", None)
        else:
            if "unit_price" in self.fields:
                self.fields["unit_price"].disabled = True
                self.fields["unit_price"].help_text = "Precio unitario tomado del producto (solo lectura)."
            if "discount_percentage" in self.fields:
                self.fields["discount_percentage"].disabled = True
                self.fields["discount_percentage"].help_text = "Descuento aplicado (solo lectura)."

        # --- Movement type ---
        if hide_movement_type and "movement_type" in self.fields:
            # forzamos el valor inicial y ocultamos el campo
            self.initial["movement_type"] = "in"
            self.fields.pop("movement_type")

        # --- Flags readonly ---
        if disable_product and "product" in self.fields:
            if "product_display" not in self.fields:
                # crear display si no existe
                self.fields["product_display"] = forms.CharField(
                    required=False,
                    disabled=True,
                    widget=forms.TextInput(attrs={"class": "form-control-plaintext"}),
                )
                if product_obj:
                    self.fields["product_display"].initial = getattr(product_obj, "name", str(product_obj))
            self.fields["product"].disabled = True

        if disable_variant and "variant" in self.fields:
            self.fields["variant"].disabled = True

        # --- Labels ---
        if "product" in self.fields:
            self.fields["product"].label = "Producto"
        if "variant" in self.fields:
            self.fields["variant"].label = "Variante"
        if "movement_type" in self.fields:
            self.fields["movement_type"].label = "Tipo de movimiento"
        if "quantity" in self.fields:
            self.fields["quantity"].label = "Cantidad"

        # --- Preparar atributos data-* para cantidad (soporte JS) ---
        if "quantity" in self.fields:
            qty_widget = self.fields["quantity"].widget

            # cantidad previa si estamos editando
            try:
                old_qty = int(getattr(self.instance, "quantity", 0) or 0)
            except Exception:
                old_qty = 0

            # tipo de movimiento (priorizar POST -> initial -> instancia)
            if "movement_type" in self.fields:
                mtype = self.data.get("movement_type") or self.initial.get("movement_type") or getattr(self.instance, "movement_type", "")
            else:
                mtype = self.initial.get("movement_type") or getattr(self.instance, "movement_type", "")

            # stock disponible preferiendo variante -> producto
            available = 0
            # Si hay una variante seleccionada en initial/instance/data, tratamos de resolverla.
            variant_obj = None
            # prioridad: initial 'variant' -> self.data -> instance.variant
            var_id = self.initial.get("variant") or self.data.get("variant")
            if var_id:
                try:
                    variant_obj = ProductVariant.objects.filter(pk=var_id).first()
                except Exception:
                    variant_obj = None
            if not variant_obj:
                variant_obj = getattr(self.instance, "variant", None)

            if variant_obj:
                available = _get_stock(variant_obj)
            elif product_obj:
                available = _get_stock(product_obj)

            qty_widget.attrs["data-mtype"] = str(mtype)
            qty_widget.attrs["data-old"] = str(old_qty)
            qty_widget.attrs["data-available"] = str(available)

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product", getattr(self.instance, "product", None))
        variant = cleaned.get("variant", getattr(self.instance, "variant", None))

        # movement_type: prefer cleaned, then initial, then instance
        movement_type = (
            cleaned.get("movement_type")
            or self.initial.get("movement_type")
            or getattr(self.instance, "movement_type", None)
        )

        qty = cleaned.get("quantity")

        # ---- Validaciones de cantidad básicas ----
        if movement_type in ("in", "out") and (qty is None or qty <= 0):
            raise ValidationError("Para entradas/salidas la cantidad debe ser un entero positivo.")
        if movement_type == "adjust" and (qty is None or int(qty) == 0):
            raise ValidationError("Para ajustes la cantidad no puede ser 0.")

        # ---- Validar stock disponible para salidas ----
        if movement_type == "out" and qty:
            # stock actual (después de aplicar movimientos actuales en BD)
            current_stock = _get_stock(variant or product)

            # Si estamos editando una salida que ya estaba aplicada, el stock actual ya
            # refleja la resta previa. Entonces el máximo permitido para qty es
            # current_stock + old_qty (porque old_qty ya fue restado).
            max_allowed = current_stock
            if getattr(self.instance, "pk", None):
                try:
                    old = int(getattr(self.instance, "quantity", 0) or 0)
                except Exception:
                    old = 0
                # Solo sumar old si la instancia previa era una salida (para mantener coherencia)
                if getattr(self.instance, "movement_type", None) == "out":
                    max_allowed = current_stock + old

            if qty > max_allowed:
                # Mensaje claro: mostrar stock actual y máximo permitido
                raise ValidationError(
                    f"No se puede realizar la salida de {qty} unidades. "
                    f"Disponibles actualmente: {current_stock}. "
                    f"Máximo permitido para este movimiento: {max_allowed}."
                )

        # ---- Defaults/normalizaciones ----
        if "discount_percentage" in self.fields and cleaned.get("discount_percentage") is None:
            cleaned["discount_percentage"] = Decimal("0.00")

        return cleaned



class BulkAddStockForm(forms.Form):
    """
    Acción masiva para productos (NO admite productos con variantes).
    Se envía CSV de product_ids (hidden) y la cantidad a agregar (movement_type='in' por defecto).
    """
    product_ids = forms.CharField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control form-control-sm", "placeholder": "Cantidad a agregar", "step": "1"}),
        label="Cantidad",
        help_text="Cantidad a sumar a cada producto seleccionado.",
    )
    movement_type = forms.ChoiceField(
        choices=[("in", "Entrada"), ("adjust", "Ajuste")],
        initial="in",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
        label="Tipo",
    )

    def clean_product_ids(self):
        raw = self.cleaned_data["product_ids"]
        try:
            ids = [int(x) for x in raw.split(",") if x.strip()]
        except Exception:
            raise forms.ValidationError("IDs inválidos.")
        if not ids:
            raise forms.ValidationError("Debe seleccionar al menos un producto.")
        # doble-check: asegurarnos que ninguno tiene variantes (caller ya debe validar)
        products_with_variants = ProductVariant.objects.filter(product_id__in=ids).values_list("product_id", flat=True).distinct()
        if products_with_variants:
            raise forms.ValidationError("Algunos productos seleccionados tienen variantes. Remuévelos de la selección o use la acción por variantes.")
        return ids


class BulkVariantsStockForm(forms.Form):
    """
    Acción masiva sobre variantes de un único producto.
    product_id se envía aparte (hidden), variant_ids: CSV.
    """
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    variant_ids = forms.CharField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control form-control-sm", "placeholder": "Cantidad", "step": "1"}),
        label="Cantidad",
    )
    movement_type = forms.ChoiceField(
        choices=[("in", "Entrada"), ("adjust", "Ajuste")],
        initial="in",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
        label="Tipo",
    )

    def clean_variant_ids(self):
        raw = self.cleaned_data["variant_ids"]
        try:
            ids = [int(x) for x in raw.split(",") if x.strip()]
        except Exception:
            raise forms.ValidationError("IDs de variantes inválidos.")
        if not ids:
            raise forms.ValidationError("Debe seleccionar al menos una variante.")
        return ids


class PasswordConfirmForm(forms.Form):
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Introduce tu contraseña"}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Contraseña incorrecta.")
        return password