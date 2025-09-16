# apps/billing/electronic/utils_electronic.py

import base64
import hashlib
import io
import qrcode
from datetime import datetime
from lxml import etree  # pip install lxml


def generate_cufe(invoice, issuer_nit: str, environment: str = "2") -> str:
    """
    Generador simplificado de CUFE (versión beta).
    ❗ El CUFE oficial usa concatenación estricta definida por DIAN.
    """
    invoice_number = invoice.code or str(invoice.pk)
    invoice_date = (invoice.created_at or datetime.utcnow()).isoformat()
    total = str(getattr(invoice, "total", 0) or 0)
    taxes = str(sum([getattr(i, "tax_amount", 0) for i in invoice.items.all()]) or 0)

    raw = f"{issuer_nit}|{invoice_number}|{invoice_date}|{total}|{taxes}|{environment}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return h


def build_basic_invoice_xml(invoice, issuer_info: dict, receiver_info: dict, cufe: str) -> bytes:
    """
    Construye un XML simplificado para la factura electrónica (solo pruebas internas).
    """
    root = etree.Element("InvoiceElectronic")

    meta = etree.SubElement(root, "Meta")
    etree.SubElement(meta, "CUFE").text = cufe
    etree.SubElement(meta, "GeneratedAt").text = (invoice.created_at or datetime.utcnow()).isoformat()

    emitter = etree.SubElement(root, "Emitter")
    for k, v in issuer_info.items():
        etree.SubElement(emitter, k).text = str(v)

    receiver = etree.SubElement(root, "Receiver")
    for k, v in receiver_info.items():
        etree.SubElement(receiver, k).text = str(v)

    lines = etree.SubElement(root, "Lines")
    for it in invoice.items.all():
        ln = etree.SubElement(lines, "Line")
        etree.SubElement(ln, "Description").text = str(it.product.name or "")
        etree.SubElement(ln, "Quantity").text = str(it.quantity)
        etree.SubElement(ln, "UnitPrice").text = str(it.unit_price)
        etree.SubElement(ln, "Subtotal").text = str(it.subtotal)
        etree.SubElement(ln, "TaxAmount").text = str(getattr(it, "tax_amount", 0))

    totals = etree.SubElement(root, "Totals")
    etree.SubElement(totals, "Subtotal").text = str(invoice.subtotal or 0)
    etree.SubElement(totals, "Discount").text = str(getattr(invoice, "discount_amount", 0))
    etree.SubElement(totals, "Total").text = str(invoice.total or 0)

    xml_bytes = etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    )
    return xml_bytes


def xml_to_base64(xml_bytes: bytes) -> str:
    """Convierte el XML a base64 para incrustar en HTML o descargas."""
    return base64.b64encode(xml_bytes).decode("utf-8")


def generate_qr_base64(payload: str, box_size: int = 4) -> str:
    """
    Genera un PNG QR codificado en base64, para usar en el template HTML.
    payload: ej. CUFE + NIT + total o URL de validación DIAN.
    """
    qr = qrcode.QRCode(box_size=box_size, border=1)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"
