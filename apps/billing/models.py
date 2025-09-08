from decimal import Decimal
from datetime import timedelta
from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.products.models import Product, ProductVariant, InventoryMovement
from apps.users.models import AuditLog


def add_business_days(start_date, days):
    """Suma días hábiles (lunes-viernes)."""
    current = start_date
    added = 0
    while added < days:
        current = current + timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


class Reservation(models.Model):
    """Apartado (reserva de productos)."""
    STATUS_CHOICES = [
        ("active", "Activo"),
        ("completed", "Completado"),
        ("cancelled", "Cancelado"),
        ("expired", "Expirado"),
    ]

    client_first_name = models.CharField("Nombre del cliente", max_length=100, null=True, blank=True)
    client_last_name = models.CharField("Apellido del cliente", max_length=100, null=True, blank=True)
    client_phone = models.CharField("Teléfono del cliente", max_length=30, null=True, blank=True)

    created_at = models.DateTimeField("Creado el", auto_now_add=True)
    amount_deposited = models.DecimalField("Monto abonado", max_digits=12, decimal_places=2, default=0)
    due_date = models.DateTimeField("Fecha límite")
    status = models.CharField("Estado", max_length=20, choices=STATUS_CHOICES, default="active")
    movement_created = models.BooleanField("Movimientos generados", default=False)

    class Meta:
        verbose_name = "Apartado"
        verbose_name_plural = "Apartados"

    def mark_reserved_movements(self, user=None, request=None):
        """
        Crea movimientos 'reserve' para bloquear stock de forma lógica
        (no descuenta del inventario físico).
        """
        if self.movement_created:
            return
        with transaction.atomic():
            for item in self.items.select_related("product", "variant").all():
                InventoryMovement.objects.create(
                    product=item.product,
                    variant=item.variant,
                    movement_type="reserve",   # 👈 ahora RESERVA
                    reservation_id=self.pk,    # 👈 vínculo robusto con la reserva
                    quantity=item.quantity,
                    user=user,
                    unit_price=item.unit_price,
                    discount_percentage=Decimal("0.00"),
                    notes=f"Apartado #{self.pk}"
                )
            self.movement_created = True
            self.save(update_fields=["movement_created"])
            AuditLog.log_action(
                request=request,
                user=user,
                action="create",
                model=Reservation,
                obj=self,
                description=f"Apartado creado y stock marcado como reservado (ID {self.pk})"
            )

    def release(self, user=None, reason="expired", request=None):
        """
        Libera la reserva.
        No genera movimiento 'in' porque 'reserve' no modificó stock físico.
        Solo cambia el estado y registra la liberación en el log.
        """
        if self.status in ("cancelled", "expired", "completed"):
            return
        with transaction.atomic():
            self.status = "expired" if reason == "expired" else "cancelled"
            self.save(update_fields=["status"])
            AuditLog.log_action(
                request=request,
                user=user,
                action="update",
                model=Reservation,
                obj=self,
                description=f"Apartado liberado (ID {self.pk}) Motivo: {reason}"
            )

    def __str__(self):
        return f"Apartado #{self.pk} - {self.client_first_name or ''} {self.client_last_name or ''}".strip()


class ReservationItem(models.Model):
    reservation = models.ForeignKey(Reservation, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Producto", on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, verbose_name="Variante", null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField("Cantidad", default=1)
    unit_price = models.DecimalField("Precio unitario", max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Producto apartado"
        verbose_name_plural = "Productos apartados"

    def subtotal(self):
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price


class Invoice(models.Model):
    """Factura de venta."""
    client_first_name = models.CharField("Nombre del cliente", max_length=100, null=True, blank=True)
    client_last_name = models.CharField("Apellido del cliente", max_length=100, null=True, blank=True)
    client_phone = models.CharField("Teléfono del cliente", max_length=30, null=True, blank=True)

    created_at = models.DateTimeField("Creado el", auto_now_add=True)
    reservation = models.ForeignKey(Reservation, verbose_name="Apartado relacionado", null=True, blank=True, on_delete=models.SET_NULL)

    # 👇 Descuento directo en la venta
    discount_percentage = models.DecimalField(
        "% Descuento",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    discount_amount = models.DecimalField("Monto descuento", max_digits=12, decimal_places=2, default=0)

    subtotal = models.DecimalField("Subtotal", max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField("Total", max_digits=12, decimal_places=2, default=0)

    code = models.CharField("Código de factura", max_length=50, unique=True, blank=True)
    notes = models.TextField("Notas", blank=True)
    paid = models.BooleanField("Pagada", default=False)
    payment_date = models.DateTimeField("Fecha de pago", null=True, blank=True)
    inventory_moved = models.BooleanField("Movimientos aplicados", default=False)

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"

    def compute_totals(self):
        subtotal = sum([li.subtotal for li in self.items.all()]) if hasattr(self, "items") else Decimal("0.00")
        self.subtotal = Decimal(subtotal).quantize(Decimal("0.01"))
        self.discount_amount = (self.subtotal * self.discount_percentage / Decimal("100.00")).quantize(Decimal("0.01"))
        self.total = (self.subtotal - self.discount_amount).quantize(Decimal("0.01"))

    def generate_code(self):
        now = timezone.now()
        return f"FAC-{now.year}-{self.pk:06d}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            code = self.generate_code()
            Invoice.objects.filter(pk=self.pk).update(code=code)

    def apply_inventory_movements(self, user=None, request=None):
        """Crea movimientos 'out' por cada item de la factura."""
        if self.inventory_moved:
            return
        with transaction.atomic():
            for item in self.items.select_related("product", "variant").all():
                # Si viene de reserva y ya se descontó stock, no repetir
                if self.reservation and self.reservation.movement_created:
                    continue
                InventoryMovement.objects.create(
                    product=item.product,
                    variant=item.variant,
                    movement_type="out",
                    quantity=item.quantity,
                    user=user,
                    unit_price=item.unit_price,
                    discount_percentage=self.discount_percentage,
                    notes=f"Venta factura {self.code or self.pk}"
                )
            self.inventory_moved = True
            self.save(update_fields=["inventory_moved"])
            AuditLog.log_action(
                request=request,
                user=user,
                action="create",
                model=Invoice,
                obj=self,
                description=f"Movimientos de inventario aplicados por factura {self.code}"
            )

    def __str__(self):
        return f"Factura {self.code or self.pk} - {self.client_first_name or ''} {self.client_last_name or ''}".strip()


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Producto", on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, verbose_name="Variante", null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField("Cantidad", default=1)
    unit_price = models.DecimalField("Precio unitario", max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField("Subtotal", max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Producto facturado"
        verbose_name_plural = "Productos facturados"

    def save(self, *args, **kwargs):
        self.subtotal = (self.unit_price * self.quantity).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"
