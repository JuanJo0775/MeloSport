from django.db import models
from django.core.exceptions import ValidationError

from apps.products.models import Product
from apps.frontend.image_optimizer import optimize_carousel_image


# ============================================================
# 🎠 Carrusel de Productos Destacados
# ============================================================

class FeaturedProductCarousel(models.Model):
    """
    Modelo para gestionar productos destacados en el carrusel principal.
    Reutiliza las imágenes optimizadas del producto (ProductImage).
    """

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

    created_at = models.DateTimeField(auto_now_add=True)

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
        images_count = self.product.images.count()

        if images_count < 1:
            raise ValidationError("El producto debe tener al menos 1 imagen.")

        if self.layout == "two_img" and images_count < 2:
            raise ValidationError("Se requieren al menos 2 imágenes.")

        if self.layout == "three_img" and images_count < 3:
            raise ValidationError("Se requieren al menos 3 imágenes.")

    @property
    def title(self):
        return self.custom_title or self.product.name

    @property
    def subtitle(self):
        return self.custom_subtitle or (
            self.product.categories.first().name
            if self.product.categories.exists()
            else "Sin categoría"
        )

    @property
    def images(self):
        return self.product.images.all()

    @property
    def product_link(self):
        return self.product.get_absolute_url()


# ============================================================
# 🧾 Carrusel Informativo / Promocional (OPTIMIZADO)
# ============================================================

class InformativeCarousel(models.Model):
    """
    Tarjetas informativas/promocionales para el carrusel mixto.
    Las imágenes se optimizan automáticamente al guardarse.
    """

    title = models.CharField(max_length=120)
    description = models.CharField(max_length=240, blank=True)

    image1 = models.ImageField(upload_to="carousel_info/", blank=True, null=True)
    image2 = models.ImageField(upload_to="carousel_info/", blank=True, null=True)
    image3 = models.ImageField(upload_to="carousel_info/", blank=True, null=True)

    # 🔒 Flags internos (evitan reprocesar)
    image1_optimized = models.BooleanField(default=False, editable=False)
    image2_optimized = models.BooleanField(default=False, editable=False)
    image3_optimized = models.BooleanField(default=False, editable=False)

    link = models.CharField(max_length=255, blank=True)

    bg_color = models.CharField(max_length=7, default="#198754")

    LAYOUT_CHOICES = [
        ("default", "Texto izquierda + imagen derecha"),
        ("full_text", "Texto centrado sin imagen"),
        ("icon_text", "Ícono grande + texto abajo"),
        ("three_img", "Texto + hasta 3 imágenes"),
        ("image_bg", "Imagen de fondo con overlay"),
        ("split_banner", "Banner dividido"),
        ("minimal", "Minimal"),
    ]

    layout = models.CharField(
        max_length=20,
        choices=LAYOUT_CHOICES,
        default="default"
    )

    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    DEFAULT_TYPES = [
        ("welcome", "Bienvenida"),
        ("about", "Nosotros"),
    ]

    default_type = models.CharField(
        max_length=20,
        choices=DEFAULT_TYPES,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tarjeta informativa"
        verbose_name_plural = "Carrusel: Tarjetas informativas"
        ordering = ["display_order", "-created_at"]

    def __str__(self):
        return self.title

    # ---------------------------
    # ⚙️ Optimización automática
    # ---------------------------

    def save(self, *args, **kwargs):
        old = None
        if self.pk:
            try:
                old = InformativeCarousel.objects.get(pk=self.pk)
            except InformativeCarousel.DoesNotExist:
                pass

        for field, flag in [
            ("image1", "image1_optimized"),
            ("image2", "image2_optimized"),
            ("image3", "image3_optimized"),
        ]:
            new_img = getattr(self, field)
            old_img = getattr(old, field) if old else None
            optimized = getattr(self, flag)

            if new_img and (not optimized or new_img != old_img):
                optimized_file = optimize_carousel_image(new_img)
                setattr(self, field, optimized_file)
                setattr(self, flag, True)

                if old_img:
                    try:
                        old_img.delete(save=False)
                    except Exception:
                        pass

        super().save(*args, **kwargs)

    # ---------------------------
    # 🖼️ Helpers
    # ---------------------------

    @property
    def images(self):
        return [img for img in (self.image1, self.image2, self.image3) if img]

    @property
    def safe_link(self):
        return self.link or "#"


# ============================================================
# 📩 Mensajes de Contacto
# ============================================================

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
