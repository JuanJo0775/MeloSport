from django.db import models
from apps.products.models import Product
from apps.categories.models import Category
from apps.users.models import User

class ReportTemplate(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    template_file = models.FileField(upload_to='report_templates/')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Plantilla de Reporte"
        verbose_name_plural = "Plantillas de Reporte"

    def __str__(self):
        return self.name

class GeneratedReport(models.Model):
    REPORT_TYPES = [
        ('inventory', 'Valor de Inventario'),
        ('top_products', 'Productos Más Vendidos'),
        ('low_rotation', 'Productos con Baja Rotación'),
        ('movements', 'Historial de Movimientos'),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    parameters = models.JSONField(default=dict)  # Filtros y parámetros usados
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to='generated_reports/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reporte Generado"
        verbose_name_plural = "Reportes Generados"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.created_at}"