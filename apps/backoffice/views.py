# apps/backoffice/views.py
from django.db.models import Q
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import Permission
from django.db.models import F

from apps.categories.models import Category, AbsoluteCategory
from apps.products.models import Product
from apps.users.models import AuditLog


# ==========================
# Dashboard protegido
# ==========================
@login_required(login_url="/backoffice/login/")
def dashboard(request):
    user = request.user

    products = Product.objects.all()

    total_products = products.count()
    inventory_value = sum(p.stock * p.price for p in products)  # ✅ usa property stock

    # Alertas de stock calculadas en Python (no con _stock directo)
    low_stock_qs = [p for p in products if 0 < p.stock <= p.min_stock]
    no_stock_qs = [p for p in products if p.stock == 0]

    qs = AuditLog.objects.filter(user__isnull=False)

    if user.is_superuser:
        recent_activity = qs.order_by("-created_at")[:10]
    else:
        allowed_models = set()
        for perm in user.get_all_permissions():
            try:
                app_label, codename = perm.split(".")
                if codename.startswith(("view_", "add_", "change_", "delete_")):
                    model_name = codename.split("_", 1)[1]
                    allowed_models.add(model_name.capitalize())
            except ValueError:
                continue

        recent_activity = (
            qs.filter(
                action__in=["create", "update", "delete"],
                model__in=allowed_models
            )
            .order_by("-created_at")[:10]
        )

    context = {
        "last_login": user.last_access,
        "current_login": user.current_login,
        "stats": {
            "products_count": total_products,
            "inventory_value": inventory_value,
            "low_stock": len(low_stock_qs),
            "no_stock": len(no_stock_qs),
            "categories_count": Category.objects.count(),
            "absolute_categories_count": AbsoluteCategory.objects.count(),
        },
        "stock_alerts": low_stock_qs + no_stock_qs,
        "recent_activity": recent_activity,
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
            user.update_login_timestamps()
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
@permission_required("products.view_product", raise_exception=True)
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
