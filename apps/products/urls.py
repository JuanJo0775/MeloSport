from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductListView, ProductCreateView, ProductDetailView, ProductUpdateView, ProductDeleteView,
    VariantListView, VariantCreateView, VariantUpdateView, VariantDeleteView, ProductViewSet
)

router = DefaultRouter()
router.register(r'products', ProductViewSet)

app_name = "products"

urlpatterns = [
    path('api/', include(router.urls)),

    # Productos
    path("", ProductListView.as_view(), name="product_list"),
    path("create/", ProductCreateView.as_view(), name="product_create"),
    path("<int:pk>/", ProductDetailView.as_view(), name="product_detail"),
    path("<int:pk>/edit/", ProductUpdateView.as_view(), name="product_update"),
    path("<int:pk>/delete/", ProductDeleteView.as_view(), name="product_delete"),

    # Variantes
    path("<int:pk>/variants/", VariantListView.as_view(), name="variant_list"),
    path("<int:pk>/variants/create/", VariantCreateView.as_view(), name="variant_create"),
    path("variants/<int:pk>/edit/", VariantUpdateView.as_view(), name="variant_update"),
    path("variants/<int:pk>/delete/", VariantDeleteView.as_view(), name="variant_delete"),
]