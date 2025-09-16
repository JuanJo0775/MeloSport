# apps/billing/electronic/urls.py

from django.urls import path
from .views import InvoiceElectronicView

app_name = "electronic"

urlpatterns = [
    path("invoice/<int:pk>/", InvoiceElectronicView.as_view(), name="invoice_electronic"),
]
