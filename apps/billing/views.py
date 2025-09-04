from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.views.generic import CreateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db import transaction

from apps.products.models import InventoryMovement
from apps.users.models import AuditLog
from .models import Invoice, Reservation
from .forms import InvoiceForm, ReservationForm



# 1️⃣ Registrar venta (Salida de inventario)

class SaleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Crear una venta (directa o desde apartado) que genera salida en inventario y factura."""
    permission_required = "billing.add_invoice"
    model = Invoice
    form_class = InvoiceForm
    template_name = "backoffice/billing/sale_create.html"

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.compute_totals()
            self.object.save()

            # Si viene de un apartado → heredar cliente y marcar apartado como completado
            if self.object.reservation:
                reservation = self.object.reservation
                self.object.client_first_name = reservation.client_first_name
                self.object.client_last_name = reservation.client_last_name
                self.object.client_phone = reservation.client_phone
                reservation.status = "completed"
                reservation.save(update_fields=["status"])
                self.object.save()

            # Aplicar movimientos de inventario
            self.object.apply_inventory_movements(user=self.request.user, request=self.request)

            # Auditoría
            AuditLog.log_action(
                request=self.request,
                user=self.request.user,
                action="create",
                model="Invoice",
                obj=self.object,
                description=f"Factura #{self.object.code} registrada",
            )

        messages.success(self.request, f"Venta registrada correctamente. Factura #{self.object.code}")
        return redirect(reverse("backoffice:billing:invoice_detail", args=[self.object.pk]))



# 2️⃣ Apartados (reservas)

class ReservationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Registrar un apartado de productos con reglas de negocio."""
    permission_required = "billing.add_reservation"
    model = Reservation
    form_class = ReservationForm
    template_name = "backoffice/billing/reservation_create.html"

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            abono = self.object.amount_deposited or Decimal("0.00")
            total = sum([i.subtotal() for i in self.object.items.all()]) if self.object.pk else Decimal("0.00")

            # Regla de negocio → calcular plazo
            if abono >= (Decimal("0.20") * total):
                self.object.due_date = timezone.now() + timedelta(days=30)
            else:
                self.object.due_date = timezone.now() + timedelta(days=3)

            self.object.save()

            # Crear movimientos reservando stock
            self.object.mark_reserved_movements(user=self.request.user, request=self.request)

        messages.success(self.request, f"Reserva registrada. Vence el {self.object.due_date.date()}")
        return redirect(reverse("backoffice:billing:reservation_detail", args=[self.object.pk]))


class ReservationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "billing.view_reservation"
    model = Reservation
    template_name = "backoffice/billing/reservation_list.html"
    context_object_name = "reservations"

    def get_queryset(self):
        qs = super().get_queryset()
        # Revisar vencimientos y liberar stock si aplica
        for r in qs:
            if r.status == "active" and r.due_date < timezone.now():
                r.release(user=self.request.user, reason="expired", request=self.request)
        return qs


class ReservationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "billing.view_reservation"
    model = Reservation
    template_name = "backoffice/billing/reservation_detail.html"
    context_object_name = "reservation"



# 3️⃣ Facturas (ventas realizadas)

class InvoiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "billing.view_invoice"
    model = Invoice
    template_name = "backoffice/billing/invoice_list.html"
    context_object_name = "invoices"
    ordering = ["-created_at"]


class InvoiceDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "billing.view_invoice"
    model = Invoice
    template_name = "backoffice/billing/invoice_detail.html"
    context_object_name = "invoice"



# 4️⃣ Factura HTML limpia

class InvoiceHTMLView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Factura en plantilla exclusiva (HTML limpio)."""
    permission_required = "billing.view_invoice"
    model = Invoice
    template_name = "backoffice/billing/invoice_template/invoice_template.html"
    context_object_name = "invoice"
