from django.urls import path, include
from MeloSport import settings
from . import views
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),

                  path("backoffice/password_reset/",
                       auth_views.PasswordResetView.as_view(template_name="backoffice/password_reset.html"),
                       name="password_reset"),
                  path("backoffice/password_reset/done/",
                       auth_views.PasswordResetDoneView.as_view(template_name="backoffice/password_reset_done.html"),
                       name="password_reset_done"),
                  path("backoffice/reset/<uidb64>/<token>/",
                       auth_views.PasswordResetConfirmView.as_view(
                           template_name="backoffice/password_reset_confirm.html"),
                       name="password_reset_confirm"),
                  path("backoffice/reset/done/",
                       auth_views.PasswordResetCompleteView.as_view(
                           template_name="backoffice/password_reset_complete.html"),
                       name="password_reset_complete"),

    # Rutas internas del backoffice
    path('products/', include('apps.products.urls')),
    path('categories/', include('apps.categories.urls')),
    path('reports/', include('apps.reports.urls')),
    path('users/', include('apps.users.urls')),
    path('database/', include('apps.database.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
