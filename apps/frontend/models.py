from django.db import models
from apps.products.models import Product
from django.core.exceptions import ValidationError

class FeaturedProductCarousel(models.Model):
    """Modelo para gestionar productos destacados en el carrusel principal"""
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        verbose_name="Producto destacado",
        unique=True,
        help_text="Seleccione un producto existente para mostrar en el carrusel"
    )
    custom_title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Título personalizado (opcional)",
        help_text="Si se deja vacío, se usará el nombre del producto"
    )
    custom_subtitle = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Subtítulo personalizado (opcional)"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Orden de visualización",
        help_text="Determina la posición en el carrusel (menor número = primero)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Marcar para mostrar este producto en el carrusel"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    class Meta:
        verbose_name = "Producto Destacado"
        verbose_name_plural = "Carrusel de Productos Destacados"
        ordering = ['display_order', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                name='unique_featured_product'
            )
        ]

    def __str__(self):
        return f"Destacado: {self.product.name}"

    def clean(self):
        """Valida que el producto tenga imágenes antes de destacarlo"""
        if not self.product.images.exists():
            raise ValidationError(
                "El producto debe tener al menos una imagen para ser destacado"
            )

    @property
    def title(self):
        return self.custom_title or self.product.name

    @property
    def subtitle(self):
        # Obtener la primera categoría o usar un valor por defecto
        categories = self.product.categories.all()
        return self.custom_subtitle or categories[0].name if categories else "Sin categoría"

    @property
    def image(self):
        """Obtiene la imagen principal del producto"""
        main_image = self.product.images.filter(is_main=True).first()
        return main_image.image if main_image else self.product.images.first().image

    @property
    def product_link(self):
        """Genera automáticamente el enlace al producto"""
        return self.product.get_absolute_url()

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField()
    is_answered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje de Contacto"
        verbose_name_plural = "Mensajes de Contacto"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.created_at}"