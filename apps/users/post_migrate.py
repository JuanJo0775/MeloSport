from django.core.management import call_command


def init_roles_post_migrate(sender, **kwargs):
    """
    Ejecuta el comando init_roles automáticamente
    después de aplicar migraciones.
    """
    call_command("init_roles")
