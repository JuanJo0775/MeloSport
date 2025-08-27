from django import forms
from django.contrib.auth.forms import (
    UserCreationForm,
    UserChangeForm,
    SetPasswordForm,
)
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

    # Sobrescribir campos de contraseña
    password1 = forms.CharField(
        label="Nueva Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Nueva Contraseña"
        })
    )
    password2 = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Confirmar Contraseña"
        })
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

    # Campos extras para cambio de contraseña
    password1 = forms.CharField(
        label="Nueva Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Nueva contraseña"}),
        required=False
    )
    password2 = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirmar contraseña"}),
        required=False
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

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password1 = self.cleaned_data.get("password1")
        if password1:
            user.set_password(password1)
        if commit:
            user.save()
        return user


class CustomPasswordChangeForm(SetPasswordForm):
    old_password = forms.CharField(
        label="Contraseña actual",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control rounded-3",
                "placeholder": "Contraseña actual",
                "autocomplete": "current-password"
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update({
            "class": "form-control rounded-3",
            "placeholder": "Nueva contraseña",
            "autocomplete": "new-password"
        })
        self.fields["new_password2"].widget.attrs.update({
            "class": "form-control rounded-3",
            "placeholder": "Confirmar nueva contraseña",
            "autocomplete": "new-password"
        })

    def clean_old_password(self):
        old_password = self.cleaned_data.get("old_password")
        if not self.user.check_password(old_password):
            raise forms.ValidationError("La contraseña actual no es correcta.")
        return old_password

class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellido"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Correo"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Teléfono"}),
        }