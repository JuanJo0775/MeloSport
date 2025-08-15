from django.db.models.functions import Coalesce
from rest_framework import viewsets, mixins, generics
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.throttling import AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Sum, Value
from unidecode import unidecode
from rest_framework.decorators import action

from apps.products.models import Product
from apps.categories.models import Category, AbsoluteCategory
from apps.frontend.models import FeaturedProductCarousel, ContactMessage



from .serializers import (
    ProductSerializer,
    CategorySerializer,
    CarouselItemSerializer,
    ContactoSerializer, AbsoluteCategorySerializer
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
    queryset = Product.objects.filter(status='active').prefetch_related(
        'images', 'variants', 'categories'
    ).distinct()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'sku']

    # Campos disponibles para ordenar desde el frontend
    ordering_fields = ['price', 'created_at', 'name', 'total_stock']
    ordering = ['name']  # Orden por defecto

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtro por búsqueda con normalización de acentos
        search = self.request.query_params.get('search', '').strip()
        if search:
            normalized = unidecode(search).lower()
            queryset = queryset.filter(
                Q(name__icontains=normalized) |
                Q(description__icontains=normalized) |
                Q(sku__icontains=normalized)
            )

        # Anotar stock total (con fallback a 0 si no hay variantes)
        queryset = queryset.annotate(
            total_stock=Coalesce(Sum('variants__stock'), Value(0))
        )

        return queryset

    @action(detail=False, methods=['get'])
    def autocomplete(self, request):
        """
        Devuelve sugerencias de productos y categorías para autocompletar.
        """
        term = request.query_params.get('q', '').strip()
        if not term:
            return Response([])

        normalized = unidecode(term).lower()

        # Productos (máx 5)
        productos = self.get_queryset().filter(
            Q(name__icontains=normalized) |
            Q(description__icontains=normalized) |
            Q(sku__icontains=normalized)
        ).values_list('name', flat=True).distinct()[:5]

        # Categorías (máx 5)
        categorias = Category.objects.filter(
            Q(name__icontains=normalized) |
            Q(nombre__icontains=normalized)
        ).values_list('name', flat=True).distinct()[:5]

        return Response({
            "productos": list(productos),
            "categorias": list(categorias)
        })

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

class CategoryTreeView(APIView):
    """
    Devuelve categorías padre con sus hijas.
    Excluye las categorías absolutas.
    """
    def get(self, request):
        # Filtrar solo las categorías padre (sin parent) y que no sean absolutas
        padres = Category.objects.filter(parent__isnull=True).prefetch_related('children')

        data = []
        for padre in padres:
            hijas_data = []
            for hija in padre.children.all():
                hijas_data.append({
                    "id": hija.id,
                    "nombre": hija.name
                })

            data.append({
                "id": padre.id,
                "nombre": padre.name,
                "is_parent": True,
                "hijas": hijas_data
            })

        return Response(data)

class AbsoluteCategoryListView(generics.ListAPIView):
    """
    Lista todas las categorías absolutas activas.
    """
    serializer_class = AbsoluteCategorySerializer

    def get_queryset(self):
        # Solo categorías absolutas activas
        queryset = AbsoluteCategory.objects.filter(activo=True).order_by('nombre')
        return queryset