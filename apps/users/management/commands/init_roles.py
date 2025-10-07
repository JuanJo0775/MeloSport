#apps/users/management/commands/init_roles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Crea roles iniciales y superusuario admin"

    def handle(self, *args, **options):
        # Crear grupos
        admin_group, _ = Group.objects.get_or_create(name="Administrador")
        vendedor_group, _ = Group.objects.get_or_create(name="Vendedor")

        # --- Admin: todos los permisos ---
        admin_group.permissions.set(Permission.objects.all())


        # --- Vendedor: permisos específicos ---
        allowed = []

        # Solo lectura de productos y categorías
        allowed += list(
            Permission.objects.filter(
                codename__startswith="view_", content_type__app_label="products"
            )
        )
        allowed += list(
            Permission.objects.filter(
                codename__startswith="view_", content_type__app_label="categories"
            )
        )

        # Movimientos de inventario: solo ver y agregar
        inventory_perms = Permission.objects.filter(
            content_type__app_label="products",
            codename__in=["view_inventorymovement", "add_inventorymovement"],
        )
        allowed += list(inventory_perms)

        # --- Billing (ventas / reservas): todos los permisos ---
        billing_perms = Permission.objects.filter(content_type__app_label="billing")
        allowed += list(billing_perms)

        # Asignar permisos al grupo Vendedor
        vendedor_group.permissions.set(allowed)

        # --- Superusuario por defecto ---
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                "admin", "melosport4@gmail.com", "DimeSport2025$"
            )
            self.stdout.write(
                self.style.SUCCESS("✅ Superusuario creado: admin / DimeSport2025$")
            )

        self.stdout.write(
            self.style.SUCCESS("✅ Roles y permisos iniciales configurados")
        )
