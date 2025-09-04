# apps/billing/urls.py
from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    # Ventas
    path("sales/register/", views.SaleCreateView.as_view(), name="sale_create"),

    # Reservas
    path("reservations/", views.ReservationListView.as_view(), name="reservation_list"),
    path("reservations/create/", views.ReservationCreateView.as_view(), name="reservation_create"),
    path("reservations/<int:pk>/", views.ReservationDetailView.as_view(), name="reservation_detail"),

    # Facturas
    path("invoices/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/html/", views.InvoiceHTMLView.as_view(), name="invoice_html"),

    # Productos: navegador/buscador y API JSON
    path("products/browser/", views.ProductBrowserView.as_view(), name="products_browser"),
    path("api/product/<int:pk>/", views.product_detail_json, name="product_detail_json"),
]
