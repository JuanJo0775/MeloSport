import uuid
from io import BytesIO

from PIL import Image
from django.core.files.base import ContentFile


# ============================================================
# 🎠 Configuración de optimización para carruseles
# ============================================================

# Tamaño ideal para slides principales (full-width, responsive)
CAROUSEL_SIZE = (1400, 800)

# Calidad balanceada (peso vs nitidez)
CAROUSEL_QUALITY = 80


def optimize_carousel_image(image_field):
    """
    Optimiza imágenes del carrusel:
    - Redimensiona a tamaño máximo controlado
    - Convierte a WEBP
    - Reduce peso drásticamente
    - Mantiene buena calidad visual
    """

    # Abrir imagen
    image = Image.open(image_field)

    # Convertir a RGB si es necesario (evita errores con PNG/alpha)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # Redimensionar manteniendo proporción
    image.thumbnail(CAROUSEL_SIZE, Image.LANCZOS)

    # Guardar en memoria
    buffer = BytesIO()
    image.save(
        buffer,
        format="WEBP",
        quality=CAROUSEL_QUALITY,
        optimize=True
    )

    buffer.seek(0)

    # Nombre único
    filename = f"{uuid.uuid4().hex}.webp"

    return ContentFile(buffer.read(), name=filename)
