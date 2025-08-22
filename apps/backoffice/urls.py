from django.urls import path, include
from MeloSport import settings
from . import views
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView


# 👇 Namespace para evitar conflictos de nombres
app_name = "backoffice"

urlpatterns = [
    # Dashboard y login
    path("dashboard/", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),

    # Reset de contraseña (sin prefijos duplicados)
    path("password_reset/",
         auth_views.PasswordResetView.as_view(template_name="login/password_reset.html"),
         name="password_reset"),
    path("password_reset/done/",
         auth_views.PasswordResetDoneView.as_view(template_name="login/password_reset_done.html"),
         name="password_reset_done"),
    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(
             template_name="login/password_reset_confirm.html"),
         name="password_reset_confirm"),
    path("reset/done/",
         auth_views.PasswordResetCompleteView.as_view(
             template_name="login/password_reset_complete.html"),
         name="password_reset_complete"),

    # Logout (redirige al login del backoffice)
    path("logout/", LogoutView.as_view(next_page="backoffice:login"), name="logout"),

    # Perfil y configuraciones
    path("perfil/", views.perfil_view, name="perfil"),
    path("configuraciones/", views.configuraciones_view, name="configuraciones"),
    path("cambiar-password/",
         auth_views.PasswordChangeView.as_view(
             template_name="perfil/cambiar_password.html"
         ),
         name="cambiar_password"),
    path("cambiar-password/done/",
         auth_views.PasswordChangeDoneView.as_view(
             template_name="perfil/cambiar_password_done.html"
         ),
         name="password_change_done"),

    path("categories/", include(("apps.categories.urls", "categories"), namespace="categories")),

    # 📌 Rutas dummy (temporal mientras se crean los módulos reales)
    path("productos/crear/", views.placeholder_view, name="product-create"),
    path("inventario/subir/", views.placeholder_view, name="inventory-upload"),
    path("reportes/lista/", views.placeholder_view, name="report-list"),
    path("respaldos/crear/", views.placeholder_view, name="backup-create"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
