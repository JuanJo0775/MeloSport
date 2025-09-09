# apps/billing/forms.py
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from .models import Invoice, InvoiceItem, Reservation, ReservationItem


# ------------------------
# 🔹 Descuentos predefinidos
# ------------------------
DISCOUNT_CHOICES = [
    (0, "0%"),
    (10, "10%"),
    (20, "20%"),
    (50, "50%"),
    (70, "70%"),
]


# ------------------------
# 🔹 Facturas
# ------------------------
class InvoiceForm(forms.ModelForm):
    discount_percentage = forms.ChoiceField(
        label="Descuento",
        choices=DISCOUNT_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    payment_method = forms.ChoiceField(
        label="Método de pago",
        choices=Invoice.PAYMENT_METHODS,
        required=True,
        widget=forms.RadioSelect,
    )
    payment_provider = forms.ChoiceField(
        label="Proveedor (si aplica)",
        choices=Invoice.DIGITAL_PROVIDERS,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    amount_paid = forms.DecimalField(
        label="Monto pagado",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )

    class Meta:
        model = Invoice
        fields = [
            "reservation",
            "client_first_name",
            "client_last_name",
            "client_phone",
            "discount_percentage",
            "payment_method",
            "payment_provider",
            "amount_paid",
            "notes",
        ]
        widgets = {
            "reservation": forms.Select(attrs={"class": "form-control"}),
            "client_first_name": forms.TextInput(attrs={"class": "form-control"}),
            "client_last_name": forms.TextInput(attrs={"class": "form-control"}),
            "client_phone": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean_discount_percentage(self):
        raw = self.cleaned_data.get("discount_percentage")
        try:
            return Decimal(raw)
        except Exception:
            return Decimal("0.00")

    def clean(self):
        cleaned = super().clean()
        pm = cleaned.get("payment_method")
        prov = cleaned.get("payment_provider")
        paid = cleaned.get("amount_paid") or Decimal("0.00")
        reservation = cleaned.get("reservation")

        # Validaciones básicas
        if pm == "DI" and not prov:
            raise ValidationError("Debes elegir un proveedor (Nequi o Daviplata) si seleccionas pago digital.")

        if paid < 0:
            raise ValidationError("El monto pagado no puede ser negativo.")

        # Validar restante si viene de reserva
        if reservation and reservation.amount_deposited is not None:
            total = self.instance.total or Decimal("0.00")
            abono = reservation.amount_deposited
            remaining = total - abono
            if remaining < 0:
                raise ValidationError("El restante a pagar no puede ser negativo.")
            if paid > remaining:
                raise ValidationError(f"El monto pagado ({paid}) no puede exceder el restante ({remaining}).")

        return cleaned


class InvoiceItemForm(forms.ModelForm):
    """Item de factura, validamos que no se permita producto vacío."""

    class Meta:
        model = InvoiceItem
        fields = ["product", "variant", "quantity", "unit_price"]
        widgets = {
            "product": forms.HiddenInput(),  # lo maneja el modal
            "variant": forms.Select(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        variant = cleaned.get("variant")
        qty = cleaned.get("quantity")

        if not product and not self.cleaned_data.get("DELETE"):
            raise ValidationError("Debe seleccionar un producto válido.")

        if qty is not None and qty <= 0:
            raise ValidationError("La cantidad debe ser mayor que 0.")

        # 🔹 Validación extra contra stock
        if product and qty:
            available = variant.stock if variant else product._stock
            if qty > available:
                raise ValidationError(f"No hay suficiente stock. Disponible: {available}.")

        return cleaned


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=0,
    can_delete=True,
)


# ------------------------
# 🔹 Apartados (Reservas)
# ------------------------
class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = [
            "client_first_name",
            "client_last_name",
            "client_phone",
            "amount_deposited",
        ]
        widgets = {
            "client_first_name": forms.TextInput(attrs={"class": "form-control"}),
            "client_last_name": forms.TextInput(attrs={"class": "form-control"}),
            "client_phone": forms.TextInput(attrs={"class": "form-control"}),
            "amount_deposited": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": 0}
            ),
        }


class ReservationItemForm(forms.ModelForm):
    """Item de reserva. Producto y variante vienen del panel dinámico (JS)."""

    class Meta:
        model = ReservationItem
        fields = ["product", "variant", "quantity", "unit_price"]
        widgets = {
            "product": forms.HiddenInput(),
            "variant": forms.HiddenInput(),  # 👈 ahora hidden, lo llena el JS
            "quantity": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": 0}
            ),
        }

    def clean(self):
        cleaned = super().clean()

        if not cleaned.get("product") and not self.cleaned_data.get("DELETE"):
            raise ValidationError("Debe seleccionar un producto válido.")

        if cleaned.get("quantity") is not None and cleaned["quantity"] <= 0:
            raise ValidationError("La cantidad debe ser mayor que 0.")

        if cleaned.get("unit_price") is not None and cleaned["unit_price"] < 0:
            raise ValidationError("El precio unitario no puede ser negativo.")

        return cleaned

class ReservationItemUpdateForm(forms.ModelForm):
    """Item de reserva para Update. Solo se usa para exponer datos ocultos (readonly)."""
    class Meta:
        model = ReservationItem
        fields = ["product", "variant", "quantity", "unit_price"]
        widgets = {
            "product": forms.HiddenInput(),
            "variant": forms.HiddenInput(),
            "quantity": forms.HiddenInput(),
            "unit_price": forms.HiddenInput(),
        }


ReservationItemFormSetCreate = inlineformset_factory(
    Reservation,
    ReservationItem,
    form=ReservationItemForm,
    extra=0,
    can_delete=True,
)

# Para actualizar reservas (no agregar, no eliminar)
ReservationItemFormSetUpdate = inlineformset_factory(
    Reservation,
    ReservationItem,
    form=ReservationItemUpdateForm,
    extra=0,
    can_delete=False,
)