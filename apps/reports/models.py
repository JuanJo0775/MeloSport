# apps/reports/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.core.files.base import ContentFile
import uuid

class ReportTemplate(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)  # ⚡ slug obligatorio, pero lo generamos en save()
    description = models.TextField(blank=True)
    template_file = models.FileField(upload_to="report_templates/", blank=True, null=True)
    builtin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="report_templates"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla de Reporte"
        verbose_name_plural = "Plantillas de Reporte"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Garantiza que siempre exista un slug único:
        - Se genera a partir del nombre si no existe.
        - Se asegura unicidad añadiendo un sufijo UUID corto si es necesario.
        """
        if not self.slug:
            base = slugify(self.name)[:40] if self.name else "reporte"
            candidate = base
            counter = 1
            while ReportTemplate.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                # si ya existe, agregar sufijo corto
                candidate = f"{base}-{uuid.uuid4().hex[:6]}"
                counter += 1
                if counter > 5:  # fallback seguro
                    candidate = f"{base}-{uuid.uuid4().hex[:8]}"
                    break
            self.slug = candidate
        super().save(*args, **kwargs)


class ReportDefinition(models.Model):
    """
    Definición reutilizable de un reporte: tipo (inventory, sales...), parámetros por defecto,
    plantilla a usar y formatos permitidos.
    """
    REPORT_TYPE_CHOICES = [
        ("daily", "Reporte Diario"),
        ("monthly", "Reporte Mensual"),
        ("inventory", "Reporte Inventario"),
        ("products", "Reporte Productos"),
        ("categories", "Reporte Categorías"),
        ("sales", "Reporte Ventas"),
        ("reservations", "Reporte Reservas"),
        ("audit", "Reporte Auditoría"),
        ("top_products", "Reporte Top Productos"),
        ("custom", "Reporte Personalizado"),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=40, choices=REPORT_TYPE_CHOICES, default="custom")
    template = models.ForeignKey(ReportTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    # default_parameters: p.e. {"date_from": "2025-01-01", "date_to": "2025-02-01"}
    default_parameters = models.JSONField(default=dict, blank=True)
    # export_formats = ["xlsx","csv","pdf","json"]
    export_formats = models.JSONField(default=list, blank=True)
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="report_definitions")
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Definición de Reporte"
        verbose_name_plural = "Definiciones de Reportes"

    def __str__(self):
        return self.name


class GeneratedReport(models.Model):
    """
    Registro de cada ejecución (histórico). Guarda parámetros, estado, archivo y preview.
    """
    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("running", "En ejecución"),
        ("completed", "Completado"),
        ("failed", "Fallido"),
    ]

    definition = models.ForeignKey(ReportDefinition, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="executions")
    report_label = models.CharField(max_length=200, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="generated_reports")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    format = models.CharField(max_length=10, default="xlsx")  # pdf, xlsx, csv, json
    file = models.FileField(upload_to="generated_reports/", null=True, blank=True)
    preview = models.JSONField(null=True, blank=True)  # primeras filas para vista rápida
    rows_count = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Reporte Generado"
        verbose_name_plural = "Reportes Generados"
        ordering = ["-created_at"]

    def __str__(self):
        label = self.report_label or (self.definition.name if self.definition else "Reporte")
        return f"{label} — {self.created_at:%Y-%m-%d %H:%M}"

    def save_file_from_bytes(self, bytes_content: bytes, filename: str):
        """
        Guardar el contenido bytes en el FileField sin cerrar la instancia.
        Luego se recomienda setear finished_at, status y save() desde la vista/servicio.
        """
        self.file.save(filename, ContentFile(bytes_content), save=False)
        # Nota: no hacemos save() aquí para dejar control a quien llama.
        return self.file.url if self.file else None
