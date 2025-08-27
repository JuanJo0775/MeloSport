# apps/users/views.py

from django.db.models import Q, Count
from django.contrib.auth.models import Group
from django.utils.timezone import now, timedelta
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, View, FormView
)
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import get_user_model, authenticate

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import EmailTokenObtainPairSerializer
from .models import AuditLog
from .forms import CustomUserCreationForm, CustomUserChangeForm, CustomPasswordChangeForm, UserProfileUpdateForm

User = get_user_model()

# ========== AUTH ==========

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "username": request.user.username,
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "phone": getattr(request.user, "phone", None),
            "roles": [g.name for g in request.user.groups.all()],
            "is_active": request.user.is_active,
        })


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


# ========== CRUD USUARIOS ==========

class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = "backoffice/users/list.html"
    context_object_name = "users"
    paginate_by = 10
    permission_required = "auth.view_user"

    def get_queryset(self):
        qs = User.objects.all().prefetch_related("groups")
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        group_id = self.request.GET.get("group_id")
        if group_id:
            qs = qs.filter(groups__id=group_id)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        admin_group = Group.objects.filter(name__iexact="Administrador").first()
        vendor_group = Group.objects.filter(name__iexact="Vendedor").first()

        ctx.update({
            "total_users": User.objects.count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "vendors": User.objects.filter(groups=vendor_group).count() if vendor_group else 0,
            "admins": User.objects.filter(groups=admin_group).count() if admin_group else 0,
            "groups": list(Group.objects.order_by("name").values("id", "name")),
            "users_by_role": (
                User.objects.values("groups__name")
                .annotate(count=Count("id"))
                .order_by()
            ),
        })
        return ctx


class UserDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = User
    template_name = "backoffice/users/detail.html"
    context_object_name = "user_obj"
    permission_required = "auth.view_user"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = self.get_object()

        # Últimas 10 auditorías del usuario
        if self.request.user.has_perm("users.view_auditlog"):
            context["user_audits"] = AuditLog.objects.filter(user=user_obj).order_by("-created_at")[:10]
        else:
            context["user_audits"] = []

        return context


class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = "backoffice/users/create.html"
    success_url = reverse_lazy("backoffice:users:list")
    permission_required = "auth.add_user"

    def form_valid(self, form):
        user = form.save()
        role = form.cleaned_data.get("role")
        if role:
            user.groups.add(role)

        # Auditoría
        AuditLog.log_action(
            user=self.request.user,
            action="create",
            model=self.model,
            obj=user,
            request=self.request,
            description=f"Creó usuario {user.username}"
        )

        messages.success(self.request, "Usuario creado correctamente.")
        return super().form_valid(form)


class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = "backoffice/users/update.html"
    success_url = reverse_lazy("backoffice:users:list")
    permission_required = "auth.change_user"

    def form_valid(self, form):
        user = form.save()
        role = form.cleaned_data.get("role")
        if role:
            user.groups.clear()
            user.groups.add(role)

        # Auditoría
        AuditLog.log_action(
            user=self.request.user,
            action="update",
            model=self.model,
            obj=user,
            request=self.request,
            description=f"Actualizó usuario {user.username}"
        )

        messages.success(self.request, "Usuario actualizado correctamente.")
        return super().form_valid(form)


class UserDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = User
    template_name = "backoffice/users/confirm_delete.html"
    success_url = reverse_lazy("backoffice:users:list")
    permission_required = "auth.delete_user"

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj == request.user:
            messages.error(request, "No puedes eliminarte a ti mismo.")
            return redirect("backoffice:users:list")

        # Auditoría
        AuditLog.log_action(
            user=request.user,
            action="delete",
            model=self.model,
            obj=obj,
            request=request,
            description=f"Eliminó usuario {obj.username}"
        )

        messages.success(request, f"Usuario {obj.username} eliminado correctamente.")
        return super().delete(request, *args, **kwargs)


class UserToggleActiveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "auth.change_user"

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, "No puedes desactivarte a ti mismo.")
            return redirect("backoffice:users:list")

        user.is_active = not user.is_active
        user.save()

        # Auditoría
        AuditLog.log_action(
            user=request.user,
            action="update",
            model=User,
            obj=user,
            request=request,
            description=f"{'Activó' if user.is_active else 'Desactivó'} usuario {user.username}"
        )

        messages.success(request, f"Usuario {user.username} {'activado' if user.is_active else 'desactivado'}.")
        return redirect("backoffice:users:list")


class UserSetPasswordView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "backoffice/users/set_password.html"
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy("backoffice:users:list")
    permission_required = "auth.change_user"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.user_obj = get_object_or_404(User, pk=self.kwargs["pk"])
        kwargs["user"] = self.user_obj
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.user_obj
        return ctx

    def form_valid(self, form):
        form.save()

        # Auditoría
        AuditLog.log_action(
            user=self.request.user,
            action="update",
            model=User,
            obj=self.user_obj,
            request=self.request,
            description=f"Cambió la contraseña del usuario {self.user_obj.username}"
        )

        messages.success(self.request, "Contraseña actualizada correctamente.")
        return super().form_valid(form)


# ========== AUDITORÍA ==========
class AuditLogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AuditLog
    template_name = "backoffice/users/auditlog_list.html"
    context_object_name = "logs"
    paginate_by = 20
    permission_required = "users.view_auditlog"

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user").all()

        # parámetros
        q = (self.request.GET.get("q") or "").strip()
        only_users = self.request.GET.get("only_users")
        user_id = self.request.GET.get("user")
        date = self.request.GET.get("date")
        period = self.request.GET.get("period")  # day, week, month, year

        # filtrar por usuario específico (viene del enlace "ver auditoría" en detalle de usuario)
        if user_id:
            try:
                qs = qs.filter(user_id=int(user_id))
            except (TypeError, ValueError):
                pass

        # solo registros con usuario (excluir "Sistema")
        if only_users in ("1", "true", "True", "on"):
            qs = qs.filter(user__isnull=False)

        # búsqueda flexible
        if q:
            base_q = (
                Q(user__username__icontains=q) |
                Q(user__email__icontains=q) |
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q) |
                Q(action__icontains=q) |
                Q(model__icontains=q) |
                Q(description__icontains=q)
            )
            qs = qs.filter(base_q)

            # intentar búsqueda en JSONField `data` si el motor lo soporta (seguro en Postgres JSONB).
            try:
                qs = qs | AuditLog.objects.filter(data__icontains=q)
            except Exception:
                # si el backend no soporta data__icontains o lanza error, lo ignoramos
                pass

        # filtro por fecha exacta
        if date:
            qs = qs.filter(created_at__date=date)

        # filtro por periodo relativo
        if period:
            now_ = now()
            if period == "day":
                qs = qs.filter(created_at__date=now_.date())
            elif period == "week":
                start_week = now_ - timedelta(days=now_.weekday())
                qs = qs.filter(created_at__date__gte=start_week.date())
            elif period == "month":
                qs = qs.filter(created_at__year=now_.year, created_at__month=now_.month)
            elif period == "year":
                qs = qs.filter(created_at__year=now_.year)

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["last_model"] = AuditLog.objects.order_by("-created_at").values_list("model", flat=True).first() or "-"
        ctx["unique_users"] = AuditLog.objects.values("user").distinct().count()
        ctx["unique_models"] = AuditLog.objects.values("model").distinct().count()
        ctx["total_logs"] = AuditLog.objects.count()
        # para mantener el estado del filtro en la plantilla
        ctx["only_users"] = self.request.GET.get("only_users", "")
        return ctx


class AuditLogDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Vista de detalle de un registro de auditoría."""
    model = AuditLog
    template_name = "backoffice/users/auditlog_detail.html"
    context_object_name = "log"
    permission_required = "users.view_auditlog"

    def get_queryset(self):
        return AuditLog.objects.select_related("user")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["data_pretty"] = self.object.get_data_display()
        return ctx


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileUpdateForm
    template_name = "perfil/actualizar_informacion.html"
    success_url = reverse_lazy("backoffice:configuraciones")

    def get_object(self, queryset=None):
        # 🔒 siempre devuelve al usuario autenticado
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Tu información ha sido actualizada correctamente.")
        return super().form_valid(form)