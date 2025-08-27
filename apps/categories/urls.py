from django.urls import path
from . import views

app_name = "categories"

urlpatterns = [
    path('', views.CategoryHomeView.as_view(), name='home'),

    # Jerárquicas (padre/hija)
    path('categorias/', views.CategoryListView.as_view(), name='list'),
    path('categorias/crear/', views.CategoryCreateView.as_view(), name='create'),
    path('categorias/<int:pk>/', views.CategoryDetailView.as_view(), name='detail'),
    path('categorias/<int:pk>/editar/', views.CategoryUpdateView.as_view(), name='edit'),
    path('categorias/<int:pk>/eliminar/', views.CategoryDeleteView.as_view(), name='delete'),

    # Absolutas (deportes)
    path('deportes/', views.AbsoluteCategoryListView.as_view(), name='absolute_list'),
    path('deportes/crear/', views.AbsoluteCategoryCreateView.as_view(), name='absolute_create'),
    path('deportes/<int:pk>/', views.AbsoluteCategoryDetailView.as_view(), name='absolute_detail'),
    path('deportes/<int:pk>/editar/', views.AbsoluteCategoryUpdateView.as_view(), name='absolute_edit'),
    path('deportes/<int:pk>/eliminar/', views.AbsoluteCategoryDeleteView.as_view(), name='absolute_delete'),

    path("deportes/<int:pk>/activar/", views.absolute_activate, name="absolute_activate"),
    path("deportes/<int:pk>/desactivar/", views.absolute_deactivate, name="absolute_deactivate"),

    path('categorias/bulk-action/', views.category_bulk_action, name='bulk_action'),
    path('deportes/bulk-action/', views.absolute_bulk_action, name='absolute_bulk_action'),
]
