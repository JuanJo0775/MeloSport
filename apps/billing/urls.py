# apps/billing/urls.py
from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    # Ventas
    path("sales/register/", views.register_sale, name="register_sale"),

    # Reservas
    path("reservations/", views.reservation_list, name="reservation_list"),
    path("reservations/create/", views.create_reservation, name="create_reservation"),
    path("reservations/<int:pk>/", views.reservation_detail, name="reservation_detail"),

    # Facturas
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/html/", views.invoice_html, name="invoice_html"),

    # Descuentos
    path("discounts/", views.discount_list, name="discount_list"),
    path("discounts/create/", views.discount_create, name="discount_create"),
]
