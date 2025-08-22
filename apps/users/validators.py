import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class ComplexPasswordValidator:
    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError(_("La contraseña debe tener al menos 8 caracteres."))
        if not re.search(r"[A-Z]", password):
            raise ValidationError(_("Debe contener al menos una mayúscula."))
        if not re.search(r"[a-z]", password):
            raise ValidationError(_("Debe contener al menos una minúscula."))
        if not re.search(r"\d", password):
            raise ValidationError(_("Debe contener al menos un número."))
        if not re.search(r"[^\w]", password):
            raise ValidationError(_("Debe contener al menos un carácter especial."))

    def get_help_text(self):
        return _("Debe incluir: 8+ caracteres, mayúscula, minúscula, número, caracter especial.")
