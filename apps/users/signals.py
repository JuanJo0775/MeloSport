# En apps/users/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import AuditLog

@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    if sender.__name__ not in ['AuditLog', 'LogEntry']:  # Evitar registrar los propios logs
        action = 'CREATED' if created else 'UPDATED'
        AuditLog.objects.create(
            user=instance.last_modified_by if hasattr(instance, 'last_modified_by') else None,
            action=action,
            model=sender.__name__,
            object_id=str(instance.pk),
            data=instance.__dict__
        )