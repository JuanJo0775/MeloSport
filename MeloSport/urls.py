"""
URL configuration for MeloSport project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import handler404, handler500, handler403, handler400
from django.shortcuts import render
from django.views.generic.base import RedirectView
from apps.backoffice.views import error_404_view, error_500_view, error_403_view, error_401_view

admin.site.site_header = "Administración de MeloSport"
admin.site.site_title = "MeloSport Admin"
admin.site.index_title = "Bienvenido al Panel de Administración"
urlpatterns = [
    path('', RedirectView.as_view(url='/backoffice/login/', permanent=False), name='root_redirect'),
    path('admin/', admin.site.urls),
    path('api/', include('apps.api.urls')),
    path('backoffice/', include(('apps.backoffice.urls', 'backoffice'), namespace='backoffice')),

    path("select2/", include("django_select2.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




handler404 = error_404_view
handler500 = error_500_view
handler403 = error_403_view
handler401 = error_401_view