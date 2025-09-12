# apps/reports/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import ReportTemplate, ReportDefinition, GeneratedReport


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "builtin", "is_active", "download_link")
    list_filter = ("builtin", "is_active")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("created_at", "updated_at", "created_by")

    def download_link(self, obj):
        if obj.template_file:
            return format_html('<a href="{}" download>Descargar</a>', obj.template_file.url)
        return "-"
    download_link.short_description = "Archivo"


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "report_type", "is_public", "created_by", "created_at")
    list_filter = ("report_type", "is_public")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at", "created_by")

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ("report_label", "definition", "generated_by", "status", "format", "created_at", "download_link")
    list_filter = ("status", "format", "created_at")
    search_fields = ("report_label", "definition__name", "generated_by__username", "error_message")
    readonly_fields = (
        "definition",
        "report_label",
        "parameters",
        "generated_by",
        "status",
        "format",
        "file",
        "preview",
        "rows_count",
        "error_message",
        "created_at",
        "started_at",
        "finished_at",
        "expires_at",
    )
    date_hierarchy = "created_at"

    def download_link(self, obj):
        if obj.file:
            url = reverse("reports:generated_download", args=[obj.pk])
            return format_html('<a href="{}">Descargar</a>', url)
        return "-"
    download_link.short_description = "Archivo"
