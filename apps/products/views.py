# apps/products/views.py
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
from apps.products.forms import ProductForm, ProductVariantForm, ProductImageForm
from apps.users.models import AuditLog
from .serializers import ProductSerializer


# ================================
# Formsets
# ================================
ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    fields=("image", "is_main", "order"),
    extra=0,
    can_delete=True
)

ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    extra=1,
    can_delete=True,
    fields=("size", "color", "price_modifier", "stock", "is_active"),  # 👈 declaramos explícitamente
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
class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    permission_required = "products.view_product"
    model = Product
    template_name = "backoffice/products/list.html"
    context_object_name = "products"
    filterset_class = ProductFilter
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # añadir thumbnails seguros para la lista
        for product in context.get("products", []):
            images_rel = getattr(product, "images", None) or getattr(product, "productimage_set", None)
            product._thumbs = images_rel.all() if images_rel else []
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

        # variantes existentes
        context["variants"] = self.object.variants.all()

        # formset de variantes (para edición en bloque)
        if self.request.method == "POST":
            context["variant_formset"] = ProductVariantFormSet(self.request.POST, instance=self.object)
        else:
            context["variant_formset"] = ProductVariantFormSet(instance=self.object)

        # formulario rápido (para añadir una variante desde el detalle)
        context["variant_form"] = ProductVariantForm()

        return context


class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "products.add_product"
    model = Product
    form_class = ProductForm
    template_name = "backoffice/products/create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            context["image_formset"] = ProductImageFormSet(self.request.POST, self.request.FILES)
        else:
            context["image_formset"] = ProductImageFormSet()
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
                action="create",
                model=self.model,
                obj=self.object,
                description=f"Producto '{self.object.name}' creado"
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
    success_url = reverse_lazy("backoffice:products:product_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            context["image_formset"] = ProductImageFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context["image_formset"] = ProductImageFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        image_formset = self.get_context_data().get("image_formset")

        with transaction.atomic():
            response = super().form_valid(form)
            if image_formset and image_formset.is_valid():
                image_formset.instance = self.object
                image_formset.save()
            elif image_formset and not image_formset.is_valid():
                return self.form_invalid(form)

            AuditLog.log_action(
                request=self.request,
                action="update",
                model=self.model,
                obj=self.object,
                description=f"Producto '{self.object.name}' actualizado"
            )

        messages.success(self.request, "Producto actualizado correctamente.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        if "image_formset" not in context:
            context["image_formset"] = ProductImageFormSet(self.request.POST or None, self.request.FILES or None, instance=self.object)
        return self.render_to_response(context)


class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "products.delete_product"
    model = Product
    template_name = "backoffice/products/confirm_delete.html"
    success_url = reverse_lazy("backoffice:products:product_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        nombre = self.object.name
        response = super().delete(request, *args, **kwargs)
        AuditLog.log_action(
            request=request,
            action="delete",
            model=self.model,
            obj=self.object,
            description=f"Producto '{nombre}' eliminado"
        )
        messages.success(request, "Producto eliminado correctamente.")
        return response


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
            action="create",
            model=self.model,
            obj=self.object,
            description=f"Variante '{self.object.sku}' creada para producto '{self.product.name}'"
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
            action="update",
            model=self.model,
            obj=self.object,
            description=f"Variante '{self.object.sku}' actualizada"
        )
        messages.success(self.request, "Variante actualizada correctamente.")
        return response

    def get_success_url(self):
        return reverse("backoffice:products:product_detail", kwargs={"pk": self.object.product.pk})


class VariantDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "products.delete_productvariant"
    model = ProductVariant
    template_name = "backoffice/products/variant_confirm_delete.html"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        sku = self.object.sku
        product = self.object.product
        response = super().delete(request, *args, **kwargs)
        AuditLog.log_action(
            request=request,
            action="delete",
            model=self.model,
            obj=self.object,
            description=f"Variante '{sku}' eliminada del producto '{product.name}'"
        )
        messages.success(request, "Variante eliminada correctamente.")
        return response

    def get_success_url(self):
        return reverse("backoffice:products:product_detail", kwargs={"pk": self.object.product.pk})


# ================================
# GESTIÓN INLINE DE VARIANTES EN PRODUCT DETAIL
# ================================
@require_POST
def product_variants_manage(request, pk):
    product = get_object_or_404(Product, pk=pk)
    formset = ProductVariantFormSet(request.POST, instance=product)

    if formset.is_valid():
        formset.save()
        AuditLog.log_action(
            request=request,
            action="update",
            model=ProductVariant,
            obj=product,
            description=f"Variantes de producto '{product.name}' gestionadas desde detalle"
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
                action="create",
                model=ProductVariant,
                obj=variant,
                description=f"Variante rápida '{variant.sku}' creada para producto '{product.name}'"
            )
            messages.success(request, "Variante creada correctamente.")
        else:
            messages.error(request, "Error al crear variante. Verifique el formulario.")

    return redirect("backoffice:products:product_detail", pk=product.pk)
