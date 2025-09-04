from django import forms
from django.forms import inlineformset_factory
from .models import Invoice, InvoiceItem, Reservation, ReservationItem

DISCOUNT_CHOICES = [
    (0, "0%"),
    (10, "10%"),
    (20, "20%"),
    (50, "50%"),
    (70, "70%"),
]


class InvoiceForm(forms.ModelForm):
    discount_percentage = forms.ChoiceField(choices=DISCOUNT_CHOICES, required=False)

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


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ["product", "variant", "quantity", "unit_price"]


InvoiceItemFormSet = inlineformset_factory(
    Invoice, InvoiceItem, form=InvoiceItemForm,
    extra=1, can_delete=True
)


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["client_first_name", "client_last_name", "client_phone", "amount_deposited", "due_date"]


ReservationItemFormSet = inlineformset_factory(
    Reservation, ReservationItem, fields=["product", "variant", "quantity", "unit_price"],
    extra=1, can_delete=True
)
