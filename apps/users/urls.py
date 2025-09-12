from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    EmailTokenObtainPairView, ProfileView,
    UserListView, UserCreateView, UserDetailView,
    UserUpdateView, UserDeleteView, UserToggleActiveView,
    UserSetPasswordView, AuditLogListView, AuditLogDetailView, UserProfileUpdateView,
    AuditLogAccessDetailView, AuditLogAccessListView, AuditLogAccessDeleteAllView,
)

app_name = "users"

urlpatterns = [
    # ========== AUTH ==========
    path("login/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair_email"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", ProfileView.as_view(), name="profile"),

    # ========== CRUD USUARIOS ==========
    path("", UserListView.as_view(), name="list"),
    path("crear/", UserCreateView.as_view(), name="create"),
    path("<int:pk>/", UserDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", UserUpdateView.as_view(), name="edit"),
    path("<int:pk>/eliminar/", UserDeleteView.as_view(), name="delete"),
    path("<int:pk>/toggle-active/", UserToggleActiveView.as_view(), name="toggle_active"),
    path("<int:pk>/password/set/", UserSetPasswordView.as_view(), name="set_password"),

    # ========== AUDITORÍA ==========
    path("auditlogs/", AuditLogListView.as_view(), name="auditlog_list"),
    path("audit/<int:pk>/", AuditLogDetailView.as_view(), name="audit_detail"),

    # Auditoría de accesos / navegación
    path("auditlogs/accesos/", AuditLogAccessListView.as_view(), name="auditlog_access_list"),
    path("audit/acceso/<int:pk>/", AuditLogAccessDetailView.as_view(), name="audit_access_detail"),
    path("auditlogs/accesos/eliminar-todos/", AuditLogAccessDeleteAllView.as_view(), name="auditlog_access_delete_all"),

    # ========== CONFIGURACIONES DE USUARIO ==========
    path("configuraciones/actualizar/", UserProfileUpdateView.as_view(), name="actualizar_informacion_personal"),
]
