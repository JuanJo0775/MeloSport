from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from apps.categories.models import Category, AbsoluteCategory


# Dashboard protegido: requiere login
@login_required(login_url="/backoffice/login/")
def dashboard(request):
    context = {
        "stats": {
            "categories_count": Category.objects.count(),
            "absolute_categories_count": AbsoluteCategory.objects.count(),
        }
    }
    return render(request, "backoffice/dashboard.html", context)


# Login con rate limiting
@ratelimit(key='ip', rate='5/m', block=True)
def login_view(request):
    if request.method == "POST":
        username_or_email = request.POST.get("username")
        password = request.POST.get("password")

        # Usa el backend custom (email o username)
        user = authenticate(request, username=username_or_email, password=password)

        if user is not None:
            login(request, user)
            return redirect("backoffice:dashboard")  # ✅ con namespace
        else:
            messages.error(request, "Credenciales inválidas. Inténtalo de nuevo.")

    return render(request, "login/login.html")


# Logout
@login_required(login_url="/backoffice/login/")
def logout_view(request):
    logout(request)
    return redirect("backoffice:login")


# Ejemplo de vista protegida por permisos
@login_required(login_url="/backoffice/login/")
@permission_required("productos.view_producto", raise_exception=True)
def productos(request):
    return render(request, "backoffice/productos.html")


@login_required(login_url="/backoffice/login/")
def perfil_view(request):
    return render(request, "perfil/perfil.html")


@login_required(login_url="/backoffice/login/")
def configuraciones_view(request):
    return render(request, "perfil/configuraciones.html")




@login_required(login_url="/backoffice/login/")
def placeholder_view(request):
    return render(request, "backoffice/placeholder.html")