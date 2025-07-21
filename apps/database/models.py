from django.db import models
from apps.users.models import User

class DatabaseBackup(models.Model):
    BACKUP_TYPES = [
        ('manual', 'Manual'),
        ('automatic', 'Automático'),
    ]

    backup_type = models.CharField(max_length=10, choices=BACKUP_TYPES)
    file = models.FileField(upload_to='database_backups/')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Respaldo de Base de Datos"
        verbose_name_plural = "Respaldos de Base de Datos"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_backup_type_display()} - {self.created_at}"

class DatabaseStatusLog(models.Model):
    status = models.CharField(max_length=20)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Estado de BD"
        verbose_name_plural = "Registros de Estado de BD"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.status} - {self.created_at}"