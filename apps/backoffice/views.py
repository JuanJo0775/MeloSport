from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django_ratelimit.decorators import ratelimit
from django.contrib import messages

# Dashboard protegido: requiere login
@login_required(login_url="/backoffice/login/")
def dashboard(request):
    return render(request, "backoffice/dashboard.html")

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
            return redirect("dashboard")  # redirige al dashboard
        else:
            messages.error(request, "Credenciales inválidas. Inténtalo de nuevo.")

    return render(request, "backoffice/login.html")

# Logout
@login_required(login_url="/backoffice/login/")
def logout_view(request):
    logout(request)
    return redirect("login")

# Ejemplo de vista protegida por permisos
@login_required(login_url="/backoffice/login/")
@permission_required("productos.view_producto", raise_exception=True)
def productos(request):
    return render(request, "backoffice/productos.html")
