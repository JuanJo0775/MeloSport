# apps/backoffice/views.py
import json
from datetime import datetime, timedelta, time as dt_time
from django.db.models import Q, F, Sum
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import Permission
from django.db.models.functions import TruncDate
from django.core.serializers.json import DjangoJSONEncoder

from apps.categories.models import Category, AbsoluteCategory
from apps.products.models import Product, InventoryMovement
from apps.billing.models import InvoiceItem
from apps.users.models import AuditLog


# ==========================
# Dashboard protegido
# ==========================
@login_required(login_url="/backoffice/login/")
def dashboard(request):
    user = request.user

    # --- Productos e inventario
    products = Product.objects.all()
    total_products = products.count()
    inventory_value = sum((getattr(p, "stock", 0) or 0) * (getattr(p, "price", 0) or 0) for p in products)
    low_stock_qs = [p for p in products if 0 < (getattr(p, "stock", 0) or 0) <= (getattr(p, "min_stock", 0) or 0)]
    no_stock_qs = [p for p in products if (getattr(p, "stock", 0) or 0) == 0]

    # --- Auditoría (igual que antes)
    qs = AuditLog.objects.filter(user__isnull=False)
    if user.is_superuser:
        recent_activity = qs.order_by("-created_at")[:10]
    else:
        allowed_models = set()
        for perm in user.get_all_permissions():
            try:
                _, codename = perm.split(".")
                if codename.startswith(("view_", "add_", "change_", "delete_")):
                    model_name = codename.split("_", 1)[1]
                    allowed_models.add(model_name.capitalize())
            except ValueError:
                continue
        recent_activity = (
            qs.filter(action__in=["create", "update", "delete"], model__in=allowed_models)
            .order_by("-created_at")[:10]
        )

    # =============================
    # Manejo de fechas dinámico
    # =============================
    today = timezone.localdate()
    tz = timezone.get_current_timezone()

    # --- semana por defecto = semana actual
    iso_year, iso_week, _ = today.isocalendar()

    week_param = request.GET.get("week")
    if week_param:
        # El input type="week" devuelve algo como "2025-W39"
        try:
            year_str, week_str = week_param.split("-W")
            year, week = int(year_str), int(week_str)
        except ValueError:
            year, week = iso_year, iso_week
    else:
        year, week = iso_year, iso_week

    # Calcular fecha inicial y final de la semana seleccionada
    # ISO: lunes=1, domingo=7
    first_day = datetime.fromisocalendar(year, week, 1).date()
    last_day = datetime.fromisocalendar(year, week, 7).date()
    date_from, date_to = first_day, last_day

    # Rango datetime aware
    start_dt = timezone.make_aware(datetime.combine(date_from, dt_time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(date_to, dt_time.max), tz)

    # --- Movimientos inventario en la semana seleccionada
    movements_qs = (
        InventoryMovement.objects.filter(created_at__range=(start_dt, end_dt))
        .exclude(movement_type="reserve")
        .annotate(day=TruncDate("created_at"))
        .values("day", "movement_type")
        .annotate(total_qty=Sum("quantity"))
    )

    mov_map = {}
    for m in movements_qs:
        d = m["day"]
        if not d:
            continue
        d_key = d.isoformat()
        mov_map.setdefault(d_key, {})[m["movement_type"]] = int(m["total_qty"] or 0)

    labels, entries, exits = [], [], []
    cur = date_from
    while cur <= date_to:
        key = cur.isoformat()
        labels.append(key)
        day_map = mov_map.get(key, {})
        entries.append(day_map.get("in", 0))
        exits.append(day_map.get("out", 0))
        cur += timedelta(days=1)

    total_entries = sum(entries)
    total_exits = sum(exits)

    # =============================
    # Top productos vendidos
    # =============================
    day_param = request.GET.get("day")

    top_qs = InvoiceItem.objects.filter(invoice__status="completed")

    if day_param:
        # filtro por día específico
        try:
            d = datetime.strptime(day_param, "%Y-%m-%d").date()
            d_start = timezone.make_aware(datetime.combine(d, dt_time.min), tz)
            d_end = timezone.make_aware(datetime.combine(d, dt_time.max), tz)
            top_qs = top_qs.filter(invoice__created_at__range=(d_start, d_end))
        except ValueError:
            pass
    elif week_param:
        # filtro por la semana seleccionada
        top_qs = top_qs.filter(invoice__created_at__range=(start_dt, end_dt))
    else:
        # sin filtro = todos los tiempos
        pass

    top_qs = (
        top_qs.values("product_id", "product__name", "product__sku", "variant__color", "variant__size")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")[:10]
    )

    top_products = []
    for t in top_qs:
        name = t.get("product__name") or "Sin nombre"
        extras = []
        if t.get("variant__color"):
            extras.append(t["variant__color"])
        if t.get("variant__size"):
            extras.append(t["variant__size"])
        if extras:
            name = f"{name} ({', '.join(extras)})"
        top_products.append({
            "product_id": t["product_id"],
            "name": name,
            "sku": t.get("product__sku") or "N/A",
            "qty": int(t.get("total_qty") or 0),
        })

    # --- Contexto
    context = {
        "last_login": getattr(user, "last_access", None),
        "current_login": getattr(user, "current_login", None),
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
        "chart_labels_json": json.dumps(labels, cls=DjangoJSONEncoder),
        "chart_entries_json": json.dumps(entries, cls=DjangoJSONEncoder),
        "chart_exits_json": json.dumps(exits, cls=DjangoJSONEncoder),
        "total_entries": total_entries,
        "total_exits": total_exits,
        "top_products": top_products,
        "top_products_labels_json": json.dumps([p["name"] for p in top_products], cls=DjangoJSONEncoder),
        "top_products_qty_json": json.dumps([p["qty"] for p in top_products], cls=DjangoJSONEncoder),
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

@login_required(login_url="/backoffice/login/")
def perfil_view(request):
    return render(request, "perfil/perfil.html")


@login_required(login_url="/backoffice/login/")
def configuraciones_view(request):
    return render(request, "perfil/configuraciones.html")


@login_required(login_url="/backoffice/login/")
def placeholder_view(request):
    return render(request, "backoffice/placeholder.html")


def error_404_view(request, exception):
    return render(request, 'errors/404.html', status=404)

def error_500_view(request):
    return render(request, 'errors/500.html', status=500)

def error_403_view(request, exception):
    return render(request, 'errors/403.html', status=403)

def error_401_view(request, exception):
    return render(request, 'errors/401.html', status=400)