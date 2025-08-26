from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import EmailTokenObtainPairView, ProfileView
from . import views

app_name = "users"

urlpatterns = [
    path('login/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair_email'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),

    path("", views.UserListView.as_view(), name="list"),
    path("crear/", views.UserCreateView.as_view(), name="create"),
    path("<int:pk>/", views.UserDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.UserUpdateView.as_view(), name="edit"),
    path("<int:pk>/eliminar/", views.UserDeleteView.as_view(), name="delete"),
    path("<int:pk>/toggle-active/", views.UserToggleActiveView.as_view(), name="toggle_active"),
    path("<int:pk>/password/set/", views.UserSetPasswordView.as_view(), name="password_set"),

    path("audit/", views.AuditLogListView.as_view(), name="audit_list"),
    path("audit/<int:pk>/", views.AuditLogDetailView.as_view(), name="audit_detail"),

]
