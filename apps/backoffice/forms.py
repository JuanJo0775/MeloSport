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
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.contrib.staticfiles.storage import staticfiles_storage
from email.mime.image import MIMEImage
import os


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
        Envía el correo de restablecimiento con:
        - Imagen inline (Content-ID)
        - URL de respaldo del logo (logo_web_url)
        - Compatibilidad con collectstatic
        """
        # ====================================================
        # Renderizar asunto y cuerpo en texto plano
        # ====================================================
        subject = render_to_string(subject_template_name, context).strip()
        body = render_to_string(email_template_name, context)

        # ====================================================
        # Localizar logo estático
        # ====================================================
        logo_static_name = "img/Logo_sin_fondo_blanco.png"
        logo_path = finders.find(logo_static_name) or os.path.join(settings.BASE_DIR, "static", logo_static_name)

        # ====================================================
        # Crear URL pública de respaldo para el logo
        # ====================================================
        try:
            logo_web_url = staticfiles_storage.url(logo_static_name)
        except Exception:
            logo_web_url = static(logo_static_name)

        if context.get("protocol") and context.get("domain"):
            context["logo_web_url"] = f"{context['protocol']}://{context['domain']}{logo_web_url}"
        else:
            context["logo_web_url"] = logo_web_url

        # ====================================================
        # Renderizar versión HTML del correo
        # ====================================================
        html_body = None
        if html_email_template_name:
            html_body = render_to_string(html_email_template_name, context)

        # ====================================================
        # Construir mensaje con texto y HTML
        # ====================================================
        msg = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_body:
            msg.attach_alternative(html_body, "text/html")

        # ====================================================
        # Incrustar logo inline (Content-ID)
        # ====================================================
        try:
            if logo_path and os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo = MIMEImage(f.read())
                    logo.add_header("Content-ID", "<logo_cid>")
                    logo.add_header("Content-Disposition", "inline", filename="logo.png")
                    msg.attach(logo)
        except Exception as e:
            print(f"[Advertencia] No se pudo adjuntar el logo: {e}")

        # ====================================================
        # Enviar el correo
        # ====================================================
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
