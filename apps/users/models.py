import json
from django.contrib.auth.models import AbstractUser
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    permissions = models.JSONField(default=dict)  # Almacenar permisos como JSON
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def has_permission(self, perm_codename):
        return self.permissions.filter(codename=perm_codename).exists()

    def __str__(self):
        return self.name


class User(AbstractUser):
    roles = models.ManyToManyField(Role, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    last_access = models.DateTimeField(null=True, blank=True)

    # Agrega estos campos para resolver los conflictos
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="melo_user_groups",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="melo_user_permissions",
        related_query_name="user",
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.get_full_name() or self.username


class AuditLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario"
    )
    action = models.CharField(
        max_length=255,
        verbose_name="Acción"
    )
    model = models.CharField(
        max_length=100,
        verbose_name="Modelo"
    )
    object_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID del Objeto"
    )
    data = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,  # Usa el encoder de Django que maneja más tipos
        verbose_name="Datos"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Dirección IP"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )

    class Meta:
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['model']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user or 'Sistema'} - {self.action} ({self.model})"

    def save(self, *args, **kwargs):
        # Limpieza y validación de datos antes de guardar
        self._clean_data()
        super().save(*args, **kwargs)

    def _clean_data(self):
        """
        Asegura que los datos sean serializables a JSON.
        Convierte objetos no serializables a representaciones de cadena.
        """
        if not isinstance(self.data, dict):
            self.data = {'value': str(self.data)}

        try:
            # Intenta serializar para validar
            json.dumps(self.data, cls=DjangoJSONEncoder)
        except (TypeError, ValueError) as e:
            # Si falla, guarda un mensaje de error y los datos convertidos a string
            self.data = {
                '_error': 'Los datos no pudieron ser serializados completamente',
                '_original_error': str(e),
                '_fallback_data': str(self.data)
            }

    @classmethod
    def log_action(cls, user=None, action=None, model=None, obj=None, request=None, **kwargs):
        """
        Método helper para crear registros de auditoría fácilmente.
        """
        data = {
            'model': str(model.__class__.__name__) if model else None,
            'object_id': str(obj.pk) if obj and hasattr(obj, 'pk') else None,
            **kwargs
        }

        if request:
            data.update({
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
            })

        return cls.objects.create(
            user=user,
            action=action or 'Acción no especificada',
            model=model.__class__.__name__ if model else 'Desconocido',
            object_id=str(obj.pk) if obj and hasattr(obj, 'pk') else '',
            data=data,
            ip_address=request.META.get('REMOTE_ADDR') if request else None
        )

    def get_data_display(self):
        """
        Devuelve una representación legible de los datos.
        """
        try:
            return json.dumps(self.data, indent=2, ensure_ascii=False)
        except:
            return str(self.data)