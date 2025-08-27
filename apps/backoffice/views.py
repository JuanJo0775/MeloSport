# apps/backoffice/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from django.utils import timezone

from apps.categories.models import Category, AbsoluteCategory
from apps.users.models import AuditLog


# ==========================
# Dashboard protegido
# ==========================
@login_required(login_url="/backoffice/login/")
def dashboard(request):
    last_login = request.user.last_login
    current_login = timezone.localtime(timezone.now())  # 👈 convierte UTC → local

    context = {
        "last_login": timezone.localtime(last_login) if last_login else None,
        "current_login": current_login,
        "stats": {
            "categories_count": Category.objects.count(),
            "absolute_categories_count": AbsoluteCategory.objects.count(),
        }
    }
    return render(request, "backoffice/dashboard.html", context)


# ==========================
# Login con auditoría + rate limiting
# ==========================
@ratelimit(key="ip", rate="5/m", block=True)
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_active:
            login(request, user)

            # Registrar login exitoso
            AuditLog.log_action(
                request=request,
                user=user,
                action="login",
                model="User",
                obj=user,
                description="Inicio de sesión exitoso",
                extra_data={"username": username},
            )

            messages.success(request, f"Bienvenido {user.get_full_name() or user.username} 👋")
            return redirect("backoffice:dashboard")

        else:
            # Registrar intento fallido
            AuditLog.log_action(
                request=request,
                action="login",
                model="User",
                obj={"username": username},
                description="Intento de inicio de sesión fallido",
                extra_data={"reason": "Credenciales inválidas"},
            )

            messages.error(request, "Credenciales inválidas. Inténtalo de nuevo.")

    return render(request, "login/login.html")


# ==========================
# Logout con auditoría
# ==========================
@login_required(login_url="/backoffice/login/")
def logout_view(request):
    user = request.user

    # Registrar logout
    AuditLog.log_action(
        request=request,
        user=user,
        action="logout",
        model="User",
        obj=user,
        description="Cierre de sesión",
    )

    logout(request)
    request.session.flush()

    messages.info(request, "Sesión cerrada correctamente.")
    return redirect("backoffice:login")


# ==========================
# Vistas protegidas de ejemplo
# ==========================
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
