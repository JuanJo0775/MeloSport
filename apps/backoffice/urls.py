from django.urls import path, include
from MeloSport import settings
from . import views
from django.conf.urls.static import static

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),




    # Rutas internas del backoffice
    path('products/', include('apps.products.urls')),
    path('categories/', include('apps.categories.urls')),
    path('reports/', include('apps.reports.urls')),
    path('users/', include('apps.users.urls')),
    path('database/', include('apps.database.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
