# apps/billing/forms.py

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

    class Meta:
        model = Invoice
        fields = [
            "reservation",
            "client_first_name",
            "client_last_name",
            "client_phone",
            "discount_percentage",
            "paid",
            "payment_date",
            "notes",
        ]
        widgets = {
            "reservation": forms.Select(attrs={"class": "form-control"}),
            "client_first_name": forms.TextInput(attrs={"class": "form-control"}),
            "client_last_name": forms.TextInput(attrs={"class": "form-control"}),
            "client_phone": forms.TextInput(attrs={"class": "form-control"}),
            "paid": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "payment_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


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
        if not cleaned.get("product") and not self.cleaned_data.get("DELETE"):
            raise ValidationError("Debe seleccionar un producto válido.")
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
    form=ReservationItemForm,
    extra=0,
    can_delete=False,
)