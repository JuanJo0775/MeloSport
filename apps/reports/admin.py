from django.contrib import admin
from .models import ReportTemplate, GeneratedReport
from django.utils.html import format_html
from django.urls import reverse


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'download_template', 'is_active')
    list_filter = ('is_active',)
    list_editable = ('is_active',)


    def download_template(self, obj):
        if obj.template_file:
            return format_html(
                '<a href="{}" download>Descargar</a>',
                obj.template_file.url
            )
        return "-"

    download_template.short_description = "Plantilla"


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'parameters_preview', 'generated_by', 'created_at', 'download_report')
    list_filter = ('report_type', 'created_at')
    search_fields = ('generated_by__username', 'parameters')
    readonly_fields = ('report_type', 'parameters', 'generated_by', 'created_at', 'download_link')
    date_hierarchy = 'created_at'

    def parameters_preview(self, obj):
        params = obj.parameters
        if not params:
            return "-"
        return ", ".join([f"{k}: {v}" for k, v in params.items()][:3]) + ("..." if len(params) > 3 else "")

    parameters_preview.short_description = "Parámetros"

    def download_report(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" download>Descargar</a>',
                obj.file.url
            )
        return "-"

    download_report.short_description = "Reporte"

    def download_link(self, obj):
        return self.download_report(obj)

    download_link.short_description = "Enlace de descarga"

    def has_add_permission(self, request):
        return False