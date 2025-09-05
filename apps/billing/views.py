from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views.generic import CreateView, ListView, DetailView, TemplateView, DeleteView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db import transaction

from apps.products.models import InventoryMovement, Product
from apps.users.models import AuditLog
from .models import Invoice, Reservation, InvoiceItem, ReservationItem, add_business_days
from .forms import InvoiceForm, ReservationForm, InvoiceItemFormSet, ReservationItemFormSet


# Registrar venta (Salida de inventario)

class SaleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Crear una venta (directa o desde apartado) que genera salida en inventario y factura."""
    permission_required = "billing.add_invoice"
    model = Invoice
    form_class = InvoiceForm
    template_name = "backoffice/billing/sale_create.html"

    def get_initial(self):
        """Si viene de un apartado, hereda datos del cliente."""
        initial = super().get_initial()
        reservation_id = self.request.GET.get("reservation")
        if reservation_id:
            res = get_object_or_404(Reservation, pk=reservation_id)
            initial.update({
                "reservation": res,
                "client_first_name": res.client_first_name,
                "client_last_name": res.client_last_name,
                "client_phone": res.client_phone,
            })
        return initial

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["items_formset"] = InvoiceItemFormSet(self.request.POST)
        else:
            reservation_id = self.request.GET.get("reservation")
            if reservation_id:
                # Prellenar los items desde el apartado
                res = get_object_or_404(Reservation, pk=reservation_id)
                data["items_formset"] = InvoiceItemFormSet(
                    queryset=InvoiceItem.objects.none(),
                    initial=[
                        {
                            "product": item.product,
                            "variant": item.variant,
                            "quantity": item.quantity,
                            "unit_price": item.unit_price,
                        }
                        for item in res.items.all()
                    ],
                )
            else:
                data["items_formset"] = InvoiceItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context["items_formset"]

        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.compute_totals()
            self.object.save()

            if items_formset.is_valid():
                items_formset.instance = self.object
                items_formset.save()
            else:
                return self.form_invalid(form)

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


# Facturas (ventas realizadas)

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


# Factura HTML limpia

class InvoiceHTMLView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Factura en plantilla exclusiva (HTML limpio)."""
    permission_required = "billing.view_invoice"
    model = Invoice
    template_name = "backoffice/billing/invoice_template/invoice_template.html"
    context_object_name = "invoice"




class ReservationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Registrar un apartado de productos con reglas de negocio."""
    permission_required = "billing.add_reservation"
    model = Reservation
    form_class = ReservationForm
    template_name = "backoffice/billing/reservation_create.html"
    paginate_by = 12  # productos por página


    # Queryset / filtros

    def get_queryset(self):
        qs = (
            Product.objects.filter(status="active")
            .prefetch_related("variants", "images")
        )

        request = self.request
        q = request.GET.get("q", "").strip()
        filter_type = request.GET.get("type", "all")  # all | simple | variants
        stock_filter = request.GET.get("stock", "in_stock")

        # 🔎 búsqueda con soporte unaccent (si está registrado)
        if q:
            qs = qs.filter(
                Q(name__unaccent_icontains=q) |
                Q(sku__unaccent_icontains=q) |
                Q(description__unaccent_icontains=q)
            ).distinct()

        # ⚡ forzar el orden simple → variantes
        simples = qs.filter(variants__isnull=True).order_by("name")
        variantes = qs.filter(variants__isnull=False).distinct().order_by("name")

        if filter_type == "simple":
            final_qs = simples
        elif filter_type == "variants":
            final_qs = variantes
        else:
            final_qs = list(simples) + list(variantes)

        # ✅ filtro stock
        if stock_filter == "in_stock":
            final_qs = [
                p for p in final_qs
                if (getattr(p, "stock", 0) and p.stock > 0) or
                   any((getattr(v, "stock", 0) or 0) > 0 for v in p.variants.all())
            ]

        return final_qs


    # Contexto

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Formset de items (POST o vacío)
        if self.request.POST:
            context["items_formset"] = ReservationItemFormSet(self.request.POST)
        else:
            context["items_formset"] = ReservationItemFormSet()

        # Productos con paginación
        qs = self.get_queryset()
        paginator = Paginator(qs, self.paginate_by)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["products"] = page_obj  # iterable en template
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        context["paginator"] = paginator

        # mantener filtros actuales (útil para inputs y paginación)
        context["current_q"] = self.request.GET.get("q", "")
        context["current_filter_type"] = self.request.GET.get("type", "all")
        context["current_stock_filter"] = self.request.GET.get("stock", "in_stock")
        qs_copy = self.request.GET.copy()
        if "page" in qs_copy:
            qs_copy.pop("page")
        context["querystring"] = qs_copy.urlencode()

        return context


    # Guardado (form + formset + auditoría + bloqueo stock)

    def form_valid(self, form):
        reservation = form.save(commit=False)
        items_formset = ReservationItemFormSet(self.request.POST, instance=reservation)

        if not items_formset.is_valid():
            return self.form_invalid(form)

        has_items = False
        total = Decimal("0.00")

        for item_form in items_formset:
            cleaned = getattr(item_form, "cleaned_data", None)
            if not cleaned or cleaned.get("DELETE"):
                continue

            has_items = True
            qty = cleaned.get("quantity") or 0
            unit_price = cleaned.get("unit_price") or Decimal("0.00")
            total += (Decimal(str(qty)) * Decimal(str(unit_price)))

        if not has_items:
            form.add_error(None, "No puede enviar un formulario vacío")
            return self.form_invalid(form)

        abono = reservation.amount_deposited or Decimal("0.00")

        # vencimiento según el abono (en días hábiles)
        if total > 0 and abono >= (Decimal("0.20") * total):
            reservation.due_date = add_business_days(timezone.now(), 30)
        else:
            reservation.due_date = add_business_days(timezone.now(), 3)

        with transaction.atomic():
            reservation.save()
            items_formset.instance = reservation
            items_formset.save()

            # marcar movimientos / bloquear stock (usa tu método existente)
            try:
                reservation.mark_reserved_movements(user=self.request.user, request=self.request)
            except Exception:
                # no fallar el guardado si el bloque de stock falla temporalmente
                pass

            # Auditoría
            AuditLog.log_action(
                request=self.request,
                action="Create",
                model=self.model,
                obj=reservation,
                description=f"Reserva #{reservation.pk} creada para {reservation.client_first_name} {reservation.client_last_name}",
            )

        messages.success(self.request, f"Reserva registrada. Vence el {reservation.due_date.date()}")
        return redirect(reverse("backoffice:billing:reservation_detail", args=[reservation.pk]))


class ReservationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "billing.view_reservation"
    model = Reservation
    template_name = "backoffice/billing/reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related("client").prefetch_related("items")
        # Revisar vencimientos y liberar stock si aplica
        for r in qs:
            if r.status == "active" and r.due_date < timezone.now():
                r.release(user=self.request.user, reason="expired", request=self.request)
        return qs.order_by("-created_at")


class ReservationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "billing.view_reservation"
    model = Reservation
    template_name = "backoffice/billing/reservation_detail.html"
    context_object_name = "reservation"


class ReservationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Permite actualizar datos de la reserva y sus items."""
    permission_required = "billing.change_reservation"
    model = Reservation
    form_class = ReservationForm
    template_name = "backoffice/billing/reservation_update.html"
    context_object_name = "reservation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["items_formset"] = ReservationItemFormSet(self.request.POST, instance=self.object)
        else:
            context["items_formset"] = ReservationItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context["items_formset"]

        if not items_formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()
            items_formset.instance = self.object
            items_formset.save()

            # recalcular vencimiento
            total = sum(item.subtotal for item in self.object.items.all())
            abono = self.object.amount_deposited or Decimal("0.00")
            if total > 0 and abono >= (Decimal("0.20") * total):
                self.object.due_date = add_business_days(timezone.now(), 30)
            else:
                self.object.due_date = add_business_days(timezone.now(), 3)
            self.object.save()

            AuditLog.log_action(
                request=self.request,
                action="Update",
                model=self.model,
                obj=self.object,
                description=f"Reserva #{self.object.pk} actualizada",
            )

        messages.success(self.request, f"Reserva #{self.object.pk} actualizada correctamente.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("billing:reservation_detail", args=[self.object.pk])


class ReservationDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Cancela una reserva y libera stock."""
    permission_required = "billing.delete_reservation"
    model = Reservation
    template_name = "backoffice/billing/reservation_confirm_delete.html"
    context_object_name = "reservation"
    success_url = reverse_lazy("billing:reservation_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        with transaction.atomic():
            # liberar stock
            self.object.release(user=request.user, reason="cancelled", request=request)

            AuditLog.log_action(
                request=request,
                action="Delete",
                model=self.model,
                obj=self.object,
                description=f"Reserva #{self.object.pk} eliminada",
            )

            messages.success(request, f"Reserva #{self.object.pk} cancelada y stock liberado.")
        return super().delete(request, *args, **kwargs)