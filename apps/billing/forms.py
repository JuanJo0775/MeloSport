from django import forms
from django.forms import inlineformset_factory

from .models import Invoice, InvoiceItem, Reservation, ReservationItem


# --- Descuentos predefinidos ---
DISCOUNT_CHOICES = [
    (0, "0%"),
    (10, "10%"),
    (20, "20%"),
    (50, "50%"),
    (70, "70%"),
]


# --- Formulario de Factura ---
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
    class Meta:
        model = InvoiceItem
        fields = ["product", "variant", "quantity", "unit_price"]
        widgets = {
            # Producto lo maneja el modal → se guarda como hidden
            "product": forms.HiddenInput(),
            # Variante simple (se llena con JS según producto)
            "variant": forms.Select(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
        }


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=0,   # no necesitamos uno vacío, ya que los productos se agregan vía modal
    can_delete=True,
)


# --- Formulario de Apartado ---
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
                attrs={"class": "form-control", "step": "0.01"}
            ),
        }


class ReservationItemForm(forms.ModelForm):
    class Meta:
        model = ReservationItem
        fields = ["product", "variant", "quantity", "unit_price"]
        widgets = {
            "product": forms.HiddenInput(),
            "variant": forms.Select(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
        }


ReservationItemFormSet = inlineformset_factory(
    Reservation,
    ReservationItem,
    form=ReservationItemForm,
    extra=0,
    can_delete=True,
)
