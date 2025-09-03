# apps/products/forms_inventory.py
from decimal import Decimal
from typing import Optional

from django import forms
from django.core.exceptions import ValidationError

from .models import InventoryMovement, ProductVariant, Product


def _get_stock(obj) -> int:
    """Helper safe getter for stock (variant or product)."""
    if not obj:
        return 0
    return int(getattr(obj, "stock", getattr(obj, "_stock", 0)) or 0)


class InventoryMovementForm(forms.ModelForm):
    """
    Form personalizado para crear/editar movimientos de inventario.

    Comportamientos importantes:
    - En creación normalmente se llama con hide_price_fields=True y hide_movement_type=True
      (flujo de "Añadir stock"). En ese caso movement_type por defecto será 'in' y el campo
      se ocultará en el formulario.
    - Para edición se puede mostrar movement_type.
    - adjust_reason está incluido y es obligatorio en todos los movimientos.
    - El atributo data-* del campo 'quantity' se completa para facilitar validación/UX en JS:
        data-mtype: tipo de movimiento efectivo (in/out/adjust)
        data-old: cantidad previa (si editando)
        data-available: stock actual (prioriza variante sobre producto)
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
            "adjust_reason",   # obligatorio en todo
        ]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select", "data-select": "product"}),
            "variant": forms.Select(attrs={"class": "form-select", "data-select": "variant"}),
            "movement_type": forms.Select(attrs={"class": "form-select"}),
            # No definimos 'min' aquí: se define dinámicamente según movement_type
            "quantity": forms.NumberInput(
                attrs={
                    "class": "form-control",
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
            "adjust_reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Motivo obligatorio del movimiento",
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
        """
        Parámetros extras:
          - product_id / variant_id: para preseleccionar la relación.
          - hide_price_fields: si True se eliminan unit_price y discount_percentage.
          - hide_movement_type: si True se forzará un movement_type por defecto (ver abajo) y
            el campo se ocultará.
          - disable_product / disable_variant: marca el campo como readonly (disabled).
        """
        super().__init__(*args, **kwargs)

        # --- Estilos básicos de campos ---
        for fname in ("product", "variant", "movement_type", "quantity", "notes", "adjust_reason"):
            if fname in self.fields:
                w = self.fields[fname].widget
                if not w.attrs.get("class"):
                    w.attrs["class"] = "form-select" if fname in ("movement_type", "product", "variant") else "form-control"

        # --- Resolución del objeto product (instancia / product_id / POST) ---
        product_obj = getattr(self.instance, "product", None)

        if product_id and not product_obj:
            product_obj = Product.objects.filter(pk=product_id).first()
            if product_obj:
                self.initial.setdefault("product", product_id)

        if not product_obj and "product" in self.data:
            try:
                pid = self.data.get("product")
                if pid:
                    product_obj = Product.objects.filter(pk=pid).first()
            except Exception:
                product_obj = None

        # --- Configuración del campo product_display / ocultar product si corresponde ---
        if product_obj:
            if "product" in self.fields:
                # mantenemos el campo product como HiddenInput para enviar su valor
                self.fields["product"].widget = forms.HiddenInput()
                self.fields["product"].disabled = False
            self.fields["product_display"].initial = getattr(product_obj, "name", str(product_obj))
        else:
            # si no hay producto, eliminamos el field display para evitar inconsistencias
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

        # --- Precio / descuento (ocultar si corresponde) ---
        if hide_price_fields:
            # mantengo compatibilidad: si hide_price_fields True, eliminamos campos
            self.fields.pop("unit_price", None)
            self.fields.pop("discount_percentage", None)
        else:
            if "unit_price" in self.fields:
                self.fields["unit_price"].disabled = True
                self.fields["unit_price"].help_text = "Precio unitario tomado del producto (solo lectura)."
            if "discount_percentage" in self.fields:
                self.fields["discount_percentage"].disabled = True
                self.fields["discount_percentage"].help_text = "Descuento aplicado (solo lectura)."

        # --- Movement type: si se oculta, definimos valor por defecto 'in' (añadir stock) ---
        if hide_movement_type:
            # por defecto para los flujos "añadir stock" dejamos 'in'
            self.initial.setdefault("movement_type", "in")
            # removemos el campo para que la UI no lo muestre
            self.fields.pop("movement_type", None)

        # --- Flags readonly ---
        if disable_product and "product" in self.fields:
            if "product_display" not in self.fields:
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
        if "adjust_reason" in self.fields:
            self.fields["adjust_reason"].label = "Motivo (obligatorio)"
            # Marcamos obligatorio a nivel de campo (se comprobará también en clean)
            self.fields["adjust_reason"].required = True

        # --- Preparar atributos data-* para cantidad (soporte JS) ---
        if "quantity" in self.fields:
            qty_widget = self.fields["quantity"].widget

            # cantidad previa si estamos editando
            try:
                old_qty = int(getattr(self.instance, "quantity", 0) or 0)
            except Exception:
                old_qty = 0

            # tipo de movimiento (prioridad: POST -> initial -> instancia)
            if "movement_type" in self.fields:
                mtype = self.data.get("movement_type") or self.initial.get("movement_type") or getattr(self.instance, "movement_type", "")
            else:
                mtype = self.initial.get("movement_type") or getattr(self.instance, "movement_type", "")

            # stock disponible preferiendo variante -> producto
            available = 0
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

            # Ajustamos el atributo 'min' dinámicamente:
            if str(mtype) in ("in", "out"):
                qty_widget.attrs["min"] = "1"
            else:
                # en ajustes permitimos que la UI maneje (si usas signed qty) -> borramos min
                qty_widget.attrs.pop("min", None)

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product", getattr(self.instance, "product", None))
        variant = cleaned.get("variant", getattr(self.instance, "variant", None))

        # movimiento efectivo: preferir cleaned -> initial -> instancia
        movement_type = (
            cleaned.get("movement_type")
            or self.initial.get("movement_type")
            or getattr(self.instance, "movement_type", None)
        )

        qty = cleaned.get("quantity")

        # ---- Validaciones de cantidad ----
        if movement_type in ("in", "out") and (qty is None or qty <= 0):
            raise ValidationError("Para entradas/salidas la cantidad debe ser un entero positivo.")
        if movement_type == "adjust" and (qty is None or int(qty) == 0):
            raise ValidationError("Para ajustes la cantidad no puede ser 0 (usa positivo o negativo).")

        # ---- Validar stock disponible para salidas ----
        if movement_type == "out" and qty:
            current_stock = _get_stock(variant or product)

            # Si estamos editando una salida que ya existía, sumar la cantidad previa para calcular el máximo
            max_allowed = current_stock
            if getattr(self.instance, "pk", None):
                try:
                    old = int(getattr(self.instance, "quantity", 0) or 0)
                except Exception:
                    old = 0
                if getattr(self.instance, "movement_type", None) == "out":
                    max_allowed = current_stock + old

            if qty > max_allowed:
                raise ValidationError(
                    f"No se puede realizar la salida de {qty} unidades. Disponibles actualmente: {current_stock}. "
                    f"Máximo permitido para este movimiento: {max_allowed}."
                )

        # ---- Defaults / normalizaciones ----
        if "discount_percentage" in self.fields and cleaned.get("discount_percentage") is None:
            cleaned["discount_percentage"] = Decimal("0.00")

        # ---- Motivo obligatorio (ahora obligatorio en todo) ----
        reason = cleaned.get("adjust_reason")
        if not reason or not str(reason).strip():
            raise ValidationError("Debes indicar un motivo para el movimiento de inventario.")

        return cleaned


class InventoryAdjustmentForm(InventoryMovementForm):
    """
    Form especializado para ajustes de inventario.

    - En UI la cantidad siempre se muestra positiva.
    - Campo `action` determina si se añade o quita stock.
    - Al guardar, si action == 'remove' la cantidad se convierte a negativa.
    - Garantiza motivo obligatorio y valida stock para 'remove'.
    """
    ACTION_CHOICES = (
        ("add", "Añadir stock"),
        ("remove", "Quitar stock"),
    )

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        label="Tipo de ajuste",
        help_text="Selecciona si deseas añadir o quitar stock.",
    )

    def __init__(self, *args, **kwargs):
        """
        No pasar explícitamente hide_price_fields/hide_movement_type como argumentos
        separados a super() (evita errores "multiple values for keyword arg").
        En cambio los forzamos vía kwargs para pasarlos por **kwargs.
        """
        # Forzamos ocultar campos de precio a nivel UI para ajustes
        kwargs['hide_price_fields'] = True
        # Queremos controlar movement_type manualmente (no forzarlo a 'in' desde parent)
        kwargs.setdefault('hide_movement_type', False)

        # Llamada segura al padre (no duplicará kwargs)
        super().__init__(*args, **kwargs)

        # Forzar movement_type a 'adjust' y ocultarlo en la UI
        self.initial.setdefault("movement_type", "adjust")
        if "movement_type" in self.fields:
            self.fields["movement_type"].initial = "adjust"
            self.fields["movement_type"].widget = forms.HiddenInput()
            self.fields["movement_type"].required = False

        # Cantidad: en UI pedimos siempre positivos
        if "quantity" in self.fields:
            self.fields["quantity"].widget.attrs["min"] = "1"
            self.fields["quantity"].help_text = "Ingresa un número entero positivo. La acción define el efecto."

        # Motivo obligatorio (si existe en fields)
        if "adjust_reason" in self.fields:
            self.fields["adjust_reason"].required = True
            self.fields["adjust_reason"].label = "Motivo del ajuste"
            self.fields["adjust_reason"].help_text = "Explica por qué se realiza el ajuste (obligatorio para auditoría)."

        # Si estamos editando una instancia existente de tipo 'adjust',
        # normalizamos el valor que se muestra: cantidad positiva y acción acorde.
        if getattr(self, "instance", None) and getattr(self.instance, "pk", None):
            if getattr(self.instance, "movement_type", None) == "adjust":
                raw_qty = int(getattr(self.instance, "quantity", 0) or 0)
                # Mostrar siempre la magnitud (positiva) en el input
                self.initial.setdefault("quantity", abs(raw_qty))
                # Preseleccionar la acción acorde al signo original
                init_action = "remove" if raw_qty < 0 else "add"
                self.initial.setdefault("action", init_action)

    def clean(self):
        cleaned = super().clean()

        # Forzar movement_type en cleaned_data para no depender del POST/UI
        cleaned["movement_type"] = "adjust"

        qty = cleaned.get("quantity")
        action = cleaned.get("action") or (
            "remove" if (getattr(self.instance, "quantity", 0) < 0) else "add"
        )

        # Validaciones básicas
        if qty is None or qty <= 0:
            raise ValidationError({"quantity": "La cantidad debe ser un número entero positivo."})

        # Resolver stock actual (priorizar variante sobre producto)
        variant = cleaned.get("variant") or getattr(self.instance, "variant", None)
        product = cleaned.get("product") or getattr(self.instance, "product", None)
        current_stock = _get_stock(variant or product)

        # Si la acción es quitar, validar stock y convertir a negativo
        if action == "remove":
            if qty > current_stock:
                raise ValidationError(
                    {"quantity": f"No puedes quitar {qty} unidades. Stock disponible: {current_stock}."}
                )
            cleaned["quantity"] = -int(qty)
        else:
            cleaned["quantity"] = int(qty)

        # Motivo obligatorio: dejar error ligado al campo para mejor UX
        reason = cleaned.get("adjust_reason")
        if not reason or not str(reason).strip():
            raise ValidationError({"adjust_reason": "Debes indicar un motivo para el ajuste."})

        # Finalmente devolvemos cleaned_data
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