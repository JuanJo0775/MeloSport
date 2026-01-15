from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView

from . import views
from .views_auth import (
    BackofficePasswordChangeView,
    BackofficePasswordChangeDoneView,
    BackofficePasswordResetView,
    BackofficePasswordResetDoneView,
    BackofficePasswordResetConfirmView,
    BackofficePasswordResetCompleteView,
)

app_name = "backoffice"

urlpatterns = [
    # ==========================
    # Dashboard y login
    # ==========================
    path("dashboard/", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),

    # ==========================
    # Reset de contraseña
    # ==========================
    path("password_reset/", BackofficePasswordResetView.as_view(), name="password_reset"),
    path("password_reset/done/", BackofficePasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", BackofficePasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", BackofficePasswordResetCompleteView.as_view(), name="password_reset_complete"),

    # ==========================
    # Cambiar contraseña
    # ==========================
    path("cambiar-password/", BackofficePasswordChangeView.as_view(), name="cambiar_password"),
    path("cambiar-password/done/", BackofficePasswordChangeDoneView.as_view(), name="password_change_done"),

    # ==========================
    # Logout
    # ==========================
    path("logout/", LogoutView.as_view(next_page="backoffice:login"), name="logout"),

    # ==========================
    # Perfil
    # ==========================
    path("perfil/", views.perfil_view, name="perfil"),
    path("configuraciones/", views.configuraciones_view, name="configuraciones"),

    # ==========================
    # Apps internas
    # ==========================
    path("categories/", include(("apps.categories.urls", "categories"), namespace="categories")),
    path("products/", include(("apps.products.urls", "products"), namespace="products")),
    path("database/", include(("apps.database.urls", "database"), namespace="database")),
    path("frontend/", include(("apps.frontend.urls", "frontend"), namespace="frontend")),
    path("users/", include(("apps.users.urls", "users"), namespace="users")),
    path("reports/", include(("apps.reports.urls", "reports"), namespace="reports")),
    path("billing/", include(("apps.billing.urls", "billing"), namespace="billing")),

    # ==========================
    # Rutas dummy
    # ==========================
    path("inventario/subir/", views.placeholder_view, name="inventory-upload"),
    path("reportes/lista/", views.placeholder_view, name="report-list"),
    path("respaldos/crear/", views.placeholder_view, name="backup-create"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
