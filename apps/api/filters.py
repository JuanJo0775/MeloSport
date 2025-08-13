# apps/api/filters.py
import django_filters
from django_filters import rest_framework as filters
from apps.products.models import Product

class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass

class ProductFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    categories = NumberInFilter(field_name='categories__id', lookup_expr='in')  # <-- multi
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')

    class Meta:
        model = Product
        fields = ['has_variants', 'status', 'categories']
