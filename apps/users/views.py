from django.db.models import Q, Count
from django.contrib.auth.models import Group
from django.utils.timezone import now, timedelta
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import get_user_model

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import EmailTokenObtainPairSerializer
from .models import AuditLog
from .forms import CustomUserCreationForm, CustomUserChangeForm

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
        qs = User.objects.all().select_related()
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        group = self.request.GET.get("group")
        if group:
            qs = qs.filter(groups__name__iexact=group)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_users"] = User.objects.count()
        context["active_users"] = User.objects.filter(is_active=True).count()
        context["inactive_users"] = User.objects.filter(is_active=False).count()
        context["users_by_role"] = (
            User.objects.values("groups__name")
            .annotate(count=Count("id"))
            .order_by()
        )
        return context


class UserDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = User
    template_name = "backoffice/users/detail.html"
    context_object_name = "user_obj"
    permission_required = "auth.view_user"


class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = "backoffice/users/create.html"
    success_url = reverse_lazy("users:list")
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
    success_url = reverse_lazy("users:list")
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
    success_url = reverse_lazy("users:list")
    permission_required = "auth.delete_user"

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj == request.user:
            messages.error(request, "No puedes eliminarte a ti mismo.")
            return redirect("users:list")
        messages.success(request, f"Usuario {obj.username} eliminado correctamente.")
        return super().delete(request, *args, **kwargs)


class UserToggleActiveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "auth.change_user"

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, "No puedes desactivarte a ti mismo.")
            return redirect("users:list")
        user.is_active = not user.is_active
        user.save()
        messages.success(request, f"Usuario {user.username} {'activado' if user.is_active else 'desactivado'}.")
        return redirect("users:list")


class UserSetPasswordView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = SetPasswordForm
    template_name = "backoffice/users/set_password.html"
    success_url = reverse_lazy("users:list")
    permission_required = "auth.change_user"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.get_object()
        return kwargs

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
        user_id = self.request.GET.get("user")
        period = self.request.GET.get("period")  # day, week, month, year
        date = self.request.GET.get("date")      # formato YYYY-MM-DD

        if user_id:
            queryset = queryset.filter(user_id=user_id)
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
                queryset = queryset.filter(created_at__year=now_.year, created_at__month=now_.month)
            elif period == "year":
                queryset = queryset.filter(created_at__year=now_.year)
        return queryset


class AuditLogDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = AuditLog
    template_name = "backoffice/users/auditlog_detail.html"
    context_object_name = "log"
    permission_required = "users.view_auditlog"
