import random
import string
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from apps.categories.models import Category
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils.text import slugify


class Product(models.Model):
    PRODUCT_STATUS = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('draft', 'Borrador'),
    ]

    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU", blank=True)
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
    absolute_category = models.ForeignKey(
        'categories.AbsoluteCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
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

    def generate_product_sku(self):
        """
        Genera un SKU legible y único para el producto.
        Estrategia:
          - Base: primeros 8 caracteres slugificados del nombre (o 'PRO' si no hay nombre)
          - Sufijo: 6 caracteres hex (uuid) o combinación aleatoria
          - Si hay colisión, intenta con sufijo alternativo hasta 10 veces.
        """
        base = (slugify(self.name)[:8].upper() if self.name else "PRO").strip("-_")
        attempts = 0
        while attempts < 10:
            suffix = uuid.uuid4().hex[:6].upper()
            candidate = f"{base}-{suffix}"
            if not Product.objects.filter(sku=candidate).exists():
                return candidate
            attempts += 1

        # Fallback seguro (menos legible) si por alguna razón hay colisiones
        return f"{base}-{uuid.uuid4().hex[:8].upper()}"

    def calculated_stock(self):
        """Calcula el stock dependiendo de si tiene variantes o no"""
        if self.has_variants:
            return sum(v.stock for v in self.variants.all())
        return self._stock

    def get_absolute_url(self):
        return f"/productos/{self.pk}/"

    @property
    def stock(self):
        """Devuelve el stock real, calculado si tiene variantes"""
        if self.variants.exists():
            return sum(v.stock for v in self.variants.all())
        return self._stock

    @stock.setter
    def stock(self, value):
        """Permite asignar stock como si fuera un campo normal"""
        self._stock = value

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
        Mantengo la estructura original; la lógica de acceso a atributos
        parecía referirse a self.product.* en un contexto distinto — dejo el cálculo seguro.
        """
        try:
            # Si quieres usar cost, tax y markup del propio producto:
            cost = Decimal(self.cost or 0)
            tax = Decimal(self.tax_percentage or 0)
            profit_pct = Decimal(self.markup_percentage or 0)

            cost_with_tax = cost * (1 + tax / 100)
            suggested = cost_with_tax * (1 + profit_pct / 100)
            return round(suggested, 2)
        except Exception:
            return Decimal("0.00")

    def clean(self):
        super().clean()

        if self.sku and Product.objects.filter(sku=self.sku).exclude(pk=self.pk).exists():
            raise ValidationError(f"El SKU {self.sku} ya existe para otro producto")

        # Solo validar si el producto ya existe (tiene PK) y no es nuevo
        if self.pk and not self.has_variants and self.variants.exists():
            raise ValidationError(
                "El producto está marcado como 'sin variantes' pero tiene variantes asociadas. "
                "Por favor cambie la opción '¿Tiene Variantes?' a 'Sí' o elimine las variantes."
            )

    def save(self, *args, **kwargs):
        """
        Sobrescribimos save para asegurar generación de SKU antes de persistir,
        sin eliminar ninguna lógica existente.
        """
        # Si sku está vacío o es cadena vacía, generamos uno
        if not self.sku or (isinstance(self.sku, str) and self.sku.strip() == ""):
            self.sku = self.generate_product_sku()
        super().save(*args, **kwargs)


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
        """Validación estricta de producto existente y generación de SKU para la variante"""
        if not self.product_id:
            raise ValidationError(
                "No se puede guardar una variante sin producto asociado. "
                "Guarde primero el producto principal."
            )

        # Generar SKU si no existe (no dependemos de raise en generator)
        if not self.sku:
            self.sku = self.generate_standardized_sku()

        super().save(*args, **kwargs)

    def generate_standardized_sku(self):
        """
        Genera un SKU para la variante basado en el SKU del producto (si existe),
        o en el nombre del producto como fallback. Asegura unicidad.
        Formato: <BASE>-<SIZE3>-<COL3>-<NN>
        """
        # Base preferente: parte anterior del SKU del producto si existe
        if self.product and self.product.sku:
            base_sku = self.product.sku.split('-')[0]
        else:
            base_sku = (slugify(self.product.name)[:6].upper() if self.product and self.product.name else "PROD")

        size_part = (self.size[:3].upper().strip() if self.size else "UNI")
        color_part = (self.color[:3].upper().strip() if self.color else "DEF")

        attempts = 0
        while attempts < 10:
            checksum = ''.join(random.choices(string.digits, k=2))
            candidate = f"{base_sku}-{size_part}-{color_part}-{checksum}"
            if not ProductVariant.objects.filter(sku=candidate).exists():
                return candidate
            attempts += 1

        # Fallback con uuid corto
        return f"{base_sku}-{size_part}-{color_part}-{uuid.uuid4().hex[:4].upper()}"

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
        ('reserve', 'Reserva'),  # 👈 Nuevo tipo
    ]

    # Relaciones
    product = models.ForeignKey(
        'Product', on_delete=models.CASCADE, related_name='movements'
    )
    variant = models.ForeignKey(
        'ProductVariant', on_delete=models.CASCADE, null=True, blank=True
    )

    # Datos de movimiento
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    notes = models.TextField(blank=True)

    # Nuevo campo robusto para vincular con reservas
    reservation_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID de Reservation si proviene de una reserva"
    )

    adjust_reason = models.TextField(
        blank=True,
        verbose_name="Motivo del ajuste",
        help_text="Obligatorio solo para ajustes."
    )

    # Metadatos
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Precios
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
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="% Descuento"
    )

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} de {self.quantity} - {self.product}"

    def clean(self):
        super().clean()

        if not self.product_id:
            raise ValidationError("Debe seleccionar un producto.")

        if self.variant_id and self.variant.product_id != self.product_id:
            raise ValidationError("La variante no pertenece al producto.")

        if self.movement_type in ('in', 'out'):
            if not self.quantity or self.quantity <= 0:
                raise ValidationError("Entradas y salidas requieren cantidad positiva (> 0).")

        if self.movement_type == 'adjust':
            if not self.quantity or int(self.quantity) == 0:
                raise ValidationError("En ajustes la cantidad no puede ser 0.")
            if not self.adjust_reason or str(self.adjust_reason).strip() == "":
                raise ValidationError({"adjust_reason": "Debes indicar un motivo para el ajuste."})

        if self.discount_percentage is None:
            self.discount_percentage = Decimal('0.00')

        if self.unit_price is not None and Decimal(self.unit_price) < 0:
            raise ValidationError("El precio unitario no puede ser negativo.")

        # 👉 Reserva valida igual que out/in, pero no tocará stock
        if self.movement_type == 'reserve' and (not self.quantity or self.quantity <= 0):
            raise ValidationError("La cantidad reservada debe ser positiva.")

    def _signed_qty(self) -> int:
        q = int(self.quantity or 0)
        if self.movement_type == 'in':
            return q
        if self.movement_type == 'out':
            return -q
        if self.movement_type == 'reserve':
            return 0  # 👈 Reserva no afecta stock físico
        return q  # adjust


    # Propiedades monetarias (seguros)

    @property
    def final_unit_price(self) -> Decimal:
        """
        Precio unitario final tras aplicar descuento. Siempre devuelve Decimal con 2 decimales.
        Si unit_price es None, devuelve Decimal('0.00').
        """
        unit = Decimal(self.unit_price) if self.unit_price is not None else Decimal('0.00')
        discount = Decimal(self.discount_percentage or 0)
        result = unit * (Decimal('1') - (discount / Decimal('100')))
        return result.quantize(Decimal('0.01'))

    @property
    def total_amount(self) -> Decimal:
        """
        Total = cantidad * precio_final. Seguro ante quantity == None.
        """
        qty = Decimal(self.quantity or 0)
        return (qty * self.final_unit_price).quantize(Decimal('0.01'))

    def final_unit_price_display(self):
        return f"{self.final_unit_price:.2f}"
    final_unit_price_display.short_description = "Precio final"

    def total_amount_display(self):
        return f"{self.total_amount:.2f}"
    total_amount_display.short_description = "Total"


    # Guardado atómico: apply/revert stock según create/update (y cambio de target)

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Lógica robusta de persistencia:
         - En create: aplica _signed_qty() al stock del producto/variante seleccionado.
         - En update: revierte el efecto antiguo y aplica el nuevo (maneja cambio de variante/producto).
        Se usan select_for_update() sobre Product/ProductVariant para evitar race conditions.
        """
        is_create = self.pk is None
        old = None

        if not is_create:
            # obtener la versión antigua y bloquearla para coherencia
            old = InventoryMovement.objects.select_for_update().get(pk=self.pk)

        # Determinar qué filas de stock necesitamos bloquear (productos y variantes)
        variant_ids = set()
        product_ids = set()

        if old:
            if old.variant_id:
                variant_ids.add(old.variant_id)
            else:
                product_ids.add(old.product_id)

        if self.variant_id:
            variant_ids.add(self.variant_id)
        else:
            product_ids.add(self.product_id)

        # Lockear las filas necesarias
        locked_variants = {}
        locked_products = {}

        for vid in variant_ids:
            locked_variants[vid] = ProductVariant.objects.select_for_update().get(pk=vid)

        for pid in product_ids:
            locked_products[pid] = Product.objects.select_for_update().get(pk=pid)

        # Calcular valores firmados antes de persistir
        new_signed = int(self._signed_qty())
        old_signed = int(old._signed_qty()) if old else 0

        # Persistir movimiento (ya dentro de la transacción)
        super().save(*args, **kwargs)

        # Si existía un movimiento previo: revertir su efecto sobre su target antiguo
        if old:
            if old.variant_id:
                v_old = locked_variants.get(old.variant_id) or ProductVariant.objects.select_for_update().get(pk=old.variant_id)
                v_old.stock = (v_old.stock or 0) - old_signed
                v_old.save(update_fields=['stock'])
            else:
                p_old = locked_products.get(old.product_id) or Product.objects.select_for_update().get(pk=old.product_id)
                p_old._stock = (p_old._stock or 0) - old_signed
                p_old.save(update_fields=['_stock'])

        # Aplicar el efecto del nuevo movimiento sobre su target actual
        if self.variant_id:
            v_new = locked_variants.get(self.variant_id) or ProductVariant.objects.select_for_update().get(pk=self.variant_id)
            v_new.stock = (v_new.stock or 0) + new_signed
            v_new.save(update_fields=['stock'])
        else:
            p_new = locked_products.get(self.product_id) or Product.objects.select_for_update().get(pk=self.product_id)
            p_new._stock = (p_new._stock or 0) + new_signed
            p_new.save(update_fields=['_stock'])


    @transaction.atomic
    def delete(self, *args, **kwargs):
        signed = int(self._signed_qty())  # in=+, out=-, adjust=±

        if self.variant_id:
            variant = ProductVariant.objects.select_for_update().get(pk=self.variant_id)
            new_stock = variant.stock - signed
            if new_stock < 0:
                raise ValidationError("No se puede eliminar: el stock de la variante quedaría negativo.")
            variant.stock = new_stock
            variant.save(update_fields=["stock"])
        else:
            product = Product.objects.select_for_update().get(pk=self.product_id)
            new_stock = product._stock - signed
            if new_stock < 0:
                raise ValidationError("No se puede eliminar: el stock del producto quedaría negativo.")
            product._stock = new_stock
            product.save(update_fields=["_stock"])

        return super().delete(*args, **kwargs)