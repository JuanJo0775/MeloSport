import random
import string
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.categories.models import Category
from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


class Product(models.Model):
    PRODUCT_STATUS = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('draft', 'Borrador'),
    ]

    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0.00,
        verbose_name="Costo neto",
        help_text="Costo base del producto sin impuestos"
    )
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=19.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="% de IVA",
        help_text="Porcentaje de impuesto aplicable"
    )
    markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=30.00,
        validators=[MinValueValidator(0)],
        verbose_name="% de Ganancia",
        help_text="Porcentaje de ganancia sobre el costo con IVA"
    )
    _stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        db_column='stock',
        verbose_name="Stock manual",
        help_text="Solo se usa si el producto no tiene variantes"
    )
    min_stock = models.IntegerField(default=5, verbose_name="Stock mínimo")
    status = models.CharField(max_length=10, choices=PRODUCT_STATUS, default='active')
    categories = models.ManyToManyField(
        Category,
        related_name='products',
        verbose_name="Categorías",
        help_text="Seleccione una o varias categorías para este producto"
    )
    has_variants = models.BooleanField(
        default=True,
        verbose_name="¿Tiene Variantes?",
        help_text="Marcar si este producto se venderá con variantes (tallas, colores, etc)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['name']

    def __str__(self):
        if self.sku:
            return f"{self.name} ({self.sku})"
        return self.name

    def save(self, *args, **kwargs):
        """Guarda el producto y maneja las relaciones después"""
        creating = not self.pk  # Verifica si es creación nueva

        # Generar SKU si no existe
        if not self.sku:
            self.sku = self.generate_product_sku()

        # Guardar primero el producto
        super().save(*args, **kwargs)

        # Si es creación nueva, guardar relaciones ManyToMany después
        if creating and hasattr(self, '_pending_m2m'):
            for fieldname, values in self._pending_m2m.items():
                field = getattr(self, fieldname)
                field.set(values)
            del self._pending_m2m

    def generate_product_sku(self):
        """Genera un SKU base para el producto"""
        prefix = self.name[:3].upper() if self.name else 'PRO'
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{prefix}-{random_part}"

    def calculated_stock(self):
        """Calcula el stock dependiendo de si tiene variantes o no"""
        if self.has_variants:
            return sum(v.stock for v in self.variants.all())
        return self._stock

    @property
    def stock(self):
        """Devuelve el stock real, calculado si tiene variantes"""
        if self.variants.exists():
            return sum(v.stock for v in self.variants.all())
        return self._stock


    @property
    def cost_with_tax(self):
        """Calcula el costo con IVA incluido"""
        if self.cost is None or self.tax_percentage is None:
            return None
        return round(self.cost * (1 + self.tax_percentage / 100), 2)

    @property
    def suggested_price(self):
        """
        Calcula el precio sugerido con base en el costo con IVA y el % de ganancia.
        Ejemplo: 30% sobre el costo final
        """
        try:
            cost = Decimal(self.product.cost)  # ajusta si usas otro campo
            tax = Decimal(self.product.tax_percentage)  # ajusta según tu modelo
            profit_pct = Decimal(self.product.profit_margin)  # o fija el 30%

            cost_with_tax = cost * (1 + tax / 100)
            suggested = cost_with_tax * (1 + profit_pct / 100)
            return round(suggested, 2)
        except Exception:
            return Decimal("0.00")

    def clean(self):
        super().clean()

        if Product.objects.filter(sku=self.sku).exclude(pk=self.pk).exists():
            raise ValidationError(f"El SKU {self.sku} ya existe para otro producto")

        # Solo validar si el producto ya existe (tiene PK) y no es nuevo
        if self.pk and not self.has_variants and self.variants.exists():
            raise ValidationError(
                "El producto está marcado como 'sin variantes' pero tiene variantes asociadas. "
                "Por favor cambie la opción '¿Tiene Variantes?' a 'Sí' o elimine las variantes."
            )

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        editable=False
    )
    size = models.CharField(max_length=50, blank=True, verbose_name="Talla")
    color = models.CharField(max_length=50, blank=True, verbose_name="Color")
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Inventario"
    )
    price_modifier = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Ajuste de precio"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )

    class Meta:
        verbose_name = "Variante de Producto"
        verbose_name_plural = "Variantes de Producto"
        ordering = ['sku']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'size', 'color'],
                name='unique_variant'
            )
        ]

    def __str__(self):
        attrs = []
        if self.size:
            attrs.append(f"Talla: {self.size}")
        if self.color:
            attrs.append(f"Color: {self.color}")
        return f"{self.product.name} ({', '.join(attrs)})" if attrs else f"{self.product.name} (Base)"

    def save(self, *args, **kwargs):
        """Validación estricta de producto existente"""
        if not self.product_id:
            raise ValidationError(
                "No se puede guardar una variante sin producto asociado. "
                "Guarde primero el producto principal."
            )

        if not self.sku:
            self.sku = self.generate_standardized_sku()

        super().save(*args, **kwargs)

    def generate_standardized_sku(self):
        if not self.product_id or not self.product.sku:
            raise ValidationError("No se puede generar SKU sin un producto padre con SKU válido.")

        base_sku = self.product.sku.split('-')[0]
        size_part = self.size[:3].upper().strip() if self.size else "UNI"
        color_part = self.color[:3].upper().strip() if self.color else "DEF"
        checksum = ''.join(random.choices(string.digits, k=2))

        return f"{base_sku}-{size_part}-{color_part}-{checksum}"

    def clean(self):
        super().clean()

        if not self.product_id:
            raise ValidationError("La variante debe estar asociada a un producto.")

        if self.sku and ProductVariant.objects.filter(sku=self.sku).exclude(pk=self.pk).exists():
            raise ValidationError(f"El SKU {self.sku} ya existe para otra variante.")

        # Validar que el producto padre permita variantes
        if self.product_id and not self.product.has_variants:
            raise ValidationError(
                "El producto padre no está configurado para tener variantes. "
                "Cambie la opción '¿Tiene Variantes?' en el producto primero."
            )


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    is_main = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Imagen de Producto"
        verbose_name_plural = "Imágenes de Producto"
        ordering = ['order']

    def save(self, *args, **kwargs):
        if not self.product_id:
            raise ValueError("La imagen debe estar asociada a un producto existente")
        super().save(*args, **kwargs)


class InventoryMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'Entrada'),
        ('out', 'Salida'),
        ('adjust', 'Ajuste'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    notes = models.TextField(blank=True)
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Precio unitario"
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="% Descuento"
    )

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} de {self.quantity} unidades"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.variant:
            self.variant.stock += self.quantity if self.movement_type == 'in' else -self.quantity
            self.variant.save()
        else:
            self.product.stock += self.quantity if self.movement_type == 'in' else -self.quantity
            self.product.save()

    @property
    def final_unit_price(self):
        if self.unit_price:
            return round(self.unit_price * (1 - self.discount_percentage / 100), 2)
        return 0

    @property
    def total_amount(self):
        return round(self.quantity * self.final_unit_price, 2)