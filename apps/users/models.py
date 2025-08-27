from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.timezone import now
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from django.forms.utils import ErrorDict, ErrorList
from django.db.models import Model, QuerySet
from django.http import QueryDict
import json


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    # Guarda permisos como JSON {"permissions": ["add_user", "change_user"]}
    permissions = models.JSONField(default=dict)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def has_permission(self, perm_codename):
        """
        Verifica si el rol tiene un permiso (cuando se guardan como JSON).
        """
        perms = self.permissions.get("permissions", [])
        return perm_codename in perms

    def __str__(self):
        return self.name


class User(AbstractUser):
    roles = models.ManyToManyField(Role, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    last_access = models.DateTimeField(null=True, blank=True)

    # Sobrescribimos groups y user_permissions para evitar conflictos
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
    ACTION_CHOICES = [
        ("create", "Creación"),
        ("update", "Actualización"),
        ("delete", "Eliminación"),
        ("login", "Inicio de sesión"),
        ("logout", "Cierre de sesión"),
        ("other", "Otro"),
    ]

    user = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario",
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name="Acción")
    model = models.CharField(max_length=100, verbose_name="Modelo")
    object_id = models.CharField(max_length=100, blank=True, verbose_name="ID del Objeto")
    description = models.TextField(blank=True, verbose_name="Descripción")
    data = models.JSONField(default=dict, encoder=DjangoJSONEncoder, verbose_name="Datos")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dirección IP")
    created_at = models.DateTimeField(default=now, verbose_name="Fecha de Creación")

    class Meta:
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["model"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user or 'Sistema'} - {self.get_action_display()} ({self.model})"

    # ========= utilidades internas =========
    SENSITIVE_KEYS = {"password", "pass", "token", "authorization", "secret", "api_key"}

    @classmethod
    def _to_jsonable(cls, value):
        """
        Convierte value en algo 100% serializable por json (recursivo).
        Maneja Model, Form, QueryDict, ErrorDict, QuerySet, listas, etc.
        """
        # primitivos
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        # dict
        if isinstance(value, dict):
            return {str(k): cls._to_jsonable(v) for k, v in value.items()}

        # listas/tuplas/sets
        if isinstance(value, (list, tuple, set)):
            return [cls._to_jsonable(v) for v in value]

        # QueryDict (request.POST / GET)
        if isinstance(value, QueryDict):
            return {k: (vals if len(vals) > 1 else vals[0]) for k, vals in value.lists()}

        # Errores de formulario
        if isinstance(value, ErrorDict):
            return {k: [str(e) for e in v] for k, v in value.items()}
        if isinstance(value, ErrorList):
            return [str(e) for e in value]

        # Model
        if isinstance(value, Model):
            try:
                data = model_to_dict(value)
                # Manejar ManyToMany (ej: groups, roles, user_permissions)
                for field in value._meta.many_to_many:
                    try:
                        related = getattr(value, field.name).all()
                        data[field.name] = [str(obj) for obj in related]
                    except Exception:
                        data[field.name] = []
                return data
            except Exception:
                return {"object": str(value), "pk": getattr(value, "pk", None)}

        # QuerySet
        if isinstance(value, QuerySet):
            try:
                return list(value.values())
            except Exception:
                return [str(x) for x in value]

        # Form (usa cleaned_data si existe)
        if hasattr(value, "cleaned_data"):
            try:
                return cls._to_jsonable(getattr(value, "cleaned_data", {}))
            except Exception:
                return {"form": str(value)}

        # Objetos con get_json_data (p. ej. errors)
        if hasattr(value, "get_json_data"):
            try:
                return value.get_json_data()
            except Exception:
                pass

        # último intento con el encoder de Django
        try:
            json.dumps(value, cls=DjangoJSONEncoder)
            return value
        except TypeError:
            return str(value)

    @classmethod
    def _mask_sensitive(cls, payload):
        """
        Enmascara valores de claves sensibles (password, token, etc.).
        """
        if isinstance(payload, dict):
            out = {}
            for k, v in payload.items():
                lk = str(k).lower()
                if any(s in lk for s in cls.SENSITIVE_KEYS):
                    out[k] = "***"
                else:
                    out[k] = cls._mask_sensitive(v)
            return out
        if isinstance(payload, list):
            return [cls._mask_sensitive(v) for v in payload]
        return payload

    # ========= API pública =========
    @classmethod
    def log_action(
        cls,
        *,
        user=None,
        request=None,
        action="other",
        model=None,
        obj=None,
        description="",
        extra_data=None,
    ):
        """
        Logger robusto: acepta casi cualquier cosa en obj/extra_data.
        """
        # Usuario
        if not user and request:
            user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None

        # IP (real si hay proxy)
        ip = None
        if request:
            xff = request.META.get("HTTP_X_FORWARDED_FOR")
            ip = (xff.split(",")[0] if xff else request.META.get("REMOTE_ADDR"))

        # Datos principales desde obj
        data = {}
        if obj is not None:
            data = cls._to_jsonable(obj)

        # Merge con extra_data
        if extra_data is not None:
            merged = {}
            if isinstance(data, dict):
                merged.update(data)
            else:
                merged["object"] = data
            merged["extra"] = cls._to_jsonable(extra_data)
            data = merged

        # Enmascarar sensibles SIEMPRE
        data = cls._mask_sensitive(data if isinstance(data, (dict, list)) else {"value": data})

        return cls.objects.create(
            user=user,
            action=action,
            model=(model if isinstance(model, str) else getattr(model, "__name__", str(model))),
            object_id=str(getattr(obj, "pk", "")) if hasattr(obj, "pk") else "",
            description=description,
            data=data,
            ip_address=ip,
        )

    def get_data_display(self):
        try:
            return json.dumps(self.data, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)
        except Exception:
            return str(self.data)
