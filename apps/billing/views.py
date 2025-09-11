from datetime import date, timedelta
from decimal import Decimal
import logging
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, DetailView, TemplateView, DeleteView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db import transaction, IntegrityError

from apps.products.models import InventoryMovement, Product
from apps.users.models import AuditLog
from .models import Invoice, Reservation, InvoiceItem, ReservationItem, add_business_days
from .forms import InvoiceForm, ReservationForm, InvoiceItemFormSet, \
    ReservationItemFormSetCreate, ReservationItemFormSetUpdate, InvoiceItemSimpleFormSet

logger = logging.getLogger(__name__)


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
            total_res = sum(item.subtotal for item in res.items.all())
            abono_res = res.amount_deposited or Decimal("0.00")
            saldo_res = total_res - abono_res

            initial.update({
                "client_first_name": res.client_first_name,
                "client_last_name": res.client_last_name,
                "client_phone": res.client_phone,
                "reservation": res,
                "amount_paid": saldo_res,
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

        if self.request.method == "POST":
            context["items_formset"] = InvoiceItemSimpleFormSet(self.request.POST, prefix="items")
        else:
            context["items_formset"] = InvoiceItemSimpleFormSet(prefix="items")

        if reservation:
            items_json = [
                {
                    "product_id": item.product_id,
                    "product_name": item.product.name,
                    "sku": item.product.sku,
                    "variant_id": item.variant_id or "",
                    "variant_label": " • ".join(
                        filter(None, [item.variant.size, item.variant.color])
                    ) if item.variant else "",
                    "unit_price": str(item.unit_price),
                    "qty": item.quantity,
                }
                for item in reservation.items.all()
            ]
            context["reservation_items_json"] = json.dumps(items_json, cls=DjangoJSONEncoder)
        else:
            context["reservation_items_json"] = "[]"

        qs = self.get_queryset()
        paginator = Paginator(qs, self.paginate_by)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        abono = Decimal("0.00")
        saldo = Decimal("0.00")
        if reservation:
            abono = reservation.amount_deposited or Decimal("0.00")
            total_reserva = sum(item.subtotal for item in reservation.items.all())
            saldo = total_reserva - abono

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
            "reservation_abono": abono,
            "reservation_saldo": saldo,
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
            print("❌ FORMSET inválido:", items_formset.errors)
            print("❌ MANAGEMENT form:", items_formset.management_form.errors)
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                # -------------------------
                # 1) Crear/guardar factura base
                # -------------------------
                self.object = form.save(commit=False)
                self.object.paid = True
                if not self.object.payment_date:
                    self.object.payment_date = timezone.now()

                # Intentar obtener la reserva desde cleaned_data (si el form la incluye)
                reservation = form.cleaned_data.get("reservation") if hasattr(form, "cleaned_data") else None

                # Si no vino en el form, buscar en POST/GET o en la propia instancia
                if not reservation:
                    reservation_id = (
                            self.request.POST.get("reservation")
                            or self.request.GET.get("reservation")
                            or getattr(self.object, "reservation_id", None)
                    )
                    if reservation_id:
                        try:
                            reservation = Reservation.objects.get(pk=reservation_id)
                        except Reservation.DoesNotExist:
                            reservation = None

                # Si encontramos la reserva, la adjuntamos a la factura antes de guardar
                if reservation:
                    self.object.reservation = reservation

                # Guardar la factura preliminar
                self.object.save()

                # -------------------------
                # 2) Crear items de la factura
                # -------------------------
                total_calculado = Decimal("0.00")
                for f in items_formset:
                    if not f.cleaned_data or f.cleaned_data.get("DELETE"):
                        continue

                    product = f.cleaned_data["product"]
                    variant = f.cleaned_data.get("variant")
                    qty = f.cleaned_data["quantity"]
                    unit_price = f.cleaned_data["unit_price"]

                    stock = variant.stock if variant else getattr(product, "_stock", 0)
                    if qty > stock:
                        f.add_error("quantity", "Cantidad mayor al stock disponible.")
                        raise IntegrityError("Stock insuficiente")

                    InvoiceItem.objects.create(
                        invoice=self.object,
                        product=product,
                        variant=variant,
                        quantity=qty,
                        unit_price=unit_price,
                    )
                    total_calculado += (unit_price * qty)

                # -------------------------
                # 3) Totales y monto pagado
                # -------------------------
                self.object.total = total_calculado

                # Si obtuvimos reservation arriba, usamos esa info para calcular amount_paid
                if reservation:
                    abono_res = reservation.amount_deposited or Decimal("0.00")
                    saldo_res = total_calculado - abono_res
                    if saldo_res < 0:
                        saldo_res = Decimal("0.00")
                    self.object.amount_paid = saldo_res
                else:
                    # Si el form trae campo amount_paid, se respetará; sino asumimos total
                    if not self.object.amount_paid or self.object.amount_paid == Decimal("0.00"):
                        self.object.amount_paid = total_calculado

                # -------------------------
                # 4) Revalidar formset (igual que antes)
                # -------------------------
                form = self.get_form(self.get_form_class())
                form.instance = self.object
                if not items_formset.is_valid():
                    print("❌ FORMSET inválido (post-save):", items_formset.errors)
                    print("❌ MANAGEMENT form (post-save):", items_formset.management_form.errors)
                    return self.form_invalid(form)

                # -------------------------
                # 5) Guardar factura definitiva y aplicar movimientos
                # -------------------------
                self.object.save()
                # finalize aplicará movimientos de inventario y actualizará el estado de la factura
                self.object.finalize(user=self.request.user, request=self.request)

                # -------------------------
                # 6) FORZAR completion de la reserva (si existe) — mismo botón hace todo
                # -------------------------
                # Reobtener/lockear la reserva para mayor consistencia
                if self.object.reservation:
                    try:
                        res = Reservation.objects.select_for_update().get(pk=self.object.reservation.pk)
                        print(
                            f"[form_valid] reservation BEFORE id={res.pk} status={res.status} movement_created={res.movement_created}")
                        # Llamamos al método del modelo (es idempotente: si no está 'active' no hará cambios)
                        res.complete(user=self.request.user, request=self.request)
                        AuditLog.log_action(
                            request=self.request,
                            user=self.request.user,
                            action="update",
                            model=Reservation,
                            obj=res,
                            description=f"Reserva #{res.pk} completada al crear venta (botón crear venta)."
                        )
                        print(f"[form_valid] reservation AFTER id={res.pk} status={res.status}")
                    except Reservation.DoesNotExist:
                        print(
                            f"[form_valid] reservation id {self.object.reservation.pk} no encontrada al intentar completar.")

                # -------------------------
                # 7) Log de la factura
                # -------------------------
                AuditLog.log_action(
                    request=self.request,
                    user=self.request.user,
                    action="create",
                    model=Invoice,
                    obj=self.object,
                    description=f"Factura #{self.object.code} registrada",
                )

        except IntegrityError:
            return self.form_invalid(form)
        except Exception as e:
            print("❌ ERROR en finalize o transacción:", str(e))
            form.add_error(None, str(e))
            return self.form_invalid(form)

        # Mensaje y redirección final al detalle de la factura
        messages.success(self.request, f"Venta registrada correctamente. Factura #{self.object.code}")
        return redirect(reverse("backoffice:billing:invoice_detail", args=[self.object.pk]))



# Facturas (ventas realizadas)

class InvoiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "billing.view_invoice"
    model = Invoice
    template_name = "backoffice/billing/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 20
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("items", "items__product", "items__variant")

        request = self.request
        q = request.GET.get("q", "").strip()
        payment_method = request.GET.get("payment_method", "").strip()
        payment_provider = request.GET.get("payment_provider", "").strip()
        date_from = request.GET.get("date_from", "").strip()
        date_to = request.GET.get("date_to", "").strip()

        # --- búsqueda cliente o código ---
        if q:
            qs = qs.filter(
                Q(client_first_name__unaccent_icontains=q) |
                Q(client_last_name__unaccent_icontains=q) |
                Q(code__icontains=q)
            )

        if payment_method:
            qs = qs.filter(payment_method=payment_method)

        if payment_provider:
            qs = qs.filter(payment_provider=payment_provider)

        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        full_qs = Invoice.objects.all()

        # 🔹 estadísticas rápidas
        context["stats"] = {
            "total_facturas": full_qs.count(),
            "total_vendido": sum(inv.total for inv in full_qs),
            "efectivo": full_qs.filter(payment_method="EF").count(),
            "digital": full_qs.filter(payment_method="DI").count(),
            "nequi": full_qs.filter(payment_provider="NEQUI").count(),
            "daviplata": full_qs.filter(payment_provider="DAVIPLATA").count(),
        }

        # 🔹 filtros actuales
        context["current_q"] = self.request.GET.get("q", "")
        context["current_payment_method"] = self.request.GET.get("payment_method", "")
        context["current_payment_provider"] = self.request.GET.get("payment_provider", "")
        context["current_date_from"] = self.request.GET.get("date_from", "")
        context["current_date_to"] = self.request.GET.get("date_to", "")

        return context


class InvoiceDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "billing.view_invoice"
    model = Invoice
    template_name = "backoffice/billing/invoice_detail.html"
    context_object_name = "invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object

        # Totales
        subtotal = invoice.subtotal or Decimal("0.00")
        total = invoice.total or Decimal("0.00")
        discount = invoice.discount_amount or Decimal("0.00")
        amount_paid = invoice.amount_paid or Decimal("0.00")
        balance_due = invoice.remaining_due()

        # Información de reserva (si existe)
        reservation = invoice.reservation
        reservation_info = None
        if reservation:
            reservation_info = {
                "id": reservation.pk,
                "status": reservation.status,
                "total": reservation.total,
                "abonado": reservation.amount_deposited,
                "saldo": reservation.remaining_due,
                "vence": reservation.due_date,
            }

        # Productos facturados
        items = invoice.items.select_related("product", "variant").all()

        # Armamos datos para mostrar bonito
        context.update({
            "subtotal": subtotal,
            "total": total,
            "discount": discount,
            "amount_paid": amount_paid,
            "balance_due": balance_due,
            "reservation_info": reservation_info,
            "items": items,
            "breadcrumb_label": f"Factura #{invoice.code or invoice.pk}",
        })
        return context


# Factura HTML limpia

class InvoiceHTMLView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Factura en plantilla exclusiva (HTML limpio)."""
    permission_required = "billing.view_invoice"
    model = Invoice
    template_name = "backoffice/billing/invoice_template/invoice_template.html"
    context_object_name = "invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object

        amount_paid = invoice.amount_paid or Decimal("0.00")
        balance_due = invoice.total - amount_paid

        context["balance_due"] = balance_due
        return context





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

        # 🔹 Ahora ambos plazos son corridos
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

            total = self.object.total
            abono = self.object.amount_deposited or Decimal("0.00")

            # 🔹 Recalcular vencimiento en días corridos
            if total > 0 and abono >= (Decimal("0.20") * total):
                self.object.due_date = timezone.now() + timedelta(days=30)
            else:
                self.object.due_date = timezone.now() + timedelta(days=3)

            self.object.save()

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


class ReservationCancelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Cancela (no borra) una reserva:
    - valida contraseña del usuario en POST
    - llama a reservation.cancel(...) que marca movimientos reserve como consumed=True
    - registra acción en AuditLog y muestra mensaje
    """
    permission_required = "billing.change_reservation"  # puedes cambiar a 'billing.delete_reservation' si prefieres ese permiso
    template_name = "backoffice/billing/reservation_confirm_cancel.html"

    def get(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(Reservation, pk=pk)
        return render(request, self.template_name, {"reservation": reservation})

    def post(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(Reservation, pk=pk)

        password = request.POST.get("password")
        if not password or not request.user.check_password(password):
            messages.error(request, "Contraseña incorrecta. No se pudo cancelar la reserva.")
            return render(request, self.template_name, {"reservation": reservation})

        if reservation.status != "active":
            messages.warning(request, "Solo se pueden cancelar reservas con estado 'Activo'.")
            return redirect(reverse("backoffice:billing:reservation_detail", args=[reservation.pk]))

        with transaction.atomic():
            # Usa el método del modelo para mantener la lógica atómica y consistente
            reservation.cancel(user=request.user, request=request)

            AuditLog.log_action(
                request=request,
                user=request.user,
                action="update",
                model=Reservation,
                obj=reservation,
                description=f"Reserva #{reservation.pk} cancelada desde UI."
            )

            messages.success(request, f"Reserva #{reservation.pk} cancelada correctamente.")

        return redirect(reverse("backoffice:billing:reservation_detail", args=[reservation.pk]))


class ReservationCompleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Marca una reserva como completada tras crear una venta y redirige a la factura.
    Implementado con locking y updates atómicos para garantizar que los movimientos 'reserve'
    queden marcados como consumed=True.
    """
    permission_required = "billing.change_reservation"

    def get(self, request, pk, *args, **kwargs):
        invoice_id = request.GET.get("invoice")
        try:
            with transaction.atomic():
                # Lockear la fila de la reserva para evitar race conditions
                res = Reservation.objects.select_for_update().get(pk=pk)
                print(f"[reservation_complete] invoked for reservation {pk} (status={res.status})")
                logger.info("[reservation_complete] invoked for reservation %s (status=%s)", pk, res.status)

                if res.status == "active":
                    # Marcar como completed (persistir)
                    res.status = "completed"
                    res.save(update_fields=["status"])
                    print(f"[reservation_complete] reservation {pk} status set to 'completed'")

                    # Obtener movimientos 'reserve' no consumidos y marcarlos consumed=True
                    reserve_qs = InventoryMovement.objects.filter(
                        reservation_id=res.pk,
                        movement_type="reserve",
                        consumed=False
                    )

                    reserve_ids = list(reserve_qs.values_list("id", flat=True))
                    if reserve_ids:
                        # Lockear movimientos antes de actualizar para consistencia
                        InventoryMovement.objects.select_for_update().filter(id__in=reserve_ids)

                    updated = reserve_qs.update(consumed=True)
                    print(f"[reservation_complete] updated reserve movements consumed=True count={updated}")
                    logger.info("[reservation_complete] reserve movements updated (consumed) = %s for reservation %s", updated, res.pk)

                    # Asegurar flag movement_created
                    if not res.movement_created:
                        res.movement_created = True
                        res.save(update_fields=["movement_created"])

                    AuditLog.log_action(
                        request=request,
                        user=request.user,
                        action="update",
                        model=Reservation,
                        obj=res,
                        description=f"Reserva #{res.pk} completada por conversión a venta (ReservationCompleteView)."
                    )
                    messages.success(request, f"Reserva #{res.pk} completada correctamente.")
                else:
                    # Si no está activa, solo informar
                    logger.info("[reservation_complete] reservation %s not active (status=%s)", res.pk, res.status)
                    messages.info(request, f"La reserva #{res.pk} no está en estado activo (estado actual: {res.status}).")

        except Reservation.DoesNotExist:
            messages.error(request, "Reserva no encontrada.")
            if invoice_id:
                return redirect(reverse("backoffice:billing:invoice_detail", args=[invoice_id]))
            return redirect(reverse("backoffice:billing:reservation_list"))

        # Redirigir a la factura creada (si se pasó invoice id), si no al detalle de la reserva
        if invoice_id:
            return redirect(reverse("backoffice:billing:invoice_detail", args=[invoice_id]))

        return redirect(reverse("backoffice:billing:reservation_detail", args=[res.pk]))