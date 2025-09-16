# apps/billing/electronic/views.py

from decimal import Decimal
from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from apps.billing.models import Invoice
from .utils_electronic import generate_cufe, build_basic_invoice_xml, xml_to_base64, generate_qr_base64


class InvoiceElectronicView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Representación gráfica de la factura electrónica (beta)."""
    permission_required = "billing.view_invoice"
    model = Invoice
    template_name = "backoffice/billing/invoice_template/invoice_electronic.html"
    context_object_name = "invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object

        # Datos emisor / receptor (se pueden sacar de settings o del modelo Company)
        issuer_info = {
            "Name": "MeloSport SAS",
            "NIT": "900123456-7",
            "Address": "Armenia, Quindío",
            "Email": "info@melosport.com",
        }

        # 🔹 Ajuste: usamos placeholders ya que no hay modelo de cliente con documento
        receiver_info = {
            "Name": f"{invoice.client_first_name} {invoice.client_last_name}",
            "Document": "0000000000",   # placeholder hasta que exista el campo
            "DocumentType": "CC",       # fijo por ahora (Cédula de ciudadanía)
            "Phone": invoice.client_phone or "N/A",
        }

        # CUFE (Código Único de Factura Electrónica)
        cufe = generate_cufe(invoice, issuer_info["NIT"])
        qr_img = generate_qr_base64(
            f"CUFE:{cufe}|NIT:{issuer_info['NIT']}|TOTAL:{invoice.total}"
        )

        # XML representativo
        xml_bytes = build_basic_invoice_xml(invoice, issuer_info, receiver_info, cufe)
        xml_b64 = xml_to_base64(xml_bytes)

        context.update({
            "cufe": cufe,
            "qr_img": qr_img,
            "xml_b64": xml_b64,
            "issuer_info": issuer_info,
            "receiver_info": receiver_info,
        })
        return context
