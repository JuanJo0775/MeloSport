from django.db import migrations
import json

def clean_auditlog(apps, schema_editor):
    AuditLog = apps.get_model("users", "AuditLog")
    bad_logs = []

    for log in AuditLog.objects.all():
        try:
            # Intentar serializar el campo data
            json.dumps(log.data)
        except Exception:
            bad_logs.append(log.id)

    # Eliminar registros corruptos
    if bad_logs:
        AuditLog.objects.filter(id__in=bad_logs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_auditlog_description_alter_auditlog_action_and_more"),  # cambia por la última migración real
    ]

    operations = [
        migrations.RunPython(clean_auditlog, reverse_code=migrations.RunPython.noop),
    ]
