from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD  # Indicamos que el campo de login es email

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(request=self.context.get("request"),
                                username=email, password=password)

            if not user:
                raise serializers.ValidationError("Email o contraseña incorrectos")
        else:
            raise serializers.ValidationError("Debe ingresar email y contraseña")

        data = super().validate(attrs)
        data['user'] = {
            "id": self.user.id,
            "email": self.user.email,
            "username": self.user.username,
            "roles": [role.name for role in self.user.roles.all()]
        }
        return data
