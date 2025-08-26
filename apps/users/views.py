from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import EmailTokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, SetPasswordForm
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages


User = get_user_model()

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "username": request.user.username,
            "email": request.user.email,
            "roles": [role.name for role in request.user.roles.all()]
        })

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer

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
            qs = qs.filter(username__icontains=search) | qs.filter(email__icontains=search)
        group = self.request.GET.get("group")
        if group:
            qs = qs.filter(groups__id=group)
        return qs


class UserDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = User
    template_name = "backoffice/users/detail.html"
    context_object_name = "user_obj"
    permission_required = "auth.view_user"


class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "backoffice/users/create.html"
    success_url = reverse_lazy("backoffice:users:list")
    permission_required = "auth.add_user"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Usuario creado correctamente.")
        return response


class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = UserChangeForm
    template_name = "backoffice/users/update.html"
    success_url = reverse_lazy("backoffice:users:list")
    permission_required = "auth.change_user"

    def form_valid(self, form):
        # Evitar que un usuario se quite todos sus grupos
        if self.request.user == self.object and not form.cleaned_data["groups"]:
            form.add_error("groups", "No puedes quitarte todos tus grupos.")
            return self.form_invalid(form)
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


# ========== ACTIVAR/DESACTIVAR ==========
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


# ========== CAMBIAR CONTRASEÑA DE OTRO USUARIO ==========
class UserSetPasswordView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = SetPasswordForm
    template_name = "backoffice/users/set_password.html"
    success_url = reverse_lazy("backoffice:users:list")
    permission_required = "auth.change_user"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.get_object()
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Contraseña actualizada correctamente.")
        return super().form_valid(form)
