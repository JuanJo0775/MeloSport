from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from apps.products.models import Product
from apps.categories.models import Category
from .serializers import ProductSerializer, CategorySerializer
from .filters import ProductFilter

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lectura pública de categorías (lista y detalle).
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name','description']
    ordering_fields = ['name','created_at']

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoints públicos: lista y detalle.
    Para operaciones de admin (crear/editar) puedes crear otro viewset protegido.
    """
    queryset = Product.objects.filter(status='active').prefetch_related('images','variants','categories').distinct()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name','description','sku']
    ordering_fields = ['price','created_at','name']
