# apps/users/signals.py
from django.db.models.signals import post_save, post_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AuditLog
from django.forms.models import model_to_dict

SKIP = {"AuditLog", "LogEntry"}

# ========================================================
# Señales de modelos (crear/actualizar/eliminar instancias)
# ========================================================
@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    if sender.__name__ in SKIP:
        return

    try:
        payload = model_to_dict(instance)
    except Exception:
        payload = {"repr": str(instance)}

    AuditLog.log_action(
        user=getattr(instance, "last_modified_by", None),
        action="create" if created else "update",
        model=sender.__name__,
        obj=None,  # no pasamos el objeto entero
        description=f"Registro {'creado' if created else 'actualizado'} vía signal",
        extra_data={"snapshot": payload},
    )


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if sender.__name__ in SKIP:
        return

    try:
        payload = model_to_dict(instance)
    except Exception:
        payload = {"repr": str(instance)}

    AuditLog.log_action(
        user=getattr(instance, "last_modified_by", None),
        action="delete",
        model=sender.__name__,
        obj=None,  # tampoco aquí
        description="Registro eliminado vía signal",
        extra_data={"snapshot": payload},
    )

# ========================================================
# Señales de autenticación (login / logout / login fallido)
# ========================================================
@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
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
    AuditLog.log_action(
        request=request,
        action="login",
        model="User",
        obj={"username": credentials.get("username")},
        description="Intento de inicio de sesión fallido (signal)",
    )
