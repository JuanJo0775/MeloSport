from rest_framework import viewsets, mixins
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.throttling import AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend

from apps.products.models import Product
from apps.categories.models import Category
from apps.frontend.models import FeaturedProductCarousel, ContactMessage

from .serializers import (
    ProductSerializer,
    CategorySerializer,
    CarouselItemSerializer,
    ContactoSerializer
)
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

class CarouselViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoint público para mostrar los elementos activos del carrusel.
    """
    queryset = FeaturedProductCarousel.objects.filter(is_active=True).select_related('product').order_by('display_order')
    serializer_class = CarouselItemSerializer
    permission_classes = [AllowAny]

# ====== Protección anti-spam para contacto ======
class ContactoRateThrottle(AnonRateThrottle):
    rate = '4/hour'  # Máximo 4 envíos por hora por IP

class ContactoViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Endpoint público para recibir mensajes de contacto.
    Solo permite POST.
    """
    queryset = ContactMessage.objects.all()
    serializer_class = ContactoSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ContactoRateThrottle]
