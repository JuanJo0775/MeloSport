from django import template
from django.urls import reverse, NoReverseMatch
from django.template.base import Variable, VariableDoesNotExist

register = template.Library()


def _eval_expr(expr, context):
    """
    Evalúa una expresión del template:
      - números: "123" -> 123
      - cadenas entre comillas: "'hola'" o "\"hola\"" -> "hola"
      - variables del contexto: object.product.pk -> valor resuelto
      - si no se puede resolver, devuelve el string tal cual
    """
    s = (expr or "").strip()

    if s.isdigit():
        return int(s)

    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]

    try:
        return Variable(s).resolve(context)
    except VariableDoesNotExist:
        return s


def _try_reverse(name, positional, named):
    # Primero kwargs + args; luego solo args; último intento sin args
    try:
        if named:
            return reverse(name, args=positional, kwargs=named)
        return reverse(name, args=positional)
    except NoReverseMatch:
        try:
            return reverse(name)
        except NoReverseMatch:
            return None


def _resolve_url_from_spec(spec, context):
    """
    Soporta:
      - 'app:route'                            (sin args)
      - 'app:route:arg1:arg2'                  (posicionales)
      - 'app:route:pk=...:slug=...'            (kwargs)
      - 'app:route?pk=...&slug=...'            (kwargs estilo query)
    Además intenta todas las particiones posibles para nombres con namespaces.
    """
    if not spec:
        return None

    spec = spec.strip()

    # Forma query: app:route?pk=...&slug=...
    if "?" in spec:
        name, qs = spec.split("?", 1)
        kwargs = {}
        for part in filter(None, qs.split("&")):
            if "=" in part:
                k, v = part.split("=", 1)
                kwargs[k.strip()] = _eval_expr(v, context)
        try:
            return reverse(name.strip(), kwargs=kwargs)
        except NoReverseMatch:
            return None

    # Forma con ":" mezclando namespaces y args/kwargs
    segs = [p.strip() for p in spec.split(":") if p.strip()]

    # Probar todas las particiones posibles del nombre (de más largo a más corto)
    for k in range(len(segs), 0, -1):
        name = ":".join(segs[:k])
        arg_segs = segs[k:]

        positional = []
        named = {}
        for piece in arg_segs:
            if "=" in piece:
                kk, vv = piece.split("=", 1)
                named[kk.strip()] = _eval_expr(vv, context)
            else:
                positional.append(_eval_expr(piece, context))

        url = _try_reverse(name, positional, named)
        if url:
            return url

    # Último intento directo (por si el nombre completo estaba en spec)
    try:
        return reverse(spec)
    except NoReverseMatch:
        return None


@register.inclusion_tag("partials/breadcrumb.html", takes_context=True)
def breadcrumb(context, *args):
    """
    Uso:
      {% breadcrumb "Perfil|backoffice:perfil" %}
      {% breadcrumb "Config|backoffice:config:index" "Seguridad|backoffice:config:security" %}
      {% breadcrumb "Producto|backoffice:products:product_detail:object.pk" %}
      {% breadcrumb "Producto|backoffice:products:product_detail?pk=object.pk" %}
      {% breadcrumb "Producto|products:detail:pk=object.pk:slug=object.slug" %}

    Reglas:
      - Si no hay '|' -> se toma todo como etiqueta sin link.
      - Si la parte de ruta falla, se intenta prefijar 'backoffice:'.
      - Si igual falla, se muestra como texto plano.
    """
    items = []
    for raw in args:
        raw = str(raw)
        label, sep, rest = raw.partition("|")
        label = label.strip()
        url = None

        if rest:
            spec = rest.strip()
            # Intento directo
            url = _resolve_url_from_spec(spec, context)
            # Intento con prefijo backoffice si no lo tenía
            if not url and not spec.startswith("backoffice:"):
                url = _resolve_url_from_spec(f"backoffice:{spec}", context)

        items.append({"label": label, "url": url})

    return {"items": items}
