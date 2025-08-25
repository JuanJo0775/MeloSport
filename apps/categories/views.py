from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Count
from django.db.models.functions import Cast
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate
from django.views.generic.base import TemplateView
from .models import Category, AbsoluteCategory
from ..products.models import Product
from django.db.models import CharField

class CategoryHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'backoffice/categories/index_categories.html'


# ===================== Utilidades =====================

def _has_products(obj):
    """Detecta productos asociados tolerando distintos related_name."""
    if hasattr(obj, "products"):
        return obj.products.exists()
    if hasattr(obj, "product_set"):
        return obj.product_set.exists()
    return False


# ===================== Jerárquicas (padre/hija) =====================

class CategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'categories.view_category'
    model = Category
    template_name = 'backoffice/categories/list.html'
    context_object_name = 'categorias'
    queryset = Category.objects.all().prefetch_related('children').order_by('tree_id', 'lft')


class CategoryDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = 'categories.view_category'
    model = Category
    template_name = 'backoffice/categories/detail.html'
    context_object_name = 'categoria'


class CategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'categories.add_category'
    model = Category
    fields = ['name', 'description', 'parent', 'is_active']
    template_name = 'backoffice/categories/create.html'
    success_url = reverse_lazy('categories:list')


class CategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'categories.change_category'
    model = Category
    fields = ['name', 'description', 'parent', 'is_active']
    template_name = 'backoffice/categories/update.html'
    success_url = reverse_lazy('categories:list')


class CategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Flujo de eliminación seguro:
      - GET: si tiene hijos o productos => paso 'warn' (aviso 1). Si no, va a 'confirm_password' directamente.
      - POST step=1: segundo aviso (más enfático) + campo contraseña.
      - POST step=2: valida contraseña y elimina.
    """
    permission_required = 'categories.delete_category'
    model = Category
    template_name = 'backoffice/categories/confirm_delete.html'
    success_url = reverse_lazy('categories:list')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        has_children = self.object.get_children().exists()
        has_products = _has_products(self.object)
        context = self.get_context_data(
            object=self.object,
            has_children=has_children,
            has_products=has_products,
            step='warn' if (has_children or has_products) else 'confirm_password'
        )
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        step = request.POST.get('confirm_step')

        if step == '1':
            # segundo aviso + password
            context = self.get_context_data(
                object=self.object,
                has_children=self.object.get_children().exists(),
                has_products=_has_products(self.object),
                step='confirm_password'
            )
            return self.render_to_response(context)

        if step == '2':
            password = request.POST.get('password') or ''
            user = request.user
            if not authenticate(username=user.get_username(), password=password):
                messages.error(request, "Contraseña incorrecta. No se pudo confirmar la eliminación.")
                context = self.get_context_data(
                    object=self.object,
                    has_children=self.object.get_children().exists(),
                    has_products=_has_products(self.object),
                    step='confirm_password'
                )
                return self.render_to_response(context)

            messages.success(request, "La categoría fue eliminada correctamente.")
            self.object.delete()
            return redirect(self.success_url)

        # Cancelado
        return redirect(self.success_url)


# ===================== Absolutas (deportes) =====================

class AbsoluteCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'categories.view_absolutecategory'
    model = AbsoluteCategory
    template_name = 'backoffice/absolute_categories/list.html'
    context_object_name = 'deportes'
    paginate_by = 20  # opcional

    def get_queryset(self):
        qs = AbsoluteCategory.objects.all()

        # 🔎 Búsqueda
        search = self.request.GET.get('search')
        if search:
            qs = qs.annotate(id_str=Cast("id", CharField()))
            qs = qs.filter(
                Q(nombre__icontains=search) |
                Q(descripcion__icontains=search) |
                Q(id_str__icontains=search)
            )

        # 🎚️ Filtrado por estado
        status = self.request.GET.get('status')
        if status == 'active':
            qs = qs.filter(activo=True)
        elif status == 'inactive':
            qs = qs.filter(activo=False)

        # Prefetch para contar productos sin queries extra
        return qs.annotate(product_count=Count('products'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Totales
        deportes = AbsoluteCategory.objects.all()
        context['deportes_activos'] = deportes.filter(activo=True).count()
        context['deportes_inactivos'] = deportes.filter(activo=False).count()

        # Total productos asociados a deportes
        context['total_productos'] = Product.objects.filter(
            absolute_category__in=deportes
        ).count()

        return context


class AbsoluteCategoryDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = 'categories.view_absolutecategory'
    model = AbsoluteCategory
    template_name = 'backoffice/absolute_categories/detail.html'
    context_object_name = 'deporte'
    queryset = AbsoluteCategory.objects.filter(activo=True).order_by('nombre')


class AbsoluteCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'categories.add_absolutecategory'
    model = AbsoluteCategory
    fields = ['nombre', 'descripcion', 'activo']
    template_name = 'backoffice/absolute_categories/create.html'
    success_url = reverse_lazy('categories:absolute_list')


class AbsoluteCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'categories.change_absolutecategory'
    model = AbsoluteCategory
    fields = ['nombre', 'descripcion', 'activo']
    template_name = 'backoffice/absolute_categories/update.html'
    success_url = reverse_lazy('categories:absolute_list')


class AbsoluteCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Mismo flujo de 2 avisos + contraseña.
    """
    permission_required = 'categories.delete_absolutecategory'
    model = AbsoluteCategory
    template_name = 'backoffice/absolute_categories/confirm_delete.html'
    success_url = reverse_lazy('categories:absolute_list')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # No hay jerarquía aquí; sólo productos
        has_products = _has_products(self.object)
        context = self.get_context_data(
            object=self.object,
            has_products=has_products,
            step='warn' if has_products else 'confirm_password'
        )
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        step = request.POST.get('confirm_step')

        if step == '1':
            context = self.get_context_data(
                object=self.object,
                has_products=_has_products(self.object),
                step='confirm_password'
            )
            return self.render_to_response(context)

        if step == '2':
            password = request.POST.get('password') or ''
            user = request.user
            if not authenticate(username=user.get_username(), password=password):
                messages.error(request, "Contraseña incorrecta. No se pudo confirmar la eliminación.")
                context = self.get_context_data(
                    object=self.object,
                    has_products=_has_products(self.object),
                    step='confirm_password'
                )
                return self.render_to_response(context)

            messages.success(request, "La categoría absoluta fue eliminada correctamente.")
            self.object.delete()
            return redirect(self.success_url)

        return redirect(self.success_url)

def absolute_activate(request, pk):
    deporte = get_object_or_404(AbsoluteCategory, pk=pk)
    deporte.activo = True
    deporte.save()
    messages.success(request, f"El deporte '{deporte.nombre}' ha sido activado correctamente.")
    return redirect("backoffice:categories:absolute_detail", pk=pk)


def absolute_deactivate(request, pk):
    deporte = get_object_or_404(AbsoluteCategory, pk=pk)
    deporte.activo = False
    deporte.save()
    messages.warning(request, f"El deporte '{deporte.nombre}' ha sido desactivado.")
    return redirect("backoffice:categories:absolute_detail", pk=pk)