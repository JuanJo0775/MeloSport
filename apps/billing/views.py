from decimal import Decimal
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import CreateView, ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.contrib import messages
from django.db import transaction

from apps.products.models import InventoryMovement, Product
from apps.users.models import AuditLog
from .models import Invoice, Reservation, InvoiceItem, ReservationItem
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


# Apartados (reservas)

class ReservationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Registrar un apartado de productos con reglas de negocio."""
    permission_required = "billing.add_reservation"
    model = Reservation
    form_class = ReservationForm
    template_name = "backoffice/billing/reservation_create.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        # Si hay POST, inicializamos el formset con POST para mostrar errores si los hay
        if self.request.POST:
            data["items_formset"] = ReservationItemFormSet(self.request.POST)
        else:
            data["items_formset"] = ReservationItemFormSet()
        return data

    def form_valid(self, form):
        """
        Validar form + formset, calcular due_date antes de guardar la reserva (no dejar due_date NULL).
        """
        # Creamos instancia sin guardar aún
        reservation = form.save(commit=False)

        # Asociar formset (no guardamos aún)
        items_formset = ReservationItemFormSet(self.request.POST, instance=reservation)

        # Validar formset antes de guardar cualquier cosa
        if not items_formset.is_valid():
            # get_context_data tomará self.request.POST y reconstruirá el formset con errores
            return self.form_invalid(form)

        # Calcular total a partir de los datos limpios del formset (ignorar forms marcados para borrar)
        total = Decimal("0.00")
        for item_form in items_formset:
            cleaned = item_form.cleaned_data
            if not cleaned:
                continue
            if cleaned.get("DELETE"):
                continue
            qty = cleaned.get("quantity") or 0
            unit_price = cleaned.get("unit_price") or Decimal("0.00")
            # Aseguramos Decimal para multiplicación
            total += (Decimal(str(qty)) * Decimal(str(unit_price)))

        # Abono
        abono = reservation.amount_deposited or Decimal("0.00")

        # Regla de negocio → calcular plazo antes de guardar la reserva
        if total > 0 and abono >= (Decimal("0.20") * total):
            reservation.due_date = timezone.now() + timedelta(days=30)
        else:
            reservation.due_date = timezone.now() + timedelta(days=3)

        # Guardado atómico
        with transaction.atomic():
            reservation.save()
            # Guardar los items vinculados a la reserva
            items_formset.instance = reservation
            items_formset.save()

            # Crear movimientos reservando stock (si tienes ese método en el modelo)
            try:
                reservation.mark_reserved_movements(user=self.request.user, request=self.request)
            except Exception:
                # Si quieres capturar errores específicos, hazlo aquí; por ahora dejamos que suba si algo crítico falla
                pass

        messages.success(self.request, f"Reserva registrada. Vence el {reservation.due_date.date()}")
        return redirect(reverse("backoffice:billing:reservation_detail", args=[reservation.pk]))


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


class ProductBrowserView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Vista que devuelve el listado filtrado de productos y variantes
    (se inserta dinámicamente en reservation_create o ventas).
    """
    permission_required = "products.view_product"
    template_name = "backoffice/billing/select_products_modal_content.html"

    def get(self, request, *args, **kwargs):
        q = request.GET.get("q", "").strip()
        filter_type = request.GET.get("type", "all")  # all | simple | variants
        stock_filter = request.GET.get("stock", "")  # opcional: >0 para mostrar solo con stock

        qs = Product.objects.all().order_by("name")

        # 🔹 Búsqueda insensible a mayúsculas/tildes (requiere PostgreSQL + unaccent)
        if q:
            qs = qs.filter(
                Q(name__unaccent__icontains=q) |
                Q(sku__unaccent__icontains=q)
            )

        # 🔹 Filtrar por tipo
        if filter_type == "simple":
            qs = qs.filter(variants__isnull=True)
        elif filter_type == "variants":
            qs = qs.filter(variants__isnull=False)

        # 🔹 Filtrar por stock disponible
        if stock_filter == "in_stock":
            qs = qs.filter(stock__gt=0)

        # 🔹 Prefetch variantes
        qs = qs.prefetch_related("variants")

        # 🔹 Reordenar: simples primero, luego con variantes
        simples = [p for p in qs if not p.variants.exists()]
        con_var = [p for p in qs if p.variants.exists()]
        products = simples + con_var

        return render(request, self.template_name, {
            "products": products,
            "query": q,
            "filter_type": filter_type,
            "stock_filter": stock_filter,
        })


def product_detail_json(request, pk):
    """
    Devuelve JSON con datos del producto y sus variantes
    para que el JS arme el formulario dinámico.
    """
    p = get_object_or_404(Product.objects.prefetch_related("variants"), pk=pk)

    variants = []
    for v in p.variants.all():
        variants.append({
            "id": v.pk,
            "label": getattr(v, "label", str(v)),
            "sku": getattr(v, "sku", ""),
            "stock": getattr(v, "stock", None),
            "price": str(getattr(v, "price", getattr(v, "sale_price", 0) or 0)),
        })

    data = {
        "id": p.pk,
        "name": getattr(p, "name", ""),
        "sku": getattr(p, "sku", ""),
        "image": p.image.url if getattr(p, "image", None) else "",
        "price": str(getattr(p, "price", getattr(p, "sale_price", 0) or 0)),
        "variants": variants,
        "stock": getattr(p, "stock", None),
    }
    return JsonResponse(data)