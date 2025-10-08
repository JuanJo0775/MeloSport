# apps/backoffice/forms.py
from django import forms
from django.contrib.auth.forms import (
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import os
from email.mime.image import MIMEImage


# ====================================================
# Cambio de contraseña (perfil)
# ====================================================
class BackofficePasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Contraseña actual",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Contraseña actual"
        })
    )
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Nueva contraseña"
        })
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Confirmar nueva contraseña"
        })
    )


# ====================================================
# Restablecimiento de contraseña con logo inline
# ====================================================
class BackofficePasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Ingresa tu correo"
        })
    )

    # Sobrescribimos el método de envío del correo
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None
    ):
        """
        Enviar el correo de restablecimiento con imagen inline (logo).
        """
        # Asunto
        subject = render_to_string(subject_template_name, context).strip()

        # Cuerpo en texto plano (backup)
        body = render_to_string(email_template_name, context)

        # Cuerpo HTML (opcional)
        html_body = None
        if html_email_template_name:
            html_body = render_to_string(html_email_template_name, context)

        # Crear mensaje base
        msg = EmailMultiAlternatives(subject, body, from_email, [to_email])

        # Si hay versión HTML, se adjunta
        if html_body:
            msg.attach_alternative(html_body, "text/html")

        # 📸 Incrustar logo inline (Content-ID)
        logo_path = os.path.join(settings.BASE_DIR, "static", "img", "Logo sin fondo azul.png")
        if os.path.exists(logo_path):
            try:
                with open(logo_path, "rb") as f:
                    logo = MIMEImage(f.read())
                    logo.add_header("Content-ID", "<logo_cid>")
                    logo.add_header("Content-Disposition", "inline", filename="logo.png")
                    msg.attach(logo)
            except Exception as e:
                print(f"[Advertencia] No se pudo adjuntar el logo: {e}")

        # Enviar el correo
        msg.send(fail_silently=False)


# ====================================================
# Formulario para establecer nueva contraseña
# ====================================================
class BackofficeSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Nueva contraseña"
        })
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Confirmar nueva contraseña"
        })
    )
