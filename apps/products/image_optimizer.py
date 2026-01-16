import uuid
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile

MAX_SIZE = (1000, 1000)   # productos
QUALITY = 80              # webp
FORMAT = "WEBP"


def optimize_product_image(image_field):
    """
    Recibe un ImageFieldFile y devuelve un ContentFile optimizado.
    NO guarda en disco.
    """
    image = Image.open(image_field)

    # Seguridad: convertir todo a RGB
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # Redimensionar manteniendo aspect ratio
    image.thumbnail(MAX_SIZE, Image.LANCZOS)

    buffer = BytesIO()
    image.save(
        buffer,
        format=FORMAT,
        quality=QUALITY,
        optimize=True
    )

    buffer.seek(0)

    filename = f"{uuid.uuid4().hex.lower()}.webp"
    return ContentFile(buffer.read(), name=filename)
