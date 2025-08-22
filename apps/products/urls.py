from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet)

app_name = "products"

urlpatterns = [
    path('api/', include(router.urls)),
]