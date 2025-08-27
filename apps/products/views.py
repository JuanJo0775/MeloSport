from rest_framework import viewsets
from .models import Product
from .serializers import ProductSerializer
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from .models import Product, ProductVariant
from apps.users.models import AuditLog

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint que permite ver los productos.
    """
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer

# ================================
# PRODUCTO VIEWS
# ================================

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "products.view_product"
    model = Product
    template_name = "backoffice/products/list.html"
    context_object_name = "products"


class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "products.view_product"
    model = Product
    template_name = "backoffice/products/detail.html"
    context_object_name = "product"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["variants"] = ProductVariant.objects.filter(product=self.object)
        return context


class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "products.add_product"
    model = Product
    fields = ["sku", "name", "description", "price"]
    template_name = "backoffice/products/create.html"
    success_url = reverse_lazy("products:product_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditLog.log_action(
            request=self.request,
            action="create",
            model=self.model,
            obj=self.object,
            description=f"Producto '{self.object.name}' creado"
        )
        messages.success(self.request, "Producto creado correctamente.")
        return response


class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "products.change_product"
    model = Product
    fields = ["sku", "name", "description", "price"]
    template_name = "backoffice/products/update.html"
    success_url = reverse_lazy("products:product_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditLog.log_action(
            request=self.request,
            action="update",
            model=self.model,
            obj=self.object,
            description=f"Producto '{self.object.name}' actualizado"
        )
        messages.success(self.request, "Producto actualizado correctamente.")
        return response


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
# VARIANTE VIEWS
# ================================

class VariantListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "products.view_productvariant"
    model = ProductVariant
    template_name = "backoffice/products/variant_list.html"
    context_object_name = "variants"

    def get_queryset(self):
        product = get_object_or_404(Product, pk=self.kwargs["pk"])
        return ProductVariant.objects.filter(product=product)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product"] = get_object_or_404(Product, pk=self.kwargs["pk"])
        return context


class VariantCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "products.add_productvariant"
    model = ProductVariant
    fields = ["sku", "size", "color", "price_modifier", "stock"]
    template_name = "backoffice/products/variant_create.html"

    def form_valid(self, form):
        product = get_object_or_404(Product, pk=self.kwargs["pk"])
        form.instance.product = product
        response = super().form_valid(form)
        AuditLog.log_action(
            request=self.request,
            action="create",
            model=self.model,
            obj=self.object,
            description=f"Variante '{self.object.sku}' creada para producto '{product.name}'"
        )
        messages.success(self.request, "Variante creada correctamente.")
        return response

    def get_success_url(self):
        return reverse("products:variant_list", kwargs={"pk": self.kwargs["pk"]})


class VariantUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "products.change_productvariant"
    model = ProductVariant
    fields = ["sku", "size", "color", "price_modifier", "stock"]
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