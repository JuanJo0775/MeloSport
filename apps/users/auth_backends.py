from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = None
        try:
            # Buscar por username exacto
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Buscar por email, pero asegurando unicidad
            users = User.objects.filter(email=username)
            if users.count() == 1:
                user = users.first()
            else:
                return None  # hay 0 o más de 1 → no autenticamos

        if user and user.check_password(password):
            return user
        return None

