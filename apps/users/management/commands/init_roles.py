import os

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Crea roles iniciales y superusuario (solo si está habilitado)"

    def handle(self, *args, **options):
        self.stdout.write("🔧 Inicializando roles y permisos...")

        # ====================================================
        # Grupos
        # ====================================================
        admin_group, _ = Group.objects.get_or_create(name="Administrador")
        vendedor_group, _ = Group.objects.get_or_create(name="Vendedor")

        # ====================================================
        # Admin: todos los permisos
        # ====================================================
        admin_group.permissions.set(Permission.objects.all())

        # ====================================================
        # Vendedor: permisos específicos
        # ====================================================
        allowed_permissions = []

        allowed_permissions += list(
            Permission.objects.filter(
                codename__startswith="view_",
                content_type__app_label__in=["products", "categories"],
            )
        )

        allowed_permissions += list(
            Permission.objects.filter(
                content_type__app_label="products",
                codename__in=[
                    "view_inventorymovement",
                    "add_inventorymovement",
                ],
            )
        )

        allowed_permissions += list(
            Permission.objects.filter(content_type__app_label="billing")
        )

        vendedor_group.permissions.set(allowed_permissions)

        # ====================================================
        # Superusuario (solo si está habilitado)
        # ====================================================
        if os.getenv("DJANGO_CREATE_SUPERUSER") != "True":
            self.stdout.write("ℹ️ Creación de superusuario deshabilitada")
            return

        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not all([username, email, password]):
            self.stdout.write(
                self.style.WARNING(
                    "⚠️ Variables de superusuario incompletas, no se creó admin"
                )
            )
            return

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
            self.stdout.write(
                self.style.SUCCESS(f"✅ Superusuario creado: {username}")
            )
        else:
            self.stdout.write("ℹ️ Superusuario ya existe")

        self.stdout.write(
            self.style.SUCCESS("✅ Roles y permisos configurados correctamente")
        )
