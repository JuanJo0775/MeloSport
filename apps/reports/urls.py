# apps/reports/urls.py
from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportDefinitionListView.as_view(), name="definition_list"),
    path("create/", views.ReportDefinitionCreateView.as_view(), name="definition_create"),
    path("<int:pk>/edit/", views.ReportDefinitionUpdateView.as_view(), name="definition_update"),
    path("<int:pk>/generate/", views.ReportGenerateView.as_view(), name="definition_generate"),

    path("generated/", views.GeneratedReportListView.as_view(), name="generated_list"),
    path("generated/<int:pk>/", views.GeneratedReportDetailView.as_view(), name="generated_detail"),
    path("generated/<int:pk>/download/", views.GeneratedReportDownloadView.as_view(), name="generated_download"),
]
