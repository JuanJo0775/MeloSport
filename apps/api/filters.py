import django_filters
from apps.products.models import Product
from apps.categories.models import Category

class ProductFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = django_filters.ModelChoiceFilter(field_name='categories', queryset=Category.objects.all())
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')

    class Meta:
        model = Product
        fields = ['has_variants', 'status']

    def filter_in_stock(self, queryset, name, value):
        if value:
            # productos con stock manual >0 o variantes con stock >0
            return queryset.filter(_stock__gt=0) | queryset.filter(variants__stock__gt=0)
        return queryset
