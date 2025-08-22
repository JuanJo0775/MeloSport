from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()  # 👈 Esto usa tu modelo custom

class Command(BaseCommand):
    help = "Crea roles iniciales y superusuario admin"

    def handle(self, *args, **options):
        # Crear grupos
        admin_group, _ = Group.objects.get_or_create(name="Administrador")
        vendedor_group, _ = Group.objects.get_or_create(name="Vendedor")

        # Permisos base
        # Admin: todos
        for perm in Permission.objects.all():
            admin_group.permissions.add(perm)

        # Vendedor: solo productos e inventario
        allowed = Permission.objects.filter(content_type__app_label__in=["productos", "inventario"])
        vendedor_group.permissions.set(allowed)

        # Superusuario admin
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@melosport.com", "Admin123!")
            self.stdout.write(self.style.SUCCESS("Superusuario creado: admin / Admin123!"))
