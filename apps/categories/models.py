from django.db import models
from mptt.models import MPTTModel, TreeForeignKey



class Category(MPTTModel):
    name = models.CharField(max_length=100, unique=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    @property
    def all_products(self):
        """Obtiene todos los productos de esta categoría usando el nombre del modelo como string"""
        from apps.products.models import Product
        from django.db.models import Q
        return Product.objects.filter(
            Q(categories=self) |
            Q(categories__in=self.get_descendants())
        ).distinct()

    def __str__(self):
        return self.name


class AbsoluteCategory(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoría Absoluta"
        verbose_name_plural = "Categorías Absolutas"

    def __str__(self):
        return self.nombre

    def get_product_count(self):

        return self.products.count()

    def get_related_objects(self, model_name):
        """
        Obtiene todos los objetos asociados usando el nombre del modelo como string."""
        from django.apps import apps
        model = apps.get_model(model_name)
        return model.objects.filter(absolute_category=self)


