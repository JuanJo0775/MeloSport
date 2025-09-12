# apps/reports/views.py
import os
import json
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.utils import timezone
from django.http import FileResponse, Http404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.files.base import ContentFile

from .models import ReportDefinition, GeneratedReport, ReportTemplate
from .services import ReportService
from apps.users.models import AuditLog


class ReportDefinitionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "reports.view_reportdefinition"
    model = ReportDefinition
    template_name = "backoffice/reports/definition_list.html"
    context_object_name = "definitions"


class ReportDefinitionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "reports.add_reportdefinition"
    model = ReportDefinition
    fields = ["name", "slug", "description", "report_type", "template", "default_parameters", "export_formats", "is_public"]
    template_name = "backoffice/reports/definition_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Definición de reporte creada.")
        return super().form_valid(form)


class ReportDefinitionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "reports.change_reportdefinition"
    model = ReportDefinition
    fields = ["name", "slug", "description", "report_type", "template", "default_parameters", "export_formats", "is_public"]
    template_name = "backoffice/reports/definition_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Definición de reporte actualizada.")
        return super().form_valid(form)


class GeneratedReportListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "reports.view_generatedreport"
    model = GeneratedReport
    template_name = "backoffice/reports/generated_list.html"
    context_object_name = "generated"


class GeneratedReportDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "reports.view_generatedreport"
    model = GeneratedReport
    template_name = "backoffice/reports/generated_detail.html"


class ReportGenerateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Genera el reporte de forma síncrona y lo guarda en GeneratedReport.
    Para ejecuciones largas usar Celery: en ese caso esta view encola la tarea y devuelve el ID.
    """
    permission_required = "reports.add_generatedreport"

    def post(self, request, pk):
        definition = get_object_or_404(ReportDefinition, pk=pk)
        # leer params desde JSON o form data
        if request.content_type == "application/json":
            try:
                params = json.loads(request.body.decode("utf-8"))
            except Exception:
                params = {}
        else:
            # Merge POST keys + definition.default_parameters
            params = dict(definition.default_parameters or {})
            params.update({k: v for k, v in request.POST.items() if k != "csrfmiddlewaretoken"})

        fmt = params.get("format") or (definition.export_formats[0] if definition.export_formats else "xlsx")
        gen = GeneratedReport.objects.create(
            definition=definition,
            report_label=definition.name,
            parameters=params,
            generated_by=request.user,
            status="running",
            format=fmt,
            started_at=timezone.now()
        )

        try:
            rows, columns = ReportService.run(definition, params or definition.default_parameters)
            gen.preview = rows[:50] if rows else []
            gen.rows_count = len(rows)

            # export
            if fmt == "xlsx":
                out = ReportService.to_xlsx_bytes(rows, columns)
                ext = "xlsx"
            elif fmt == "csv":
                out = ReportService.to_csv_bytes(rows, columns)
                ext = "csv"
            elif fmt == "pdf":
                out = ReportService.to_pdf_bytes(rows, columns, title=definition.name)
                ext = "pdf"
            else:
                out = ReportService.to_json_bytes(rows)
                ext = "json"

            filename = f"{definition.slug}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            # guardar bytes en FileField
            gen.file.save(filename, ContentFile(out), save=False)
            gen.finished_at = timezone.now()
            gen.status = "completed"
            gen.save()

            # auditoría
            AuditLog.log_action(
                request=request,
                user=request.user,
                action="generate_report",
                model=ReportDefinition,
                obj={"id": definition.pk, "slug": definition.slug},
                description=f"Generó reporte {definition.name} formato {fmt}"
            )

            messages.success(request, "Reporte generado correctamente.")
            return redirect(reverse("backoffice:reports:generated_detail", args=[gen.pk]))

        except Exception as e:
            gen.status = "failed"
            gen.error_message = str(e)
            gen.finished_at = timezone.now()
            gen.save()
            AuditLog.log_action(
                request=request,
                user=request.user,
                action="generate_report_failed",
                model=ReportDefinition,
                obj={"id": definition.pk, "slug": definition.slug},
                description=str(e)
            )
            messages.error(request, f"Error generando reporte: {e}")
            return redirect(reverse("reports:definition_list"))


class GeneratedReportDownloadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "reports.view_generatedreport"

    def get(self, request, pk):
        gen = get_object_or_404(GeneratedReport, pk=pk)
        if not gen.file:
            raise Http404("Archivo no disponible.")
        # FileResponse sirve streaming seguro
        return FileResponse(gen.file.open("rb"), as_attachment=True, filename=os.path.basename(gen.file.name))
