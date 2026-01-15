# apps/backoffice/views_auth.py
from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.urls import reverse_lazy

from apps.backoffice.forms import (
    BackofficePasswordChangeForm,
    BackofficePasswordResetForm,
    BackofficeSetPasswordForm,
)


# ==========================
# Cambiar contraseña
# ==========================
class BackofficePasswordChangeView(PasswordChangeView):
    template_name = "perfil/cambiar_password.html"
    form_class = BackofficePasswordChangeForm
    success_url = reverse_lazy("backoffice:password_change_done")


class BackofficePasswordChangeDoneView(PasswordResetDoneView):
    template_name = "perfil/cambiar_password_done.html"


# ==========================
# Reset de contraseña
# ==========================
class BackofficePasswordResetView(PasswordResetView):
    template_name = "login/password_reset.html"
    form_class = BackofficePasswordResetForm
    email_template_name = "login/password_reset_email.txt"
    html_email_template_name = "login/password_reset_email.html"
    subject_template_name = "login/password_reset_subject.txt"
    success_url = reverse_lazy("backoffice:password_reset_done")


class BackofficePasswordResetDoneView(PasswordResetDoneView):
    template_name = "login/password_reset_done.html"


class BackofficePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "login/password_reset_confirm.html"
    form_class = BackofficeSetPasswordForm
    success_url = reverse_lazy("backoffice:password_reset_complete")


class BackofficePasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "login/password_reset_complete.html"

