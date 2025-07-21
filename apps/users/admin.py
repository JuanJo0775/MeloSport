from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, Permission
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from .models import User, Role, AuditLog

# Desregistrar el Group admin por defecto si es necesario
admin.site.unregister(Group)


class UserRoleInline(admin.TabularInline):
    model = User.roles.through
    extra = 1
    verbose_name = "Rol asignado"
    verbose_name_plural = "Roles asignados"
    autocomplete_fields = ['role']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'permission_count', 'user_count', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)
    readonly_fields = ('created_at', 'updated_at')


    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        ('Permisos', {
            'fields': ('permissions',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def permission_count(self, obj):
        return obj.permissions.count()

    permission_count.short_description = "Permisos"

    def user_count(self, obj):
        return obj.user_set.count()

    user_count.short_description = "Usuarios"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('permissions', 'user_set')


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'full_name', 'phone', 'is_active', 'last_login', 'role_list')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'roles', 'last_login')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    inlines = [UserRoleInline]

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Fechas importantes', {
            'fields': ('last_login', 'date_joined', 'last_access'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'first_name', 'last_name', 'phone'),
        }),
    )

    readonly_fields = ('last_login', 'date_joined', 'last_access')

    def full_name(self, obj):
        return obj.get_full_name()

    full_name.short_description = "Nombre Completo"

    def role_list(self, obj):
        return ", ".join([role.name for role in obj.roles.all()[:3]]) + ("..." if obj.roles.count() > 3 else "")

    role_list.short_description = "Roles"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('roles')

    actions = ['activate_users', 'deactivate_users']

    @admin.action(description="Activar usuarios seleccionados")
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} usuarios activados.")

    @admin.action(description="Desactivar usuarios seleccionados")
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} usuarios desactivados.")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user_link', 'model', 'object_id', 'created_at', 'ip_address')
    list_filter = ('action', 'model', 'created_at')
    search_fields = ('user__username', 'action', 'model', 'object_id', 'ip_address')
    readonly_fields = ('user', 'action', 'model', 'object_id', 'data', 'ip_address', 'created_at', 'data_prettified')
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('user', 'action', 'model', 'object_id')
        }),
        ('Detalles', {
            'fields': ('data_prettified', 'ip_address', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def user_link(self, obj):
        if obj.user:
            url = reverse("admin:users_user_change", args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user)
        return "-"

    user_link.short_description = "Usuario"
    user_link.admin_order_field = 'user'

    def data_prettified(self, obj):
        import json
        from pygments import highlight
        from pygments.lexers import JsonLexer
        from pygments.formatters import HtmlFormatter
        from django.utils.safestring import mark_safe

        if not obj.data:
            return "-"

        response = json.dumps(obj.data, indent=2, ensure_ascii=False)
        formatter = HtmlFormatter(style='colorful')
        response = highlight(response, JsonLexer(), formatter)
        style = "<style>" + formatter.get_style_defs() + "</style><br>"
        return mark_safe(style + response)

    data_prettified.short_description = "Datos (formateados)"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')