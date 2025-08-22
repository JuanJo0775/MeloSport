from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Crea un usuario de prueba con datos reales"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        username = "JuanJo"
        email = "jjnaranjo_38@cue.edu.co"
        password = "@Juan0731"

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f"Usuario de prueba creado: {username} / {password}"))
        else:
            self.stdout.write(self.style.WARNING("El usuario ya existe"))
