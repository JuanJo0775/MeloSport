# apps/products/views.py
from decimal import Decimal, InvalidOperation
from django.db.models import Q, Count
from django.contrib.auth import authenticate
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView
)
from django_filters.views import FilterView
from rest_framework import viewsets
from django.forms import inlineformset_factory
from django.db import transaction
from django.views.decorators.http import require_POST

from apps.api.filters import ProductFilter
from apps.products.models import Product, ProductVariant, ProductImage
from apps.products.forms import ProductForm, ProductVariantForm, ProductImageForm, ConfirmDeleteForm, BaseProductImageFormSet

from apps.users.models import AuditLog
from .serializers import ProductSerializer


# ================================
# Formsets helpers
# ================================
ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    formset=BaseProductImageFormSet,
    extra=1,
    can_delete=True,
)


def make_product_variant_formset(request, **kwargs):
    """Factory dinámico para variantes según permisos del usuario."""
    extra_forms = 1 if request.user.has_perm("products.add_productvariant") else 0
    can_delete = request.user.has_perm("products.delete_productvariant")

    return inlineformset_factory(
        Product,
        ProductVariant,
        form=ProductVariantForm,
        extra=extra_forms,
        can_delete=can_delete,
        fields=("size", "color", "price_modifier", "stock", "is_active"),
        **kwargs,
    )


# ================================
# API (solo lectura)
# ================================
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint que permite ver los productos con filtros."""
    queryset = Product.objects.all().order_by("-created_at")
    serializer_class = ProductSerializer


# ================================
# PRODUCTO VIEWS (Backoffice)
# ================================
class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "products.view_product"
    model = Product
    template_name = "backoffice/products/list.html"
    context_object_name = "products"
    paginate_by = 25  # ajusta si quieres

    def get_queryset(self):
        qs = Product.objects.all().prefetch_related("variants", "images")
        request = self.request

        q = request.GET.get("q", "").strip()
        price_min = request.GET.get("price_min")
        price_max = request.GET.get("price_max")
        has_variants = request.GET.get("has_variants")
        status = request.GET.get("status")

        if q:
            qs = qs.filter(
                Q(name__unaccent_icontains=q) |
                Q(sku__unaccent_icontains=q)
            )

        # Precios
        if price_min:
            try:
                pm = Decimal(price_min)
                qs = qs.filter(price__gte=pm)
            except (InvalidOperation, ValueError):
                pass
        if price_max:
            try:
                pM = Decimal(price_max)
                qs = qs.filter(price__lte=pM)
            except (InvalidOperation, ValueError):
                pass

        # Variantes
        qs = qs.annotate(_variant_count=Count("variants", distinct=True))
        if has_variants == "true":
            qs = qs.filter(_variant_count__gt=0)
        elif has_variants == "false":
            qs = qs.filter(_variant_count__lte=0)

        # Estado
        if status:
            qs = qs.filter(status=status)

        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs_filtered = self.object_list

        context["productos_activos"] = qs_filtered.filter(status="active").count()
        context["productos_inactivos"] = qs_filtered.filter(status="inactive").count()
        context["variantes_count"] = ProductVariant.objects.filter(
            product__in=qs_filtered.values_list("pk", flat=True)
        ).count()
        context["imagenes_count"] = ProductImage.objects.filter(
            product__in=qs_filtered.values_list("pk", flat=True)
        ).count()

        # Mantener querystring en la paginación
        qs = self.request.GET.copy()
        if "page" in qs:
            qs.pop("page")
        context["querystring"] = qs.urlencode()
        return context


class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "products.view_product"
    model = Product
    template_name = "backoffice/products/detail.html"
    context_object_name = "product"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # imágenes
        images_rel = getattr(self.object, "images", None) or getattr(self.object, "productimage_set", None)
        context["images"] = images_rel.all() if images_rel else []

        # variantes
        context["variants"] = self.object.variants.all()

        # formset variantes
        VariantFormSet = make_product_variant_formset(self.request)
        if self.request.method == "POST":
            context["variant_formset"] = VariantFormSet(self.request.POST, instance=self.object)
        else:
            context["variant_formset"] = VariantFormSet(instance=self.object)

        # form rápido de variante
        context["variant_form"] = ProductVariantForm()

        return context


class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "products.add_product"
    model = Product
    form_class = ProductForm
    template_name = "backoffice/products/create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prefix = "images"
        if self.request.method == "POST":
            context["image_formset"] = ProductImageFormSet(self.request.POST, self.request.FILES, prefix=prefix)
        else:
            context["image_formset"] = ProductImageFormSet(prefix=prefix)
        return context

    def form_valid(self, form):
        image_formset = self.get_context_data().get("image_formset")

        with transaction.atomic():
            self.object = form.save()
            if image_formset and image_formset.is_valid():
                image_formset.instance = self.object
                image_formset.save()
            elif image_formset and not image_formset.is_valid():
                return self.form_invalid(form)

            AuditLog.log_action(
                request=self.request,
                action="Create",
                model=self.model,
                obj=self.object,
                description=f"Producto '{self.object.name}' creado",
            )

        if self.object.has_variants:
            messages.info(self.request, "Producto creado. Ahora puede agregar sus variantes.")
            return redirect("backoffice:products:product_detail", pk=self.object.pk)

        messages.success(self.request, "Producto creado correctamente.")
        return redirect("backoffice:products:product_list")

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        if "image_formset" not in context:
            context["image_formset"] = ProductImageFormSet(self.request.POST or None, self.request.FILES or None)
        return self.render_to_response(context)


class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "products.change_product"
    model = Product
    form_class = ProductForm
    template_name = "backoffice/products/update.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prefix = "images"
        # cuando venga POST, construimos formset con POST+FILES para mostrar errores
        if self.request.method == "POST":
            context["image_formset"] = ProductImageFormSet(
                self.request.POST, self.request.FILES, instance=self.object, prefix=prefix
            )
        else:
            context["image_formset"] = ProductImageFormSet(instance=self.object, prefix=prefix)
        return context

    def form_valid(self, form):
        """
        Guardamos el producto primero (para tener PK), luego validamos y guardamos el formset.
        Si el formset falla, devolvemos el template con errores.
        """
        prefix = "images"

        with transaction.atomic():
            # guardar los cambios del producto (self.object queda disponible)
            self.object = form.save()

            # construimos el formset con POST+FILES contra la instancia ya guardada
            image_formset = ProductImageFormSet(
                self.request.POST or None, self.request.FILES or None, instance=self.object, prefix=prefix
            )

            if image_formset.is_valid():
                image_formset.save()
            else:
                # Si es inválido, hacemos rollback y re-renderizamos con los errores del formset
                transaction.set_rollback(True)
                context = self.get_context_data(form=form)
                context["image_formset"] = image_formset  # formset con errores
                return self.render_to_response(context)

            # Audit log
            AuditLog.log_action(
                request=self.request,
                action="Update",
                model=self.model,
                obj=self.object,
                description=f"Producto '{self.object.name}' actualizado",
            )

        messages.success(self.request, "Producto actualizado correctamente.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        # get_context_data ya añade image_formset (POST), así que solo aseguramos que exista
        context = self.get_context_data(form=form)
        if "image_formset" not in context:
            context["image_formset"] = ProductImageFormSet(
                self.request.POST or None, self.request.FILES or None, instance=self.object
            )
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse("backoffice:products:product_detail", args=[self.object.pk])


class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "products.delete_product"
    model = Product
    template_name = "backoffice/products/confirm_delete.html"
    success_url = reverse_lazy("backoffice:products:product_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "form" not in context:
            context["form"] = ConfirmDeleteForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = ConfirmDeleteForm(request.POST)

        if form.is_valid():
            password = form.cleaned_data["password"]
            user = authenticate(username=request.user.username, password=password)
            if user:
                nombre = self.object.name
                response = super().delete(request, *args, **kwargs)
                AuditLog.log_action(
                    request=request,
                    action="Delete",
                    model=self.model,
                    obj=self.object,
                    description=f"Producto '{nombre}' eliminado",
                )
                messages.success(request, "Producto eliminado correctamente.")
                return response
            else:
                messages.error(request, "Contraseña incorrecta. Intenta nuevamente.")
                return redirect("backoffice:products:product_confirm_delete", pk=self.object.pk)

        messages.error(request, "Debes confirmar la contraseña para eliminar.")
        return self.render_to_response(self.get_context_data(form=form))


# ================================
# VARIANTE VIEWS (Backoffice)
# ================================
class VariantListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "products.view_productvariant"
    model = ProductVariant
    template_name = "backoffice/products/variant_list.html"
    context_object_name = "variants"
    paginate_by = 20

    def get_queryset(self):
        product = get_object_or_404(Product, pk=self.kwargs["pk"])
        return ProductVariant.objects.filter(product=product)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product"] = get_object_or_404(Product, pk=self.kwargs["pk"])
        return context


class VariantDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "products.view_productvariant"
    model = ProductVariant
    template_name = "backoffice/products/variant_detail.html"
    context_object_name = "variant"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product"] = self.object.product
        return context


class VariantCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "products.add_productvariant"
    model = ProductVariant
    form_class = ProductVariantForm
    template_name = "backoffice/products/variant_create.html"

    def dispatch(self, request, *args, **kwargs):
        self.product = get_object_or_404(Product, pk=self.kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.product = self.product
        response = super().form_valid(form)
        AuditLog.log_action(
            request=self.request,
            action="Create",
            model=self.model,
            obj=self.object,
            description=f"Variante '{self.object.sku}' creada para producto '{self.product.name}'",
        )
        messages.success(self.request, "Variante creada correctamente.")
        return response

    def get_success_url(self):
        return reverse("backoffice:products:product_detail", kwargs={"pk": self.product.pk})


class VariantUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "products.change_productvariant"
    model = ProductVariant
    form_class = ProductVariantForm
    template_name = "backoffice/products/variant_update.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditLog.log_action(
            request=self.request,
            action="Update",
            model=self.model,
            obj=self.object,
            description=f"Variante '{self.object.sku}' actualizada",
        )
        messages.success(self.request, "Variante actualizada correctamente.")
        return response

    def get_success_url(self):
        return reverse("backoffice:products:product_detail", kwargs={"pk": self.object.product.pk})


class VariantDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "products.delete_productvariant"
    model = ProductVariant
    template_name = "backoffice/products/variant_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "form" not in context:
            context["form"] = ConfirmDeleteForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = ConfirmDeleteForm(request.POST)

        if form.is_valid():
            password = form.cleaned_data["password"]
            user = authenticate(username=request.user.username, password=password)
            if user:
                sku = self.object.sku
                product = self.object.product
                response = super().delete(request, *args, **kwargs)
                AuditLog.log_action(
                    request=request,
                    action="Delete",
                    model=self.model,
                    obj=self.object,
                    description=f"Variante '{sku}' eliminada del producto '{product.name}'",
                )
                messages.success(request, "Variante eliminada correctamente.")
                return response
            else:
                messages.error(request, "Contraseña incorrecta. Intenta nuevamente.")
                return redirect("backoffice:products:variant_confirm_delete", pk=self.object.pk)

        messages.error(request, "Debes confirmar la contraseña para eliminar.")
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse("backoffice:products:product_detail", kwargs={"pk": self.object.product.pk})


# ================================
# GESTIÓN INLINE DE VARIANTES EN PRODUCT DETAIL
# ================================
@require_POST
def product_variants_manage(request, pk):
    product = get_object_or_404(Product, pk=pk)
    VariantFormSet = make_product_variant_formset(request)
    formset = VariantFormSet(request.POST, instance=product)

    if formset.is_valid():
        formset.save()
        AuditLog.log_action(
            request=request,
            action="Update",
            model=ProductVariant,
            obj=product,
            description=f"Variantes de producto '{product.name}' gestionadas desde detalle",
        )
        messages.success(request, "Variantes actualizadas correctamente.")
    else:
        print("Errores en variantes:", formset.errors)
        messages.error(request, "Error al actualizar variantes. Revise los formularios.")

    return redirect("backoffice:products:product_detail", pk=product.pk)


# ================================
# CREAR VARIANTE RÁPIDA (inline desde product detail)
# ================================
def variant_quick_create(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        form = ProductVariantForm(request.POST)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.product = product
            variant.save()
            AuditLog.log_action(
                request=request,
                action="Create",
                model=ProductVariant,
                obj=variant,
                description=f"Variante rápida '{variant.sku}' creada para producto '{product.name}'",
            )
            messages.success(request, "Variante creada correctamente.")
        else:
            messages.error(request, "Error al crear variante. Verifique el formulario.")

    return redirect("backoffice:products:product_detail", pk=product.pk)
