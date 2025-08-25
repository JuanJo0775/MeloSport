#categorias/forms.py
from django import forms
from .models import Category, AbsoluteCategory

# Mapea widgets -> clase CSS
INPUT_CLASSES = {
    forms.TextInput: "form-control",
    forms.EmailInput: "form-control",
    forms.URLInput: "form-control",
    forms.NumberInput: "form-control",
    forms.PasswordInput: "form-control",
    forms.Textarea: "form-control",
    forms.DateInput: "form-control",
    forms.TimeInput: "form-control",
    forms.DateTimeInput: "form-control",
    forms.ClearableFileInput: "form-control",
    forms.Select: "form-select",
    forms.SelectMultiple: "form-select",
    forms.CheckboxInput: "form-check-input",
    forms.RadioSelect: "form-check-input",
}

class BootstrapModelForm(forms.ModelForm):
    """Aplica clases Bootstrap por tipo de widget y setea placeholder por defecto."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            # Aplica clase basada en el tipo de widget
            for widget_type, css_class in INPUT_CLASSES.items():
                if isinstance(widget, widget_type):
                    existing = widget.attrs.get("class", "")
                    widget.attrs["class"] = (existing + " " + css_class).strip()
                    break
            # Placeholder por defecto = label (si no hay uno explícito)
            widget.attrs.setdefault("placeholder", field.label or name.capitalize())
            # Accesibilidad
            widget.attrs.setdefault("aria-label", field.label or name.capitalize())

class CategoryForm(BootstrapModelForm):
    class Meta:
        model = Category
        # Ajusta a tus campos reales o usa "__all__"
        fields = "__all__"
        # Opcional: personaliza widgets puntuales
        widgets = {
            # "name": forms.TextInput(attrs={"autofocus": True, "maxlength": 80}),
            # "parent": forms.Select(attrs={"data-placeholder": "Seleccione padre (opcional)"}),
            # "is_active": forms.CheckboxInput(),
        }
        # Opcional: etiquetas y ayudas
        labels = {
            # "name": "Nombre",
        }
        help_texts = {
            # "slug": "Déjalo vacío para autogenerar.",
        }

class AbsoluteCategoryForm(BootstrapModelForm):
    class Meta:
        model = AbsoluteCategory
        fields = "__all__"
        widgets = {
            # "order": forms.NumberInput(attrs={"min": 0}),
            # "show_on_home": forms.CheckboxInput(),
        }
        labels = {}
        help_texts = {}
