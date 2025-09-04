from decimal import Decimal
from datetime import timedelta

from django.db.models import Q
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


def _get_filtered_products(request):
    q = request.GET.get("q", "").strip()
    filter_type = request.GET.get("type", "all")  # all | simple | variants
    stock_filter = request.GET.get("stock", "")   # opcional: in_stock

    qs = Product.objects.filter(status="active").order_by("name").prefetch_related("variants", "images")

    if q:
        qs = qs.filter(
            Q(name__unaccent__icontains=q) |
            Q(sku__unaccent__icontains=q)
        )

    if filter_type == "simple":
        qs = qs.filter(variants__isnull=True)
    elif filter_type == "variants":
        qs = qs.filter(variants__isnull=False)

    if stock_filter == "in_stock":
        qs = qs.filter(Q(stock__gt=0) | Q(variants__stock__gt=0)).distinct()

    # Simples primero, luego con variantes
    simples = [p for p in qs if not p.variants.exists()]
    con_var = [p for p in qs if p.variants.exists()]
    return simples + con_var

# Apartados (reservas)

class ReservationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Registrar un apartado de productos con reglas de negocio."""
    permission_required = "billing.add_reservation"
    model = Reservation
    form_class = ReservationForm
    template_name = "backoffice/billing/reservation_create.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["items_formset"] = ReservationItemFormSet(self.request.POST)
        else:
            data["items_formset"] = ReservationItemFormSet()
        # 🔹 Añadir productos filtrados al contexto
        data["product_browser_products"] = _get_filtered_products(self.request)
        return data

    def form_valid(self, form):
        """Validar form + formset, calcular due_date antes de guardar."""
        reservation = form.save(commit=False)
        items_formset = ReservationItemFormSet(self.request.POST, instance=reservation)

        if not items_formset.is_valid():
            return self.form_invalid(form)

        # ✅ Verificar que no esté vacío
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
            reservation.due_date = timezone.now() + timedelta(days=30)
        else:
            reservation.due_date = timezone.now() + timedelta(days=3)

        with transaction.atomic():
            reservation.save()
            items_formset.instance = reservation
            items_formset.save()
            try:
                reservation.mark_reserved_movements(user=self.request.user, request=self.request)
            except Exception:
                pass

        messages.success(
            self.request,
            f"Reserva registrada. Vence el {reservation.due_date.date()}"
        )
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


#  Vista de productos
class ProductBrowserView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Vista que devuelve listado de productos y variantes
    (para insertarse en reservation_create o sale_create).
    """
    permission_required = "products.view_product"
    template_name = "backoffice/billing/select_products_modal_content.html"

    def get(self, request, *args, **kwargs):
        products = _get_filtered_products(request)
        return render(request, self.template_name, {
            "products": products,
            "query": request.GET.get("q", ""),
            "filter_type": request.GET.get("type", "all"),
            "stock_filter": request.GET.get("stock", ""),
        })


#  API JSON detalle producto
def product_detail_json(request, pk):
    """
    Devuelve JSON con datos del producto y sus variantes
    para que el JS arme el formulario dinámico.
    """
    p = get_object_or_404(Product.objects.prefetch_related("variants", "images"), pk=pk)

    variants = []
    for v in p.variants.all():
        # Usamos nombre legible: si tiene atributos, los concatenamos
        variant_label = getattr(v, "label", None) or str(v)
        if getattr(v, "sku", None):
            variant_label += f" • {v.sku}"

        variants.append({
            "id": v.pk,
            "label": variant_label,       # 👈 este es el usado por el <select>
            "sku": getattr(v, "sku", ""),
            "stock": getattr(v, "stock", None),
            "price": str(getattr(v, "price", getattr(v, "sale_price", 0) or 0)),
        })

    # label para producto principal
    product_label = getattr(p, "name", "")
    if getattr(p, "sku", None):
        product_label += f" • {p.sku}"

    data = {
        "id": p.pk,
        "name": getattr(p, "name", ""),
        "label": product_label,   # 👈 útil si quieres usarlo en preview
        "sku": getattr(p, "sku", ""),
        "image": p.get_main_image_url() if hasattr(p, "get_main_image_url") else "",
        "price": str(getattr(p, "price", getattr(p, "sale_price", 0) or 0)),
        "variants": variants,
        "stock": getattr(p, "stock", None),
    }
    return JsonResponse(data)
