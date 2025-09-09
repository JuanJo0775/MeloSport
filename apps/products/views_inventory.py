# apps/products/views_inventory.py
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse

from .models import InventoryMovement, Product, ProductVariant
from apps.users.models import AuditLog
from .forms_inventory import InventoryMovementForm, BulkAddStockForm, BulkVariantsStockForm, PasswordConfirmForm, \
    InventoryAdjustmentForm

# ----------------------------
# Index de Inventario (antesala)
# ----------------------------
from django.db.models import Count, Q, Sum

from ..billing.models import Reservation


class InventoryIndexView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Página inicial de Inventario (antesala sin tablas)."""
    permission_required = "products.view_inventorymovement"
    template_name = "backoffice/inventory/index_inventario.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        LOW_STOCK_THRESHOLD = 5  # ajusta el umbral a tu necesidad

        # -----------------------
        # Productos SIN variantes
        # -----------------------
        productos_sin_variantes = Product.objects.filter(variants__isnull=True).distinct()

        low_stock_prod = productos_sin_variantes.filter(
            _stock__gt=0, _stock__lte=LOW_STOCK_THRESHOLD
        ).count()

        no_stock_prod = productos_sin_variantes.filter(
            Q(_stock__isnull=True) | Q(_stock__lte=0)
        ).count()

        # ----------
        # Variantes
        # ----------
        low_stock_var = ProductVariant.objects.filter(
            stock__gt=0, stock__lte=LOW_STOCK_THRESHOLD
        ).count()

        no_stock_var = ProductVariant.objects.filter(
            Q(stock__isnull=True) | Q(stock__lte=0)
        ).count()

        # Totales consolidados (sin doble conteo)
        ctx["low_stock_count"] = low_stock_prod + low_stock_var
        ctx["no_stock_count"] = no_stock_prod + no_stock_var

        # Movimientos → Entradas y Salidas
        ctx["entries_count"] = InventoryMovement.objects.filter(movement_type="in").count()
        ctx["exits_count"] = InventoryMovement.objects.filter(movement_type="out").count()

        # Otros que ya tenías
        ctx["products_count"] = Product.objects.count()
        ctx["variants_count"] = ProductVariant.objects.count()
        ctx["movements_count"] = InventoryMovement.objects.count()

        return ctx


# ----------------------------
# CRUD de movimientos
# ----------------------------
class InventoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Listado de movimientos de inventario (solo ver)."""
    permission_required = "products.view_inventorymovement"
    model = InventoryMovement
    template_name = "backoffice/inventory/list.html"
    context_object_name = "movements"
    paginate_by = 25

    def get_queryset(self):
        qs = InventoryMovement.objects.select_related("product", "variant", "user").all()
        q = Q()

        if t := self.request.GET.get("type"):
            q &= Q(movement_type=t)

        if u := self.request.GET.get("user"):
            q &= (
                Q(user__username__unaccent_icontains=u)
                | Q(user__first_name__unaccent_icontains=u)
                | Q(user__last_name__unaccent_icontains=u)
            )

        if p := self.request.GET.get("product"):
            q &= (
                Q(product__name__unaccent_icontains=p)
                | Q(product__sku__unaccent_icontains=p)
                | Q(variant__sku__unaccent_icontains=p)
            )

        if df := self.request.GET.get("date_from"):
            q &= Q(created_at__date__gte=df)

        if dt := self.request.GET.get("date_to"):
            q &= Q(created_at__date__lte=dt)

        return qs.filter(q).order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx["filters"] = {
            "type": self.request.GET.get("type", ""),
            "user": self.request.GET.get("user", ""),
            "product": self.request.GET.get("product", ""),
            "date_from": self.request.GET.get("date_from", ""),
            "date_to": self.request.GET.get("date_to", ""),
        }

        base_qs = self.get_queryset()
        ctx["entries_count"] = base_qs.filter(movement_type="in").count()
        ctx["exits_count"] = base_qs.filter(movement_type="out").count()
        ctx["adjustments_count"] = base_qs.filter(movement_type="adjust").count()
        ctx["reserves_count"] = base_qs.filter(movement_type="reserve").count()  # 👈 nuevo

        return ctx


class InventoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Crear movimiento de inventario (solo entradas de stock)."""

    permission_required = "products.add_inventorymovement"
    model = InventoryMovement
    form_class = InventoryMovementForm
    template_name = "backoffice/inventory/create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # En creación ocultamos precio/descuento y movement_type (siempre será "in")
        kwargs.update({
            "hide_price_fields": True,
            "hide_movement_type": True,   # 👈 ahora se oculta el select
        })
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.movement_type = "in"  # 🚀 siempre será entrada

        # Calcular unit_price desde producto + variante (si aplica)
        product = form.cleaned_data.get("product")
        variant = form.cleaned_data.get("variant", None)
        base_price = Decimal(product.price or 0)
        if variant:
            modifier = Decimal(variant.price_modifier or 0)
            computed_price = (base_price + modifier).quantize(Decimal("0.01"))
        else:
            computed_price = base_price.quantize(Decimal("0.01"))

        form.instance.unit_price = computed_price
        form.instance.discount_percentage = Decimal("0.00")

        with transaction.atomic():
            self.object = form.save()
            AuditLog.log_action(
                request=self.request,
                action="Create",
                model=InventoryMovement,
                obj=self.object,
                description=f"Entrada de stock '{self.object.id}' sobre '{self.object.product.name}'"
            )
        messages.success(self.request, "Entrada de stock registrada correctamente.")
        return redirect(reverse("backoffice:products:inventory:products_inventory_list"))


class InventoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Actualizar movimiento (solo Admin)."""
    permission_required = "products.change_inventorymovement"
    model = InventoryMovement
    form_class = InventoryMovementForm
    template_name = "backoffice/inventory/update.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Mostrar precios/descuentos pero como solo lectura
        kwargs.update({
            "hide_price_fields": False,
            "disable_product": True,
            "disable_variant": True,
        })
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            AuditLog.log_action(
                request=self.request,
                action="Update",
                model=InventoryMovement,
                obj=self.object,
                description=f"Movimiento '{self.object.id}' actualizado"
            )
        messages.success(self.request, "Movimiento actualizado correctamente.")
        return redirect(reverse("backoffice:products:inventory:inventory_list"))


class InventoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Eliminar movimiento con validación de contraseña (solo Admin)."""
    permission_required = "products.delete_inventorymovement"
    model = InventoryMovement
    template_name = "backoffice/inventory/delete.html"
    success_url = reverse_lazy("backoffice:products:inventory:inventory_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Si ya se confirmó la advertencia, mostramos form de contraseña
        if self.request.POST.get("confirm_step") == "1":
            context["password_form"] = PasswordConfirmForm(user=self.request.user)
            context["confirm_step"] = True
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Paso 1 → mostrar advertencia + botón "Continuar"
        if "confirm_step" not in request.POST:
            context = self.get_context_data(object=self.object)
            context["confirm_step"] = True
            context["password_form"] = PasswordConfirmForm(user=request.user)
            return self.render_to_response(context)

        # Paso 2 → validar contraseña
        form = PasswordConfirmForm(user=request.user, data=request.POST)
        if not form.is_valid():
            context = self.get_context_data(object=self.object)
            context["password_form"] = form
            context["confirm_step"] = True
            return self.render_to_response(context)

        # ✅ Eliminar usando delete() del modelo (que ajusta stock)
        try:
            with transaction.atomic():
                AuditLog.log_action(
                    request=request,
                    action="Delete",
                    model=InventoryMovement,
                    obj=self.object,
                    description=(
                        f"Movimiento '{self.object.id}' "
                        f"({self.object.get_movement_type_display()}) "
                        f"sobre '{self.object.product.name}' eliminado"
                    )
                )
                response = super().delete(request, *args, **kwargs)
        except Exception as e:
            messages.error(request, f"Error al eliminar: {e}")
            return self.redirect_to_success_url()

        messages.success(request, "Movimiento eliminado correctamente.")
        return response

    def redirect_to_success_url(self):
        return redirect(self.success_url)


# ----------------------------
# Gestión operativa (productos / variantes / masivos)
# ----------------------------
from django.db.models import Q

class ProductsInventoryListView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Listado de productos para gestionar stock."""
    permission_required = "products.view_product"
    template_name = "backoffice/inventory/products_list_inventory.html"

    LOW_STOCK_THRESHOLD = 5

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        q = self.request.GET.get("q", "")
        stock_filter = self.request.GET.get("stock_filter", "")

        # Base queryset de productos
        qs = Product.objects.all()

        # Filtro por texto
        if q:
            qs = qs.filter(
                Q(name__unaccent_icontains=q) |
                Q(sku__unaccent_icontains=q) |
                Q(description__unaccent_icontains=q)
            )

        # Filtro por estado de stock
        if stock_filter == "with_stock":
            qs = qs.filter(
                Q(_stock__gt=0) | Q(variants__stock__gt=0)
            ).distinct()
        elif stock_filter == "low_stock":
            qs = qs.filter(
                Q(_stock__gt=0, _stock__lte=self.LOW_STOCK_THRESHOLD) |
                Q(variants__stock__gt=0, variants__stock__lte=self.LOW_STOCK_THRESHOLD)
            ).distinct()
        elif stock_filter == "no_stock":
            qs = qs.filter(
                Q(_stock__isnull=True) | Q(_stock__lte=0),
                Q(variants__stock__isnull=True) | Q(variants__stock__lte=0),
            ).distinct()

        qs = qs.order_by("name")

        # Reservas activas
        active_reservations = Reservation.objects.filter(status="active").values_list("id", flat=True)

        reserved_by_product = (
            InventoryMovement.objects.filter(
                movement_type="reserve",
                reservation_id__in=active_reservations,
                variant__isnull=True
            )
            .values("product_id")
            .annotate(reserved_qty=Sum("quantity"))
        )
        reserved_by_product = {r["product_id"]: r["reserved_qty"] for r in reserved_by_product}

        reserved_by_variant = (
            InventoryMovement.objects.filter(
                movement_type="reserve",
                reservation_id__in=active_reservations,
                variant__isnull=False
            )
            .values("variant_id")
            .annotate(reserved_qty=Sum("quantity"))
        )
        reserved_by_variant = {r["variant_id"]: r["reserved_qty"] for r in reserved_by_variant}

        # ✅ Total reservado por producto (producto + todas sus variantes)
        reserved_total_by_product = {}
        for product in qs:
            total_reserved = reserved_by_product.get(product.id, 0)
            for v in product.variants.all():
                total_reserved += reserved_by_variant.get(v.id, 0)
            if total_reserved > 0:
                reserved_total_by_product[product.id] = total_reserved

        # Conteo total de reservas (para la estadística global)
        reserved_count = sum(reserved_by_product.values()) + sum(reserved_by_variant.values())

        # Contexto principal
        ctx["products"] = qs
        ctx["query"] = q
        ctx["stock_filter"] = stock_filter
        ctx["reserved_by_product"] = reserved_by_product
        ctx["reserved_by_variant"] = reserved_by_variant
        ctx["reserved_total_by_product"] = reserved_total_by_product  # 👈 usar este en la tabla
        ctx["reserved_count"] = reserved_count

        # Estadísticas de inventario
        # Productos sin variantes
        productos_sin_variantes = Product.objects.filter(variants__isnull=True).distinct()

        with_stock_prod = productos_sin_variantes.filter(_stock__gt=0).count()
        low_stock_prod = productos_sin_variantes.filter(
            _stock__gt=0, _stock__lte=self.LOW_STOCK_THRESHOLD
        ).count()
        no_stock_prod = productos_sin_variantes.filter(
            Q(_stock__isnull=True) | Q(_stock__lte=0)
        ).count()

        # Variantes
        with_stock_var = ProductVariant.objects.filter(stock__gt=0).count()
        low_stock_var = ProductVariant.objects.filter(
            stock__gt=0, stock__lte=self.LOW_STOCK_THRESHOLD
        ).count()
        no_stock_var = ProductVariant.objects.filter(
            Q(stock__isnull=True) | Q(stock__lte=0)
        ).count()

        # Totales combinados
        ctx["products_with_stock"] = with_stock_prod + with_stock_var
        ctx["low_stock_count"] = low_stock_prod + low_stock_var
        ctx["no_stock_count"] = no_stock_prod + no_stock_var

        return ctx



class ProductVariantsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Vista de variantes de un producto específico."""
    permission_required = "products.view_product"
    template_name = "backoffice/inventory/product_variants_inventory.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = get_object_or_404(Product, pk=kwargs.get("pk"))
        ctx["product"] = product
        ctx["variants"] = product.variants.all()

        active_reservations = Reservation.objects.filter(status="active").values_list("id", flat=True)
        reserved_by_variant = (
            InventoryMovement.objects.filter(movement_type="reserve", reservation_id__in=active_reservations)
            .values("variant_id")
            .annotate(reserved_qty=Sum("quantity"))
        )
        ctx["reserved_by_variant"] = {r["variant_id"]: r["reserved_qty"] for r in reserved_by_variant}
        return ctx


class ProductVariantsJSONView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Retorna las variantes en JSON (para AJAX)."""
    permission_required = "products.view_product"

    def get(self, request, pk, *args, **kwargs):
        product = get_object_or_404(Product, pk=pk)
        variants = []
        for v in product.variants.all():
            label = ", ".join(filter(None, [v.size, v.color])) or (v.sku or f"Variante {v.id}")
            variants.append({"id": v.id, "label": label, "stock": v.stock})
        return JsonResponse({"variants": variants})


class InventoryCreateFromProductView(InventoryCreateView):
    """Crear movimiento de inventario desde un producto específico."""
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        product_id = self.request.GET.get("product")
        variant_id = self.request.GET.get("variant")
        if product_id:
            kwargs["product_id"] = product_id
        if variant_id:
            kwargs["variant_id"] = variant_id
        return kwargs


class BulkAddStockView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Acción masiva para productos sin variantes."""
    permission_required = "products.change_product"

    def post(self, request, *args, **kwargs):
        form = BulkAddStockForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Error en la acción masiva.")
            return redirect(request.META.get("HTTP_REFERER", reverse("backoffice:products:inventory:inventory_list")))

        product_ids = form.cleaned_data["product_ids"]
        qty = form.cleaned_data["quantity"]
        movement_type = form.cleaned_data["movement_type"]

        try:
            with transaction.atomic():
                for pid in product_ids:
                    product = Product.objects.select_for_update().get(pk=pid)

                    # Calcula precio unitario
                    computed_price = Decimal(product.price or 0).quantize(Decimal("0.01"))

                    InventoryMovement.objects.create(
                        product=product,
                        movement_type=movement_type,  # "in" o "adjust"
                        quantity=qty,
                        user=request.user,
                        unit_price=computed_price,
                        discount_percentage=Decimal("0.00"),
                    )

            messages.success(request, "Movimientos creados correctamente.")
        except Exception as e:
            messages.error(request, f"Error al crear movimientos: {e}")

        return redirect(reverse("backoffice:products:inventory:inventory_list"))


class BulkVariantsStockView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Acción masiva para variantes de un producto."""
    permission_required = "products.change_product"

    def post(self, request, *args, **kwargs):
        form = BulkVariantsStockForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Error en la acción masiva (variantes).")
            return redirect(
                request.META.get(
                    "HTTP_REFERER",
                    reverse("backoffice:products:inventory:product_variants", kwargs={"pk": form.data.get("product_id")})
                )
            )

        product_id = form.cleaned_data["product_id"]
        variant_ids = form.cleaned_data["variant_ids"]
        qty = form.cleaned_data["quantity"]
        movement_type = form.cleaned_data["movement_type"]

        try:
            with transaction.atomic():
                for vid in variant_ids:
                    variant = ProductVariant.objects.select_for_update().get(pk=vid)

                    # Calcula precio unitario: precio base + modificador de la variante
                    base_price = Decimal(variant.product.price or 0)
                    mod_price = Decimal(variant.price_modifier or 0)
                    computed_price = (base_price + mod_price).quantize(Decimal("0.01"))

                    InventoryMovement.objects.create(
                        product=variant.product,
                        variant=variant,
                        movement_type=movement_type,
                        quantity=qty,
                        user=request.user,
                        unit_price=computed_price,
                        discount_percentage=Decimal("0.00"),
                    )

            messages.success(request, "Movimientos creados correctamente sobre variantes.")
        except Exception as e:
            messages.error(request, f"Error al crear movimientos sobre variantes: {e}")

        return redirect(reverse("backoffice:products:inventory:product_variants", kwargs={"pk": product_id}))


class InventoryAdjustView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "products.add_inventorymovement"
    model = InventoryMovement
    form_class = InventoryAdjustmentForm
    template_name = "backoffice/inventory/adjust.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # ocultamos price y movement_type en la UI (se forzará movement_type=adjust)
        kwargs.update({
            "hide_price_fields": True,
            "hide_movement_type": True,
        })

        # Pasar product y variant desde GET
        product_id = self.request.GET.get("product")
        variant_id = self.request.GET.get("variant")
        if product_id:
            kwargs["product_id"] = product_id
        if variant_id:
            kwargs["variant_id"] = variant_id

        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.movement_type = "adjust"

        form.instance.unit_price = form.cleaned_data.get("unit_price", None)
        form.instance.discount_percentage = Decimal("0.00")

        with transaction.atomic():
            self.object = form.save()
            AuditLog.log_action(
                request=self.request,
                action="Create",
                model=InventoryMovement,
                obj=self.object,
                description=f"Ajuste de stock '{self.object.id}' sobre '{self.object.product.name}': {form.instance.adjust_reason}"
            )
        messages.success(self.request, "Ajuste de inventario registrado correctamente.")
        return redirect(reverse("backoffice:products:inventory:inventory_list"))
