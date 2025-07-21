from django.contrib import admin
from .models import DatabaseBackup, DatabaseStatusLog
from django.utils.html import format_html
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages


@admin.register(DatabaseBackup)
class DatabaseBackupAdmin(admin.ModelAdmin):
    list_display = ('backup_type', 'created_by', 'created_at', 'file_size', 'download_link')
    list_filter = ('backup_type', 'created_at')
    readonly_fields = ('backup_type', 'created_by', 'created_at', 'file_size', 'download_link')
    date_hierarchy = 'created_at'

    def file_size(self, obj):
        if obj.file:
            return f"{obj.file.size / 1024 / 1024:.2f} MB"
        return "-"

    file_size.short_description = "Tamaño"

    def download_link(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" download>Descargar Backup</a>',
                obj.file.url
            )
        return "-"

    download_link.short_description = "Descarga"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('create_backup/', self.admin_site.admin_view(self.create_backup),
                 name='database_databasebackup_create_backup'),
        ]
        return custom_urls + urls

    def create_backup(self, request):
        # Aquí iría la lógica para crear el backup
        # Por ahora simulamos que se creó
        messages.success(request, "Backup creado exitosamente")
        return HttpResponseRedirect(reverse('admin:database_databasebackup_changelist'))


@admin.register(DatabaseStatusLog)
class DatabaseStatusLogAdmin(admin.ModelAdmin):
    list_display = ('status', 'created_at', 'details_preview')
    list_filter = ('status', 'created_at')
    readonly_fields = ('status', 'details', 'created_at')
    date_hierarchy = 'created_at'

    def details_preview(self, obj):
        details = obj.details
        if not details:
            return "-"
        return ", ".join([f"{k}: {v}" for k, v in details.items()][:3]) + ("..." if len(details) > 3 else "")

    details_preview.short_description = "Detalles"

    def has_add_permission(self, request):
        return False