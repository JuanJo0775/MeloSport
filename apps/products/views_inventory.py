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
from .forms_inventory import InventoryMovementForm, BulkAddStockForm, BulkVariantsStockForm


# ----------------------------
# Index de Inventario (antesala)
# ----------------------------
class InventoryIndexView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Página inicial de Inventario (antesala sin tablas)."""
    permission_required = "products.view_inventorymovement"
    template_name = "backoffice/inventory/index_inventario.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
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
            q &= Q(user_id=u)
        if df := self.request.GET.get("date_from"):
            q &= Q(created_at__date__gte=df)
        if dt := self.request.GET.get("date_to"):
            q &= Q(created_at__date__lte=dt)
        return qs.filter(q).order_by("-created_at")


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
        return redirect(reverse("backoffice:products:inventory:inventory_list"))


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
    """Eliminar movimiento (solo Admin)."""
    permission_required = "products.delete_inventorymovement"
    model = InventoryMovement
    template_name = "backoffice/inventory/delete.html"
    success_url = reverse_lazy("backoffice:products:inventory:inventory_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            with transaction.atomic():
                signed = self.object._signed_qty()
                if self.object.variant_id:
                    variant = ProductVariant.objects.select_for_update().get(pk=self.object.variant_id)
                    new_stock = variant.stock - signed
                    if new_stock < 0:
                        messages.error(request, "No se puede eliminar: stock negativo en variante.")
                        return redirect(self.success_url)
                    variant.stock = new_stock
                    variant.save(update_fields=["stock"])
                else:
                    product = Product.objects.select_for_update().get(pk=self.object.product_id)
                    new_stock = product._stock - signed
                    if new_stock < 0:
                        messages.error(request, "No se puede eliminar: stock negativo en producto.")
                        return redirect(self.success_url)
                    product._stock = new_stock
                    product.save(update_fields=["_stock"])

                AuditLog.log_action(
                    request=request,
                    action="Delete",
                    model=InventoryMovement,
                    obj=self.object,
                    description=f"Movimiento '{self.object.id}' ({self.object.get_movement_type_display()}) sobre '{self.object.product.name}' eliminado"
                )
                response = super().delete(request, *args, **kwargs)
        except Exception as e:
            messages.error(request, f"Error al eliminar: {e}")
            return redirect(self.success_url)

        messages.success(request, "Movimiento eliminado correctamente.")
        return response


# ----------------------------
# Gestión operativa (productos / variantes / masivos)
# ----------------------------
class ProductsInventoryListView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Listado de productos para gestionar stock."""
    permission_required = "products.view_product"
    template_name = "backoffice/inventory/products_list_inventory.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "")
        qs = Product.objects.all()
        if q:
            qs = qs.filter(name__icontains=q)
        ctx["products"] = qs.order_by("name")
        ctx["query"] = q
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

        with transaction.atomic():
            for pid in product_ids:
                product = Product.objects.select_for_update().get(pk=pid)
                InventoryMovement.objects.create(
                    product=product,
                    movement_type=movement_type,
                    quantity=qty,
                    user=request.user
                )
        messages.success(request, "Movimientos creados correctamente.")
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

        with transaction.atomic():
            for vid in variant_ids:
                variant = ProductVariant.objects.select_for_update().get(pk=vid)
                InventoryMovement.objects.create(
                    product_id=product_id,
                    variant=variant,
                    movement_type=movement_type,
                    quantity=qty,
                    user=request.user
                )
        messages.success(request, "Movimientos creados correctamente sobre variantes.")
        return redirect(reverse("backoffice:products:inventory:product_variants", kwargs={"pk": product_id}))
