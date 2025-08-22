from django.urls import path
from . import views

app_name = "categories"

urlpatterns = [

    path('', views.CategoryHomeView.as_view(), name='home'),

    # Categorías
    path('categorias/', views.CategoryListView.as_view(), name='list'),
    path('categorias/crear/', views.CategoryCreateView.as_view(), name='create'),
    path('categorias/<int:pk>/editar/', views.CategoryUpdateView.as_view(), name='edit'),
    path('categorias/<int:pk>/eliminar/', views.CategoryDeleteView.as_view(), name='delete'),

    # Deportes (Categorías absolutas)
    path('deportes/', views.AbsoluteCategoryListView.as_view(), name='absolute_list'),
    path('deportes/crear/', views.AbsoluteCategoryCreateView.as_view(), name='absolute_create'),
    path('deportes/<int:pk>/editar/', views.AbsoluteCategoryUpdateView.as_view(), name='absolute_edit'),
    path('deportes/<int:pk>/eliminar/', views.AbsoluteCategoryDeleteView.as_view(), name='absolute_delete'),
]
