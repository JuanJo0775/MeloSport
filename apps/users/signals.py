from django.db.models.signals import post_save, post_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.conf import settings
from django.db import connection
from .models import AuditLog

# 🚫 Modelos que NO queremos auditar vía signals
SKIP = {
    "AuditLog",
    "LogEntry",
    "Session",       # 👈 agregado
    "ContentType",   # 👈 agregado
    "Permission",    # 👈 agregado
}


# ========================================================
# Utilidad: comprobar si la tabla existe antes de usarla
# ========================================================
def table_exists(table_name: str) -> bool:
    """Verifica si una tabla existe en la base de datos actual."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            );
        """, [table_name])
        return cursor.fetchone()[0]


# ========================================================
# Señales de modelos (crear/actualizar/eliminar instancias)
# ========================================================
@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    if sender.__name__ in getattr(settings, "AUDITLOG_SKIP_MODELS", set()):
        return

    # Evitar error si la tabla de auditoría aún no existe
    if not table_exists("users_auditlog"):
        return

    try:
        payload = model_to_dict(instance)
    except Exception:
        payload = {"repr": str(instance)}

    AuditLog.log_action(
        user=getattr(instance, "last_modified_by", None),
        action="create" if created else "update",
        model=sender.__name__,
        obj=None,  # no pasamos el objeto entero para no llenar demasiado
        description=f"Registro {'creado' if created else 'actualizado'} vía signal",
        extra_data={"snapshot": payload},
    )


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if sender.__name__ in SKIP:
        return

    # Evitar error si la tabla de auditoría aún no existe
    if not table_exists("users_auditlog"):
        return

    try:
        payload = model_to_dict(instance)
    except Exception:
        payload = {"repr": str(instance)}

    AuditLog.log_action(
        user=getattr(instance, "last_modified_by", None),
        action="delete",
        model=sender.__name__,
        obj=None,
        description="Registro eliminado vía signal",
        extra_data={"snapshot": payload},
    )


# ========================================================
# Señales de autenticación (login / logout / login fallido)
# ========================================================
@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    if not table_exists("users_auditlog"):
        return

    AuditLog.log_action(
        request=request,
        user=user,
        action="login",
        model="User",
        obj=user,
        description="Inicio de sesión exitoso (signal)",
    )


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if not table_exists("users_auditlog"):
        return

    AuditLog.log_action(
        request=request,
        user=user,
        action="logout",
        model="User",
        obj=user,
        description="Cierre de sesión (signal)",
    )


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    if not table_exists("users_auditlog"):
        return

    AuditLog.log_action(
        request=request,
        action="login",
        model="User",
        obj={"username": credentials.get("username")},
        description="Intento de inicio de sesión fallido (signal)",
    )
