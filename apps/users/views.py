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
from django.contrib.auth import get_user_model

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import EmailTokenObtainPairSerializer
from .models import AuditLog
from .forms import CustomUserCreationForm, CustomUserChangeForm, CustomPasswordChangeForm

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
        queryset = AuditLog.objects.select_related("user").all()
        search = self.request.GET.get("q")
        period = self.request.GET.get("period")  # day, week, month, year
        date = self.request.GET.get("date")      # formato YYYY-MM-DD

        # 🔎 búsqueda flexible por usuario
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )

        if date:
            queryset = queryset.filter(created_at__date=date)

        if period:
            now_ = now()
            if period == "day":
                queryset = queryset.filter(created_at__date=now_.date())
            elif period == "week":
                start_week = now_ - timedelta(days=now_.weekday())
                queryset = queryset.filter(created_at__date__gte=start_week.date())
            elif period == "month":
                queryset = queryset.filter(
                    created_at__year=now_.year,
                    created_at__month=now_.month
                )
            elif period == "year":
                queryset = queryset.filter(created_at__year=now_.year)

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Último modelo afectado (seguro, sin problemas con paginación)
        last_log = AuditLog.objects.order_by("-created_at").first()
        ctx["last_model"] = last_log.model if last_log else "-"

        # Total usuarios únicos
        ctx["unique_users"] = AuditLog.objects.values("user").distinct().count()

        # Total modelos distintos
        ctx["unique_models"] = AuditLog.objects.values("model").distinct().count()

        # Total de registros de auditoría (sin paginación)
        ctx["total_logs"] = AuditLog.objects.count()

        return ctx


class AuditLogDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = AuditLog
    template_name = "backoffice/users/auditlog_detail.html"
    context_object_name = "log"
    permission_required = "users.view_auditlog"

    def get_queryset(self):
        return AuditLog.objects.select_related("user")
