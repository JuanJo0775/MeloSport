import sys

from django.db import connection
from django.db.models.signals import post_save, post_delete
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.conf import settings


# ========================================================
# Utilidad: comprobar si una tabla existe
# ========================================================
def table_exists(table_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            );
            """,
            [table_name],
        )
        return cursor.fetchone()[0]


# ========================================================
# Señales de modelos (create / update)
# ========================================================
@receiver(post_save)
def log_save(sender, instance, created, raw=False, **kwargs):
    # ⛔ NO durante migraciones
    if "migrate" in sys.argv or "makemigrations" in sys.argv:
        return

    # ⛔ NO cuando viene de fixtures o migraciones
    if raw:
        return

    # ⛔ NO auditar modelos excluidos
    if sender.__name__ in getattr(settings, "AUDITLOG_SKIP_MODELS", set()):
        return

    # ⛔ NO auditar el propio AuditLog (CRÍTICO)
    if sender.__name__ == "AuditLog":
        return

    # ⛔ Evitar uso si la tabla aún no existe
    if not table_exists("users_auditlog"):
        return

    from .models import AuditLog  # import tardío

    try:
        payload = model_to_dict(instance)
    except Exception:
        payload = {"repr": str(instance)}

    AuditLog.log_action(
        user=getattr(instance, "last_modified_by", None),
        action="create" if created else "update",
        model=sender.__name__,
        obj=None,
        description=f"Registro {'creado' if created else 'actualizado'} vía signal",
        extra_data={"snapshot": payload},
    )


# ========================================================
# Señales de modelos (delete)
# ========================================================
@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    # ⛔ NO durante migraciones
    if "migrate" in sys.argv:
        return

    # ⛔ NO auditar modelos excluidos
    if sender.__name__ in getattr(settings, "AUDITLOG_SKIP_MODELS", set()):
        return

    # ⛔ NO auditar AuditLog
    if sender.__name__ == "AuditLog":
        return

    if not table_exists("users_auditlog"):
        return

    from .models import AuditLog

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
# Señales de autenticación
# ========================================================
@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    if not table_exists("users_auditlog"):
        return

    from .models import AuditLog

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

    from .models import AuditLog

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

    from .models import AuditLog

    AuditLog.log_action(
        request=request,
        action="login_failed",
        model="User",
        obj={"username": credentials.get("username")},
        description="Intento de inicio de sesión fallido (signal)",
    )
