from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ProductViewSet, CategoryViewSet, CarouselViewSet, ContactoViewSet, CategoryTreeView, \
    AbsoluteCategoryListView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'carousel', CarouselViewSet, basename='carousel')
router.register(r'contacto', ContactoViewSet, basename='contacto')


urlpatterns = [
    path('', include(router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('categories-tree/', CategoryTreeView.as_view(), name='categories-tree'),
    path('absolute-categories/', AbsoluteCategoryListView.as_view(), name='absolute-categories'),

]
