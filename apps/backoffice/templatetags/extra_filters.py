from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()

@register.filter
def absval(value):
    if value in (None, ''):
        return Decimal('0')
    try:
        return abs(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        try:
            return abs(float(value))
        except Exception:
            return 0
@register.filter
def mul(value, arg):
    """Multiplica dos valores numéricos con seguridad."""
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except Exception:
        return 0
