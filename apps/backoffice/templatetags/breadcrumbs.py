from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()

@register.inclusion_tag("partials/breadcrumb.html")
def breadcrumb(*args):
    """
    Renderiza un breadcrumb dinámico.
    Uso:
        {% breadcrumb "Perfil|backoffice:perfil" %}
        {% breadcrumb "Configuraciones|backoffice:configuraciones" "Cambiar Contraseña" %}
    """
    items = []
    for arg in args:
        parts = arg.split("|")
        label = parts[0].strip()
        url = None
        if len(parts) > 1:
            try:
                url = reverse(parts[1].strip())
            except NoReverseMatch:
                url = None
        items.append({"label": label, "url": url})
    return {"items": items}
