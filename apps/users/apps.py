from django.apps import AppConfig
from django.db.models.signals import post_migrate


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"

    def ready(self):
        # Importar signals (auditoría, auth, etc.)
        try:
            import apps.users.signals  # noqa: F401
        except ImportError:
            pass

        # Ejecutar init_roles automáticamente tras migrate
        from .post_migrate import init_roles_post_migrate
        post_migrate.connect(init_roles_post_migrate, sender=self)
