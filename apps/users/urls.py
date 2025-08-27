from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    EmailTokenObtainPairView, ProfileView,
    UserListView, UserCreateView, UserDetailView,
    UserUpdateView, UserDeleteView, UserToggleActiveView,
    UserSetPasswordView, AuditLogListView, AuditLogDetailView
)

app_name = "users"

urlpatterns = [
    # Auth
    path('login/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair_email'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),

    # CRUD Usuarios
    path("", UserListView.as_view(), name="list"),
    path("crear/", UserCreateView.as_view(), name="create"),
    path("<int:pk>/", UserDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", UserUpdateView.as_view(), name="edit"),
    path("<int:pk>/eliminar/", UserDeleteView.as_view(), name="delete"),
    path("<int:pk>/toggle-active/", UserToggleActiveView.as_view(), name="toggle_active"),
    path("<int:pk>/password/set/", UserSetPasswordView.as_view(), name="set_password"),

    # Auditoría
    path("auditlogs/", AuditLogListView.as_view(), name="auditlog_list"),
    path("audit/<int:pk>/", AuditLogDetailView.as_view(), name="audit_detail"),
]
