from decimal import Decimal, InvalidOperation
from datetime import timedelta
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

@register.filter
def sub(value, arg):
    """Resta dos valores numéricos con seguridad."""
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except Exception:
        try:
            return float(value) - float(arg)
        except Exception:
            return 0

@register.filter
def to(value, arg):
    """
    Devuelve un rango de enteros desde value hasta arg-1.
    Uso en template:
      {% for i in 0|to:10 %} → 0,1,2,3,4,5,6,7,8,9
    """
    try:
        start = int(value)
        end = int(arg)
        return range(start, end)
    except Exception:
        return []

@register.filter
def add_days(date, days):
    """
    Suma 'days' a una fecha.
    Devuelve la nueva fecha en formato YYYY-MM-DD (string).
    Uso en template:
      {{ some_date|add_days:3 }}
    """
    try:
        return (date + timedelta(days=int(days))).strftime("%Y-%m-%d")
    except Exception:
        return ""
