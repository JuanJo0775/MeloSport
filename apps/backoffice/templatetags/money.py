# apps/backoffice/templatetags/money.py
from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

NBSP = "\xa0"  # Espacio no separable

def format_cop(value, symbol=True, decimals=0, nbsp=True):
    """Formatea valores numéricos a pesos colombianos."""
    if value is None or value == "":
        return "-"
    try:
        q = Decimal(value)
        if decimals == 0:
            q = q.quantize(Decimal("1"))
        else:
            q = q.quantize(Decimal("1." + "0"*decimals))
    except (InvalidOperation, TypeError, ValueError):
        return "-"

    # Formateo con punto para miles y coma para decimales
    txt = f"{q:,.{decimals}f}"  # ej: 120,000.00
    txt = txt.replace(",", "_").replace(".", ",").replace("_", ".")

    prefix = f"${NBSP}" if symbol and nbsp else ("$ " if symbol else "")
    return f"{prefix}{txt}"

@register.filter(name="cop")
def cop(value, decimals=0):
    """Con símbolo por defecto: {{ precio|cop }} -> $ 120.000"""
    try:
        decimals = int(decimals)
    except Exception:
        decimals = 0
    return format_cop(value, symbol=True, decimals=decimals)

@register.filter(name="cop_ns")
def cop_ns(value, decimals=0):
    """Sin símbolo: {{ precio|cop_ns }} -> 120.000"""
    try:
        decimals = int(decimals)
    except Exception:
        decimals = 0
    return format_cop(value, symbol=False, decimals=decimals)
