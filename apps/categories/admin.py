from django.contrib import admin
from django.db import models
from mptt.admin import DraggableMPTTAdmin
from .models import Category
from .models import AbsoluteCategory


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    mptt_level_indent = 20
    list_display = ('tree_actions', 'indented_title', 'active_product_count', 'is_active')
    list_display_links = ('indented_title',)
    list_filter = ('is_active',)
    search_fields = ('name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Opción 1: Contar todos los productos
        return qs.annotate(
            _product_count=models.Count('products', distinct=True)
        )

    def active_product_count(self, obj):
        # Filtrar por el campo 'status' que sí existe en tu modelo
        return obj.products.filter(status='active').count()

    active_product_count.short_description = "Productos Activos"

    @admin.action(description="Activar categorías seleccionadas")
    def activate_categories(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} categorías activadas.")

    @admin.action(description="Desactivar categorías seleccionadas")
    def deactivate_categories(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} categorías desactivadas.")

@admin.register(AbsoluteCategory)
class AbsoluteCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'descripcion', 'activo', 'get_product_count')
    list_filter = ('activo',)
    search_fields = ('nombre',)
    actions = ['activar_categorias', 'desactivar_categorias']

    @admin.action(description="Activar categorías seleccionadas")
    def activar_categorias(self, request, queryset):
        queryset.update(activo=True)
        self.message_user(request, f"{queryset.count()} categorías activadas.")

    @admin.action(description="Desactivar categorías seleccionadas")
    def desactivar_categorias(self, request, queryset):
        queryset.update(activo=False)
        self.message_user(request, f"{queryset.count()} categorías desactivadas.")
