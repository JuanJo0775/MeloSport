from datetime import date, timedelta
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
from .forms import InvoiceForm, ReservationForm, InvoiceItemFormSet, \
    ReservationItemFormSetCreate, ReservationItemFormSetUpdate, InvoiceItemSimpleFormSet
from django.utils import timezone



class SaleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Registrar una venta (directa o desde reserva) con productos estilo tarjetas."""
    permission_required = "billing.add_invoice"
    model = Invoice
    form_class = InvoiceForm
    template_name = "backoffice/billing/sale_create.html"
    paginate_by = 12  # productos por página

    # 🔹 Prefill inicial (si viene de reserva)
    def get_initial(self):
        initial = super().get_initial()
        reservation_id = self.request.GET.get("reservation")
        if reservation_id:
            res = get_object_or_404(Reservation, pk=reservation_id)
            initial.update({
                "client_first_name": res.client_first_name,
                "client_last_name": res.client_last_name,
                "client_phone": res.client_phone,
                "reservation": res,
                "amount_paid": res.remaining_due,
            })
        return initial

    # 🔹 Catálogo de productos con filtros
    def get_queryset(self):
        qs = (
            Product.objects.filter(status="active")
            .prefetch_related("variants", "images")
        )
        request = self.request
        q = request.GET.get("q", "").strip()
        filter_type = request.GET.get("type", "all")
        stock_filter = request.GET.get("stock", "in_stock")

        if q:
            qs = qs.filter(
                Q(name__unaccent_icontains=q) |
                Q(sku__unaccent_icontains=q) |
                Q(description__unaccent_icontains=q)
            ).distinct()

        simples = qs.filter(variants__isnull=True).order_by("name")
        variantes = qs.filter(variants__isnull=False).distinct().order_by("name")

        if filter_type == "simple":
            final_qs = simples
        elif filter_type == "variants":
            final_qs = variantes
        else:
            final_qs = list(simples) + list(variantes)

        if stock_filter == "in_stock":
            final_qs = [
                p for p in final_qs
                if (getattr(p, "stock", 0) and p.stock > 0) or
                   any((getattr(v, "stock", 0) or 0) > 0 for v in p.variants.all())
            ]
        return final_qs

    # 🔹 Contexto
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        reservation_id = self.request.GET.get("reservation")
        reservation = None
        if reservation_id:
            reservation = get_object_or_404(Reservation, pk=reservation_id)

        if self.request.POST:
            # Si el usuario está enviando el formulario
            context["items_formset"] = InvoiceItemSimpleFormSet(self.request.POST, prefix="items")

        elif reservation:
            # Si viene de una reserva → precargar con los items
            initial_data = [
                {
                    "product": item.product.pk,
                    "variant": item.variant.pk if item.variant else None,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in reservation.items.all()
            ]
            context["items_formset"] = InvoiceItemSimpleFormSet(initial=initial_data, prefix="items")

        else:
            # Si no hay POST ni reserva
            context["items_formset"] = InvoiceItemSimpleFormSet(prefix="items")

        # (catálogo de productos igual que antes)
        qs = self.get_queryset()
        paginator = Paginator(qs, self.paginate_by)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context.update({
            "products": page_obj,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "paginator": paginator,
            "current_q": self.request.GET.get("q", ""),
            "current_filter_type": self.request.GET.get("type", "all"),
            "current_stock_filter": self.request.GET.get("stock", "in_stock"),
            "querystring": self._get_querystring(),
            "reservation": reservation,
        })

        return context

    def _get_querystring(self):
        qs_copy = self.request.GET.copy()
        if "page" in qs_copy:
            qs_copy.pop("page")
        return qs_copy.urlencode()

    # 🔹 Guardado con validaciones extra
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context["items_formset"]

        if not items_formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.paid = True
            if not self.object.payment_date:
                self.object.payment_date = timezone.now()

            reservation_id = self.request.GET.get("reservation")
            if reservation_id:
                res = get_object_or_404(Reservation, pk=reservation_id)
                self.object.reservation = res
                self.object.amount_paid = res.remaining_due()
            else:
                self.object.amount_paid = self.object.total

            # Guardar factura
            self.object.save()

            # Guardar items manualmente a partir del simple formset
            for f in items_formset:
                if not f.cleaned_data or f.cleaned_data.get("DELETE"):
                    continue
                product = f.cleaned_data["product"]
                variant = f.cleaned_data.get("variant")
                qty = f.cleaned_data["quantity"]
                unit_price = f.cleaned_data["unit_price"]

                # Validación de stock
                stock = variant.stock if variant else getattr(product, "stock", 0)
                if qty > stock:
                    f.add_error("quantity", "Cantidad mayor al stock disponible.")
                    transaction.set_rollback(True)
                    return self.form_invalid(form)

                InvoiceItem.objects.create(
                    invoice=self.object,
                    product=product,
                    variant=variant,
                    quantity=qty,
                    unit_price=unit_price,
                )

                stock_obj = variant if variant else product
                stock_obj.stock -= qty
                stock_obj.save(update_fields=["stock"])

                InventoryMovement.objects.create(
                    product=product,
                    variant=variant,
                    quantity=-qty,
                    reason="sale",
                    reference_invoice=self.object,
                )

            # Finalizar lógica de la venta
            try:
                self.object.finalize(user=self.request.user, request=self.request)
            except Exception as e:
                form.add_error(None, str(e))
                transaction.set_rollback(True)
                return self.form_invalid(form)

            AuditLog.log_action(
                request=self.request,
                user=self.request.user,
                action="Create",
                model=Invoice,
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
        filter_type = request.GET.get("type", "all")
        stock_filter = request.GET.get("stock", "in_stock")

        if q:
            qs = qs.filter(
                Q(name__unaccent_icontains=q) |
                Q(sku__unaccent_icontains=q) |
                Q(description__unaccent_icontains=q)
            ).distinct()

        simples = qs.filter(variants__isnull=True).order_by("name")
        variantes = qs.filter(variants__isnull=False).distinct().order_by("name")

        if filter_type == "simple":
            final_qs = simples
        elif filter_type == "variants":
            final_qs = variantes
        else:
            final_qs = list(simples) + list(variantes)

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

        # Formset de items (forzado con prefix="items")
        if self.request.POST:
            context["items_formset"] = ReservationItemFormSetCreate(
                self.request.POST, prefix="items"
            )
        else:
            context["items_formset"] = ReservationItemFormSetCreate(prefix="items")

        # Productos con paginación
        qs = self.get_queryset()
        paginator = Paginator(qs, self.paginate_by)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["products"] = page_obj
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        context["paginator"] = paginator

        # mantener filtros actuales
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
        items_formset = ReservationItemFormSetCreate(
            self.request.POST, instance=reservation, prefix="items"
        )

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

        if total > 0 and abono >= (Decimal("0.20") * total):
            reservation.due_date = add_business_days(timezone.now(), 30)
        else:
            reservation.due_date = add_business_days(timezone.now(), 3)

        with transaction.atomic():
            reservation.save()
            items_formset.instance = reservation
            items_formset.save()

            try:
                reservation.mark_reserved_movements(user=self.request.user, request=self.request)
            except Exception:
                pass

            AuditLog.log_action(
                request=self.request,
                action="Create",
                model=self.model,
                obj=reservation,
                description=f"Reserva #{reservation.pk} creada para {reservation.client_first_name} {reservation.client_last_name}",
            )

        messages.success(self.request, f"Reserva registrada. Vence el {reservation.due_date.date()}")
        return redirect(reverse("backoffice:billing:reservation_detail", args=[reservation.pk]))


class ReservationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Permite actualizar datos de la reserva y el abono, pero no modificar los productos."""
    permission_required = "billing.change_reservation"
    model = Reservation
    form_class = ReservationForm
    template_name = "backoffice/billing/reservation_update.html"
    context_object_name = "reservation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # El formset solo se pasa para mostrar productos en el template (readonly)
        context["items_formset"] = ReservationItemFormSetUpdate(
            instance=self.object, prefix="items"
        )
        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)

            # usamos la propiedad total del modelo
            total = self.object.total
            abono = self.object.amount_deposited or Decimal("0.00")

            # recalcular vencimiento desde HOY
            if total > 0 and abono >= (Decimal("0.20") * total):
                self.object.due_date = add_business_days(timezone.now(), 30)
            else:
                self.object.due_date = add_business_days(timezone.now(), 3)

            self.object.save()

            # Auditoría
            AuditLog.log_action(
                request=self.request,
                action="Update",
                model=self.model,
                obj=self.object,
                description=f"Reserva #{self.object.pk} actualizada (cliente/abono)",
            )

        messages.success(self.request, f"Reserva #{self.object.pk} actualizada correctamente.")
        return super().form_valid(form)

    def get_success_url(self):
        # Ojo con el namespace: debe coincidir con tu urls.py
        return reverse("backoffice:billing:reservation_detail", args=[self.object.pk])


class ReservationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "billing.view_reservation"
    model = Reservation
    template_name = "backoffice/billing/reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("items", "items__product", "items__variant")

        # --- filtros ---
        request = self.request
        q = request.GET.get("q", "").strip()
        status = request.GET.get("status", "").strip()
        near_due = request.GET.get("near_due", "").strip()


        if q:
            qs = qs.filter(
                Q(client_first_name__unaccent_icontains=q) |
                Q(client_last_name__unaccent_icontains=q)
            )

        if status:
            qs = qs.filter(status=status)


        if near_due:
            try:
                days = int(near_due)
            except ValueError:
                days = 3  # default
            now = timezone.now()
            limit_date = now + timedelta(days=days)
            qs = qs.filter(status="active", due_date__lte=limit_date, due_date__gte=now)


        for r in qs:
            if r.status == "active" and r.due_date < timezone.now():
                r.release(user=self.request.user, reason="expired", request=self.request)

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        full_qs = Reservation.objects.all()

        context["stats"] = {
            "activas": full_qs.filter(status="active").count(),
            "con_abono": full_qs.filter(amount_deposited__gt=0).count(),
            "sin_abono": full_qs.filter(amount_deposited=0).count(),
            "vencidas": full_qs.filter(status="expired").count(),
        }

        # mantener valores de filtros actuales en el template
        context["current_q"] = self.request.GET.get("q", "")
        context["current_status"] = self.request.GET.get("status", "")
        context["current_near_due"] = self.request.GET.get("near_due", "")

        return context

# apps/billing/views.py
from datetime import date
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import DetailView

from .models import Reservation


class ReservationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "billing.view_reservation"
    model = Reservation
    template_name = "backoffice/billing/reservation_detail.html"
    context_object_name = "reservation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservation = self.object

        today = date.today()
        due_date = reservation.due_date.date() if reservation.due_date else None
        created_date = reservation.created_at.date() if reservation.created_at else None

        # Total de productos
        total = sum(item.subtotal for item in reservation.items.all())

        # Valores financieros
        amount_deposited = reservation.amount_deposited or Decimal("0.00")
        min_deposit = (total * Decimal("0.2")).quantize(Decimal("1")) if total else Decimal("0")
        balance_due = total - amount_deposited

        # Días restantes
        days_remaining = (due_date - today).days if due_date else None

        # Definir plazo según abono
        period_days = 30 if amount_deposited >= min_deposit else 3

        # Días transcurridos desde la creación
        elapsed_days = (today - created_date).days if created_date else 0

        # Porcentaje de progreso
        try:
            progress_percent = min(100, max(0, (elapsed_days / period_days) * 100))
        except Exception:
            progress_percent = 0

        # Label del breadcrumb (solución al problema de concatenación)
        breadcrumb_label = f"Reserva #{reservation.id}"

        # Actualizar contexto
        context.update({
            "total": total,
            "amount_deposited": amount_deposited,
            "min_deposit": min_deposit,
            "balance_due": balance_due,
            "days_remaining": days_remaining,
            "period_days": period_days,
            "elapsed_days": elapsed_days,
            "progress_percent": progress_percent,
            "breadcrumb_label": breadcrumb_label,
            # opcional: pasar "today" si lo usas en el template
            "today": today,
        })
        return context


class ReservationDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Cancela una reserva, libera stock y solicita validación de contraseña."""
    permission_required = "billing.delete_reservation"
    model = Reservation
    template_name = "backoffice/billing/reservation_confirm_delete.html"
    context_object_name = "reservation"
    success_url = reverse_lazy("backoffice:billing:reservation_list")

    def post(self, request, *args, **kwargs):
        """Sobrescribimos post para pedir contraseña antes de borrar."""
        self.object = self.get_object()

        # Verificar contraseña
        password = request.POST.get("password")
        if not password or not request.user.check_password(password):
            messages.error(request, "Contraseña incorrecta. No se pudo eliminar la reserva.")
            return self.get(request, *args, **kwargs)

        # Proceder con la eliminación
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