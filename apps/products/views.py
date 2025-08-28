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

from apps.api.filters import ProductFilter
from apps.products.models import Product, ProductVariant, ProductImage
from apps.products.forms import ProductForm, ProductVariantForm, ProductImageForm
from apps.users.models import AuditLog
from .serializers import ProductSerializer


# Formset para imágenes (se usa en create/update)
ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    fields=('image', 'is_main', 'order'),
    extra=0,
    can_delete=True
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
        images_rel = getattr(self.object, "images", None) or getattr(self.object, "productimage_set", None)
        context["images"] = images_rel.all() if images_rel else []
        context["variants"] = ProductVariant.objects.filter(product=self.object)
        context["variant_form"] = ProductVariantForm()
        return context


class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "products.add_product"
    model = Product
    form_class = ProductForm
    template_name = "backoffice/products/create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadir image_formset (bind si es POST)
        if self.request.method == "POST":
            context["image_formset"] = ProductImageFormSet(self.request.POST, self.request.FILES)
        else:
            context["image_formset"] = ProductImageFormSet()
        return context

    def form_valid(self, form):
        # Obtenemos formset desde contexto (estará bind si vinimos por POST)
        image_formset = self.get_context_data().get("image_formset")

        # Guardado atómico: producto + imágenes
        with transaction.atomic():
            self.object = form.save()

            # Guardar imágenes si el formset es válido
            if image_formset and image_formset.is_valid():
                image_formset.instance = self.object
                image_formset.save()
            elif image_formset and not image_formset.is_valid():
                # Re-render con errores del formset
                return self.form_invalid(form)

            # Auditoría
            AuditLog.log_action(
                request=self.request,
                action="create",
                model=self.model,
                obj=self.object,
                description=f"Producto '{self.object.name}' creado"
            )

        # Si tiene variantes vamos al detalle para que el usuario agregue variantes
        if self.object.has_variants:
            messages.info(self.request, "Producto creado. Ahora puede agregar sus variantes.")
            return redirect("products:product_detail", pk=self.object.pk)

        messages.success(self.request, "Producto creado correctamente.")
        return redirect("products:product_list")

    def form_invalid(self, form):
        # Re-render con form y formset (si existe)
        context = self.get_context_data(form=form)
        # si no existía image_formset en contexto (p. ej. error no-POST), creadla ahora bind a POST
        if "image_formset" not in context:
            context["image_formset"] = ProductImageFormSet(self.request.POST or None, self.request.FILES or None)
        return self.render_to_response(context)


class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "products.change_product"
    model = Product
    form_class = ProductForm
    template_name = "backoffice/products/update.html"
    success_url = reverse_lazy("products:product_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # image formset bound a la instancia del producto
        if self.request.method == "POST":
            context["image_formset"] = ProductImageFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context["image_formset"] = ProductImageFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        image_formset = self.get_context_data().get("image_formset")

        with transaction.atomic():
            response = super().form_valid(form)  # guarda self.object
            # guardar formset de imágenes
            if image_formset and image_formset.is_valid():
                image_formset.instance = self.object
                image_formset.save()
            elif image_formset and not image_formset.is_valid():
                return self.form_invalid(form)

            # Auditoría
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
    success_url = reverse_lazy("products:product_list")

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
        # comprobar que el product existe antes de mostrar el formulario
        self.product = get_object_or_404(Product, pk=self.kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        # si queremos prellenar algo basándonos en el producto padre, hacerlo aquí
        return {}

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
        return reverse("products:product_detail", kwargs={"pk": self.product.pk})


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
        return reverse("products:product_detail", kwargs={"pk": self.object.product.pk})


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
        return reverse("products:product_detail", kwargs={"pk": self.object.product.pk})


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

    return redirect("products:product_detail", pk=product.pk)
