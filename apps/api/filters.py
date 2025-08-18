import django_filters
from django_filters import rest_framework as filters
from apps.products.models import Product
from apps.categories.models import Category


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class ProductFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')

    # reemplazamos el categories actual
    categories = django_filters.CharFilter(method='filter_categories')
    absolute_categories = django_filters.CharFilter(method='filter_absolute_categories')

    in_stock = django_filters.BooleanFilter(method='filter_in_stock')

    class Meta:
        model = Product
        fields = ['has_variants', 'status', 'categories', 'absolute_categories']

    def filter_categories(self, queryset, name, value):
        """
        Filtra por IDs de categorías (padres o hijas).
        Si un ID es padre, incluye automáticamente sus hijas.
        """
        ids = [int(v) for v in value.split(',') if v.isdigit()]
        if not ids:
            return queryset

        hijos_ids = Category.objects.filter(parent_id__in=ids).values_list('id', flat=True)
        all_ids = set(ids) | set(hijos_ids)

        return queryset.filter(categories__id__in=all_ids).distinct()

    def filter_absolute_categories(self, queryset, name, value):
        """
        Filtra por IDs de categorías absolutas.
        """
        ids = [int(v) for v in value.split(',') if v.isdigit()]
        if not ids:
            return queryset

        return queryset.filter(absolute_category__id__in=ids).distinct()

    def filter_in_stock(self, queryset, name, value):
        """
        Filtra productos en stock o fuera de stock.
        """
        if value is True:
            return queryset.filter(total_stock__gt=0)  # cambia a stock__gt si tu modelo lo usa
        if value is False:
            return queryset.filter(total_stock__lte=0)
        return queryset
