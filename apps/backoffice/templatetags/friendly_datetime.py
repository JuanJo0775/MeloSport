# apps/backoffice/templatetags/friendly_datetime.py
from django import template
from django.utils import timezone
import datetime as dt
import pytz  # 👈 asegúrate de tener pytz instalado
import locale

register = template.Library()

# 👇 Configurar zona horaria de Bogotá
BOGOTA_TZ = pytz.timezone("America/Bogota")

# 👇 Forzar locale en español (esto puede variar según SO, en Linux/Mac funciona con "es_ES.UTF-8")
try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except locale.Error:
    # fallback por si no existe en Windows, usamos manual
    DAYS_ES = {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miércoles",
        "Thursday": "Jueves",
        "Friday": "Viernes",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    }
else:
    DAYS_ES = None


def _fmt_time(dt_obj: dt.datetime) -> str:
    """Formatea la hora en estilo 12h (2:34 pm)."""
    s = dt_obj.strftime("%I:%M %p")
    return s.lstrip("0").replace("AM", "am").replace("PM", "pm")


@register.filter
def friendly_datetime(value):
    """Convierte un datetime en formato amigable tipo 'Hoy, 2:34 pm'."""
    if not value:
        return "-"

    if not isinstance(value, dt.datetime):
        return str(value)

    # Convertir explícitamente a zona horaria de Bogotá
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.utc)
    local_dt = value.astimezone(BOGOTA_TZ)

    now = timezone.localtime(timezone.now(), BOGOTA_TZ)
    today = now.date()
    date = local_dt.date()
    delta = now - local_dt

    if date == today:
        return f"Hoy, {_fmt_time(local_dt)}"
    if date == (today - dt.timedelta(days=1)):
        return f"Ayer, {_fmt_time(local_dt)}"
    if delta.days < 7:
        day_name = local_dt.strftime("%A")
        if DAYS_ES:  # traducir manual si no se pudo setear locale
            day_name = DAYS_ES.get(day_name, day_name)
        return f"{day_name}, {_fmt_time(local_dt)}"
    return local_dt.strftime("%d/%m/%Y")
