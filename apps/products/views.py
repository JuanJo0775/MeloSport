from rest_framework import viewsets
from .models import Product
from .serializers import ProductSerializer

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint que permite ver los productos.
    """
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer