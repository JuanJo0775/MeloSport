from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()

@register.inclusion_tag("partials/breadcrumb.html")
def breadcrumb(*args):
    """
    Renderiza un breadcrumb dinámico.
    Uso:
        {% breadcrumb "Perfil" %}
        {% breadcrumb "Usuarios" "usuarios" "Detalle" %}
    Los pares se interpretan como (label, url_name opcional).
    """
    items = []
    for arg in args:
        parts = arg.split("|")  # Ejemplo: "Perfil|perfil"
        label = parts[0]
        url = None
        if len(parts) > 1:
            try:
                url = reverse(parts[1])
            except NoReverseMatch:
                url = None
        items.append({"label": label, "url": url})
    return {"items": items}
