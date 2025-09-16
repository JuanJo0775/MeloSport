# apps/billing/mixins.py
from django.core.paginator import Paginator
from django.db.models import Q
from itertools import chain

from apps.products.models import Product


class ProductCatalogMixin:
    """Mixin para manejar catálogo de productos con filtros y paginación."""

    paginate_by = 12  # default, se puede sobreescribir en la view

    def get_base_queryset(self):
        """Queryset base de productos activos con relaciones necesarias."""
        return Product.objects.filter(status="active").prefetch_related("variants", "images")

    def filter_queryset(self, qs):
        """Aplica filtros de búsqueda, tipo y stock."""
        request = self.request
        q = request.GET.get("q", "").strip()
        filter_type = request.GET.get("type", "all")
        stock_filter = request.GET.get("stock", "in_stock")

        # 🔎 búsqueda parcial
        if q:
            qs = qs.filter(
                Q(name__unaccent_icontains=q) |
                Q(sku__unaccent_icontains=q) |
                Q(description__unaccent_icontains=q)
            ).distinct()

        # separar simples y variantes (con distinct para evitar duplicados)
        simples = qs.filter(variants__isnull=True).order_by("name").distinct()
        variantes = qs.filter(variants__isnull=False).order_by("name").distinct()

        # 🔎 filtro por tipo
        if filter_type == "simple":
            final_qs = simples
        elif filter_type == "variants":
            final_qs = variantes
        else:
            # concatenamos simples primero y luego variantes
            final_qs = list(chain(simples, variantes))

        # 🔎 filtro de stock disponible (aplicado en memoria si ya concatenamos)
        if stock_filter == "in_stock":
            final_qs = [
                p for p in final_qs
                if (not p.variants.exists() and (p._stock or 0) > 0) or
                   any((v.stock or 0) > 0 for v in p.variants.all())
            ]

        return final_qs

    def get_queryset(self):
        """Hook principal para obtener el queryset filtrado."""
        qs = self.get_base_queryset()
        return self.filter_queryset(qs)

    def paginate_queryset(self, qs):
        """Aplica paginación y devuelve objetos listos para el contexto."""
        if not isinstance(qs, list):
            qs = list(qs)  # asegurar lista para chain
        paginator = Paginator(qs, self.paginate_by)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        return page_obj, paginator

    def get_catalog_context(self):
        """Devuelve contexto estándar del catálogo de productos."""
        qs = self.get_queryset()
        page_obj, paginator = self.paginate_queryset(qs)

        qs_copy = self.request.GET.copy()
        if "page" in qs_copy:
            qs_copy.pop("page")

        return {
            "products": page_obj,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "paginator": paginator,
            "current_q": self.request.GET.get("q", ""),
            "current_filter_type": self.request.GET.get("type", "all"),
            "current_stock_filter": self.request.GET.get("stock", "in_stock"),
            "querystring": qs_copy.urlencode(),
        }
