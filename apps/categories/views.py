from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.shortcuts import redirect
from django.contrib import messages
from .models import Category, AbsoluteCategory
from django.views.generic import TemplateView

class CategoryHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'backoffice/categories/index_categories.html'

# 🔹 Categorías
class CategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'categories.view_category'
    model = Category
    template_name = 'backoffice/categories/list.html'
    context_object_name = 'categorias'

class CategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'categories.add_category'
    model = Category
    fields = ['name', 'description', 'parent', 'is_active']
    template_name = 'backoffice/categories/form.html'
    success_url = reverse_lazy('categories:list')

    def form_valid(self, form):
        form.instance.last_modified_by = self.request.user
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'categories.change_category'
    model = Category
    fields = ['name', 'description', 'parent', 'is_active']
    template_name = 'backoffice/categories/form.html'
    success_url = reverse_lazy('categories:list')

    def form_valid(self, form):
        form.instance.last_modified_by = self.request.user
        return super().form_valid(form)

class CategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'categories.delete_category'
    model = Category
    template_name = 'backoffice/categories/confirm_delete.html'
    success_url = reverse_lazy('categories:list')

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        # Validación: no permitir borrar si tiene hijos o productos
        if obj.get_children().exists() or obj.product_set.exists():
            messages.error(request, "No se puede eliminar porque tiene subcategorías o productos.")
            return redirect('categories:list')
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.last_modified_by = request.user
        obj.save()
        return super().delete(request, *args, **kwargs)

# 🔹 Deportes (Categorías absolutas)
class AbsoluteCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'categories.view_absolutecategory'
    model = AbsoluteCategory
    template_name = 'backoffice/absolute_categories/list.html'
    context_object_name = 'deportes'

class AbsoluteCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'categories.add_absolutecategory'
    model = AbsoluteCategory
    fields = ['nombre', 'descripcion', 'activo']
    template_name = 'backoffice/absolute_categories/form.html'
    success_url = reverse_lazy('categories:absolute_list')

    def form_valid(self, form):
        form.instance.last_modified_by = self.request.user
        return super().form_valid(form)

class AbsoluteCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'categories.change_absolutecategory'
    model = AbsoluteCategory
    fields = ['nombre', 'descripcion', 'activo']
    template_name = 'backoffice/absolute_categories/form.html'
    success_url = reverse_lazy('categories:absolute_list')

    def form_valid(self, form):
        form.instance.last_modified_by = self.request.user
        return super().form_valid(form)

class AbsoluteCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'categories.delete_absolutecategory'
    model = AbsoluteCategory
    template_name = 'backoffice/absolute_categories/confirm_delete.html'
    success_url = reverse_lazy('categories:absolute_list')

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.product_set.exists():
            messages.error(request, "No se puede eliminar porque tiene productos asociados.")
            return redirect('categories:absolute_list')
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.last_modified_by = request.user
        obj.save()
        return super().delete(request, *args, **kwargs)
