from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    phone = forms.CharField(
        required=True,
        label="Teléfono",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Teléfono"})
    )
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Rol",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            "username", "email", "password1", "password2",
            "first_name", "last_name", "phone", "role"
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Usuario"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Correo"}),
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellido"}),
        }


class CustomUserChangeForm(UserChangeForm):
    phone = forms.CharField(
        required=True,
        label="Teléfono",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Teléfono"})
    )
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Rol",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = User
        fields = [
            "username", "email", "first_name", "last_name",
            "phone", "role", "is_active"
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
