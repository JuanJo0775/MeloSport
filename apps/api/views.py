from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q, Sum, Value, Func, CharField, F
from django.db.models.functions import Coalesce, Lower
from rest_framework import viewsets, mixins, generics
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.throttling import AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend

from unidecode import unidecode

from apps.products.models import Product
from apps.categories.models import Category, AbsoluteCategory
from apps.frontend.models import FeaturedProductCarousel, ContactMessage, InformativeCarousel

from .serializers import (
    ProductSerializer,
    CategorySerializer,
    CarouselItemSerializer,
    ContactoSerializer,
    AbsoluteCategorySerializer,
    UnifiedCarouselItemSerializer,
)
from .filters import ProductFilter


# ===================== Categorías =====================

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lectura pública de categorías (lista y detalle).
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]


# ===================== Utilidad para búsqueda =====================

class Unaccent(Func):
    function = "unaccent"
    template = "%(function)s(%(expressions)s)"
    output_field = CharField()


# ===================== Productos =====================

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoints públicos: lista y detalle de productos.

    Soporta:
      - Filtros: categorías, absolutas, rango de precio, stock
      - Ordenado: price, -price, name, created_at, -created_at
      - Búsqueda global: nombre, descripción, tags (case/acento insensible)
    """
    queryset = Product.objects.all().prefetch_related("categories", "images", "variants")
    serializer_class = ProductSerializer

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductFilter
    ordering_fields = ["price", "name", "created_at"]
    ordering = ["-created_at"]  # por defecto: más recientes
    search_fields = ["name", "category__name"]

    def get_queryset(self):
        qs = super().get_queryset()

        # Búsqueda global (case/acento-insensible)
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            term = unidecode(search).lower()
            qs = qs.annotate(
                name_u=Unaccent(Lower("name")),
                desc_u=Unaccent(Lower("description")),
            ).filter(
                Q(name_u__icontains=term) |
                Q(desc_u__icontains=term) |
                Q(categories__name__icontains=term)
            ).distinct()

        # Anotar stock total (con fallback a 0)
        qs = qs.annotate(total_stock=Coalesce(Sum("variants__stock"), Value(0)))
        return qs

    @action(detail=False, methods=["get"])
    def autocomplete(self, request):
        """
        Devuelve coincidencias rápidas para autocompletado.
        """
        term = (request.query_params.get("q") or "").strip()
        if not term:
            return Response({"productos": [], "categorias": []})

        term_norm = unidecode(term).lower()

        # Productos (máx 5, por similitud y prefijo)
        productos = (
            self.get_queryset()
            .annotate(
                name_unaccent=Lower(Unaccent("name")),
                similarity=TrigramSimilarity("name", term),
            )
            .filter(Q(name_unaccent__icontains=term_norm) | Q(similarity__gt=0.3))
            .order_by(F("similarity").desc(), "name")[:5]
            .values_list("name", flat=True)
        )

        # Categorías (máx 5)
        categorias_qs = (
            Category.objects.annotate(name_unaccent=Lower(Unaccent("name")))
            .filter(name_unaccent__icontains=term_norm)
            .distinct()
            .values("id", "name")[:5]
        )
        categorias = [{"id": c["id"], "name": c["name"]} for c in categorias_qs]

        return Response({
            "productos": list(productos),
            "categorias": categorias,
        })


# ===================== Carrusel =====================

class CarouselViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoint público para mostrar los elementos activos del carrusel (mixto).
    Devuelve productos destacados + tarjetas informativas, ya ordenados.
    """
    permission_classes = [AllowAny]
    serializer_class = UnifiedCarouselItemSerializer

    def list(self, request, *args, **kwargs):
        products = (
            FeaturedProductCarousel.objects
            .filter(is_active=True)
            .select_related("product")
            .order_by("display_order", "-created_at")
        )
        infos = (
            InformativeCarousel.objects
            .filter(is_active=True)
            .order_by("display_order", "-created_at")
        )

        combined = list(products) + list(infos)
        # Orden estable por display_order, y luego created_at descendente
        combined.sort(key=lambda x: (x.display_order, getattr(x, "created_at", None)), reverse=False)

        serializer = self.get_serializer(combined, many=True, context={"request": request})
        return Response(serializer.data)

# ===================== Contacto =====================

class ContactoRateThrottle(AnonRateThrottle):
    rate = "4/hour"  # Máx 4 envíos/hora por IP


class ContactoViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Endpoint público para recibir mensajes de contacto.
    Solo permite POST.
    """
    queryset = ContactMessage.objects.all()
    serializer_class = ContactoSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ContactoRateThrottle]


# ===================== Árbol de categorías =====================

from rest_framework.views import APIView

class CategoryTreeView(APIView):
    """
    Devuelve categorías padre con sus hijas.
    Excluye las categorías absolutas.
    """
    def get(self, request):
        padres = Category.objects.filter(parent__isnull=True).prefetch_related("children")

        data = []
        for padre in padres:
            hijas_data = [{"id": h.id, "nombre": h.name} for h in padre.children.all()]
            data.append({
                "id": padre.id,
                "nombre": padre.name,
                "is_parent": True,
                "hijas": hijas_data,
            })
        return Response(data)


# ===================== Categorías absolutas =====================

from rest_framework import generics

class AbsoluteCategoryListView(generics.ListAPIView):
    """
    Lista todas las categorías absolutas activas.
    """
    serializer_class = AbsoluteCategorySerializer

    def get_queryset(self):
        return AbsoluteCategory.objects.filter(activo=True).order_by("nombre")
