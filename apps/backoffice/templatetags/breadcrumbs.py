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
            name = parts[1].strip()
            candidatos = [name]
            # si no empieza con "backoffice:", probamos también con ese prefijo
            if not name.startswith("backoffice:"):
                candidatos.insert(0, f"backoffice:{name}")
            for cand in candidatos:
                try:
                    url = reverse(cand)
                    break
                except NoReverseMatch:
                    url = None
        items.append({"label": label, "url": url})
    return {"items": items}
