from rest_framework import serializers
from .models import Product, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['nombre', 'descripcion']

class ProductSerializer(serializers.ModelSerializer):
    # Para mostrar el nombre de la categoría en lugar de su ID
    categoria = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ['nombre', 'precio', 'descripcion', 'stock', 'SKU', 'categoria']