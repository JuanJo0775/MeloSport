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
    bg_color = models.CharField(
        max_length=7,
        default="#0d6efd",
        verbose_name="Color de fondo",
        help_text="HEX (#RRGGBB)"
    )

    # 🎨 Variantes de diseño extendidas (igual que InformativeCarousel)
    LAYOUT_CHOICES = [
        ("default", "Texto izquierda + imagen derecha"),
        ("full_text", "Texto centrado sin imagen"),
        ("icon_text", "Ícono grande + texto abajo"),
        ("two_img", "Texto + hasta 2 imágenes"),
        ("three_img", "Texto + hasta 3 imágenes"),
        ("split_banner", "Banner dividido en dos columnas"),
        ("minimal", "Diseño minimalista (solo título y botón)"),
    ]
    layout = models.CharField(
        max_length=20,
        choices=LAYOUT_CHOICES,
        default="default",
        verbose_name="Diseño de tarjeta"
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
        """Valida que el producto tenga suficientes imágenes según el layout"""
        images_count = self.product.images.count()
        if self.layout == "two_img" and images_count < 2:
            raise ValidationError("El producto debe tener al menos 2 imágenes para este diseño.")
        if self.layout == "three_img" and images_count < 3:
            raise ValidationError("El producto debe tener al menos 3 imágenes para este diseño.")
        if images_count < 1:
            raise ValidationError("El producto debe tener al menos 1 imagen para ser destacado.")

    # ---------------------------
    # 🖼️ Helpers para frontend
    # ---------------------------
    @property
    def title(self):
        return self.custom_title or self.product.name

    @property
    def subtitle(self):
        categories = self.product.categories.all()
        return self.custom_subtitle or (categories[0].name if categories else "Sin categoría")

    @property
    def images(self):
        """Devuelve lista de imágenes del producto"""
        return [img.image.url for img in self.product.images.all()]

    @property
    def images(self):
        """Devuelve los objetos de imagen del producto (consistente con InformativeCarousel)."""
        return [img.image for img in self.product.images.all() if img.image]

    @property
    def product_link(self):
        """Genera automáticamente el enlace al producto"""
        return self.product.get_absolute_url()

# apps/frontend/models.py
class InformativeCarousel(models.Model):
    """Tarjetas informativas/promocionales para el carrusel mixto."""
    title = models.CharField(max_length=120, verbose_name="Título")
    description = models.CharField(max_length=240, blank=True, verbose_name="Descripción")

    # Hasta 3 imágenes opcionales
    image1 = models.ImageField(upload_to="carousel_info/", blank=True, null=True, verbose_name="Imagen 1 (opcional)")
    image2 = models.ImageField(upload_to="carousel_info/", blank=True, null=True, verbose_name="Imagen 2 (opcional)")
    image3 = models.ImageField(upload_to="carousel_info/", blank=True, null=True, verbose_name="Imagen 3 (opcional)")

    link = models.CharField(max_length=255, blank=True, verbose_name="Link (interno o externo)")
    bg_color = models.CharField(max_length=7, default="#198754", verbose_name="Color de fondo", help_text="HEX (#RRGGBB)")

    # 🎨 Variantes de diseño extendidas
    LAYOUT_CHOICES = [
        ("default", "Texto izquierda + imagen derecha"),
        ("full_text", "Texto centrado sin imagen"),
        ("icon_text", "Ícono grande + texto abajo"),
        ("three_img", "Texto + hasta 3 imágenes"),
        ("image_bg", "Imagen de fondo con overlay de texto"),
        ("split_banner", "Banner dividido en dos columnas"),
        ("minimal", "Diseño minimalista (solo título y botón)"),
    ]
    layout = models.CharField(
        max_length=20,
        choices=LAYOUT_CHOICES,
        default="default",
        verbose_name="Diseño de tarjeta"
    )

    display_order = models.PositiveIntegerField(default=0, verbose_name="Orden de visualización")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    is_default = models.BooleanField(default=False, verbose_name="Es slide predeterminada")
    DEFAULT_TYPES = [
        ("welcome", "Bienvenida"),
        ("about", "Nosotros y Contacto"),
    ]
    default_type = models.CharField(
        max_length=20,
        choices=DEFAULT_TYPES,
        blank=True,
        null=True,
        verbose_name="Tipo de slide predeterminada",
        help_text="Usado para identificar slides fijos como Bienvenida o Nosotros"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Tarjeta informativa"
        verbose_name_plural = "Carrusel: Tarjetas informativas"
        ordering = ["display_order", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def images(self):
        """Devuelve los objetos de imagen (no solo la URL)."""
        return [img for img in [self.image1, self.image2, self.image3] if img]


    @property
    def safe_link(self):
        return self.link or "#"


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