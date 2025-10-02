from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.reports.models import ReportDefinition

class Command(BaseCommand):
    help = "Crea definiciones iniciales de reportes (8 básicos)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        current_month = today.strftime("%Y-%m")       # yyyy-mm
        first_day = today.replace(day=1).strftime("%Y-%m-%d")
        last_day = today.replace(day=28).strftime("%Y-%m-%d")  # seguro hasta el 28
        # ⚠️ tip: si quieres último día real del mes usa calendar.monthrange

        definitions = [
            {
                "name": "Reporte Diario",
                "slug": "reporte-diario",
                "description": "Rendimiento de un día específico.",
                "report_type": "daily",
                "export_formats": ["xlsx", "csv", "pdf"],
                "default_parameters": {"date": today.strftime("%Y-%m-%d")},
            },
            {
                "name": "Reporte Mensual",
                "slug": "reporte-mensual",
                "description": "Tendencias, ingresos, top productos, reservas.",
                "report_type": "monthly",
                "export_formats": ["xlsx", "csv", "pdf"],
                "default_parameters": {"month": current_month},
            },
            {
                "name": "Reporte de Inventario",
                "slug": "reporte-inventario",
                "description": "Stock actual, reservado, valor total y alertas.",
                "report_type": "inventory",
                "export_formats": ["xlsx", "csv", "pdf"],
                "default_parameters": {"min_stock": 5},
            },
            {
                "name": "Reporte de Productos",
                "slug": "reporte-productos",
                "description": "Más vendidos, menos vendidos, sin rotación.",
                "report_type": "top_products",
                "export_formats": ["xlsx", "csv", "pdf"],
                "default_parameters": {"limit": 20},
            },
            {
                "name": "Reporte de Categorías",
                "slug": "reporte-categorias",
                "description": "Ventas y distribución de ingresos por categoría.",
                "report_type": "categories",
                "export_formats": ["xlsx", "csv", "pdf"],
                "default_parameters": {"date_from": first_day, "date_to": last_day},
            },
            {
                "name": "Reporte de Ventas",
                "slug": "reporte-ventas",
                "description": "Listado detallado de ventas, descuentos, métodos de pago.",
                "report_type": "sales",
                "export_formats": ["xlsx", "csv", "pdf"],
                "default_parameters": {"date_from": first_day, "date_to": last_day},
            },
            {
                "name": "Reporte de Reservas",
                "slug": "reporte-reservas",
                "description": "Activas, completadas, canceladas, vencidas, impacto en inventario.",
                "report_type": "reservations",
                "export_formats": ["xlsx", "csv", "pdf"],
                "default_parameters": {"date_from": first_day, "date_to": last_day},
            },
            {
                "name": "Reporte de Auditoría",
                "slug": "reporte-auditoria",
                "description": "Acciones de usuarios, cambios realizados, transparencia.",
                "report_type": "audit",
                "export_formats": ["xlsx", "csv", "pdf"],
                "default_parameters": {"date_from": first_day, "date_to": last_day},
            },
        ]

        created, skipped = 0, 0
        for d in definitions:
            obj, was_created = ReportDefinition.objects.get_or_create(
                slug=d["slug"],
                defaults={
                    "name": d["name"],
                    "description": d["description"],
                    "report_type": d["report_type"],
                    "export_formats": d["export_formats"],
                    "default_parameters": d["default_parameters"],
                    "is_public": True,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"✔ Creado: {obj.name}"))
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"• Ya existía: {obj.name}"))

        self.stdout.write(self.style.SUCCESS(f"Finalizado. {created} creados, {skipped} existentes."))
