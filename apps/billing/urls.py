# apps/billing/urls.py
from django.urls import path, include
from . import views

app_name = "billing"

urlpatterns = [
    # Ventas
    path("sales/register/", views.SaleCreateView.as_view(), name="sale_create"),

    # Reservas
    path("reservations/", views.ReservationListView.as_view(), name="reservation_list"),
    path("reservations/create/", views.ReservationCreateView.as_view(), name="reservation_create"),
    path("reservations/<int:pk>/", views.ReservationDetailView.as_view(), name="reservation_detail"),
    path("reservations/<int:pk>/update/", views.ReservationUpdateView.as_view(), name="reservation_update"),
    path("reservations/<int:pk>/delete/", views.ReservationDeleteView.as_view(), name="reservation_delete"),
    path("reservations/<int:pk>/cancel/", views.ReservationCancelView.as_view(), name="reservation_cancel"),
    path("reservations/<int:pk>/complete/", views.ReservationCompleteView.as_view(), name="reservation_complete"),

    # Facturas
    path("invoices/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/html/", views.InvoiceHTMLView.as_view(), name="invoice_html"),

    path("electronic/", include(("apps.billing.electronic.urls", "electronic"), namespace="electronic")),

    # Selección de productos para venta o reserva
    path('billing/selection/save/', views.SaveSelectionView.as_view(), name='selection_save'),
]
