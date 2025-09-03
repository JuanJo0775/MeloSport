from decimal import Decimal
from django.contrib import admin, messages
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Discount, Reservation, ReservationItem, Invoice, InvoiceItem
from apps.users.models import AuditLog


# -------------------------
# Inlines
# -------------------------
class ReservationItemInline(admin.TabularInline):
    model = ReservationItem
    extra = 0
    fields = ("product", "variant", "quantity", "unit_price", "subtotal_display")
    readonly_fields = ("subtotal_display",)
    raw_id_fields = ("product", "variant")

    def subtotal_display(self, obj):
        return obj.subtotal()

    subtotal_display.short_description = "Subtotal"


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client_full_name",
        "client_phone",
        "status",
        "amount_deposited",
        "due_date",
        "created_at",
        "movement_created",
    )
    list_filter = ("status", "due_date", "created_at")
    search_fields = ("client_first_name", "client_last_name", "client_phone", "id")
    date_hierarchy = "created_at"
    inlines = [ReservationItemInline]
    readonly_fields = ("movement_created",)

    actions = ["release_selected_reservations", "create_invoice_from_reservations"]

    def client_full_name(self, obj):
        return f"{obj.client_first_name} {obj.client_last_name}"

    client_full_name.short_description = "Cliente"

    @admin.action(description="Liberar apartados seleccionados (crear movimientos 'in')")
    def release_selected_reservations(self, request, queryset):
        released = 0
        for r in queryset:
            if r.status == "active":
                r.release(user=request.user, reason="manual_release", request=request)
                released += 1
        self.message_user(request, f"{released} apartados liberados.", level=messages.SUCCESS)

    @admin.action(description="Crear factura(s) desde apartados seleccionados")
    def create_invoice_from_reservations(self, request, queryset):
        created = 0
        errors = []
        for r in queryset:
            if r.status != "active":
                errors.append(f"Apartado {r.pk} no está activo (estado={r.status})")
                continue
            if r.items.count() == 0:
                errors.append(f"Apartado {r.pk} no tiene items")
                continue

            with transaction.atomic():
                invoice = Invoice.objects.create(
                    client_first_name=r.client_first_name,
                    client_last_name=r.client_last_name,
                    client_phone=r.client_phone,
                    reservation=r,
                )
                # crear items
                for item in r.items.all():
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=item.product,
                        variant=item.variant,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                    )
                invoice.compute_totals()
                invoice.save()
                invoice.apply_inventory_movements(user=request.user, request=request)

                # cerrar el apartado
                r.status = "completed"
                r.save(update_fields=["status"])
                AuditLog.log_action(
                    request=request,
                    user=request.user,
                    action="create",
                    model=Invoice,
                    obj=invoice,
                    description=f"Factura creada desde Apartado {r.pk} (ID factura {invoice.pk})"
                )
                created += 1

        if created:
            self.message_user(request, f"{created} factura(s) creadas correctamente.", level=messages.SUCCESS)
        if errors:
            for e in errors:
                self.message_user(request, e, level=messages.WARNING)


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ("name", "percentage", "fixed_amount", "active")
    list_filter = ("active",)
    search_fields = ("name",)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    fields = ("product", "variant", "quantity", "unit_price", "subtotal")
    readonly_fields = ("subtotal",)
    raw_id_fields = ("product", "variant")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "code",
        "client_full_name",
        "client_phone",
        "total",
        "paid",
        "created_at",
        "inventory_moved",
    )
    list_filter = ("paid", "created_at")
    search_fields = ("code", "client_first_name", "client_last_name", "client_phone")
    date_hierarchy = "created_at"
    inlines = [InvoiceItemInline]
    readonly_fields = ("subtotal", "discount_amount", "total", "code", "inventory_moved", "created_at")

    actions = ["mark_as_paid", "mark_as_unpaid", "download_invoice_html"]

    def client_full_name(self, obj):
        return f"{obj.client_first_name} {obj.client_last_name}"

    client_full_name.short_description = "Cliente"

    def save_related(self, request, form, formsets, change):
        """Después de guardar inlines recalculamos totales y aplicamos movimientos."""
        super().save_related(request, form, formsets, change)
        invoice = form.instance
        invoice.compute_totals()
        invoice.save(update_fields=["subtotal", "discount_amount", "total"])

        try:
            invoice.apply_inventory_movements(user=request.user, request=request)
        except Exception as e:
            self.message_user(request, f"Error aplicando movimientos de inventario: {e}", level=messages.ERROR)
            return

        if invoice.reservation and invoice.reservation.status != "completed":
            invoice.reservation.status = "completed"
            invoice.reservation.save(update_fields=["status"])
            AuditLog.log_action(
                request=request,
                user=request.user,
                action="update",
                model=Reservation,
                obj=invoice.reservation,
                description=f"Apartado {invoice.reservation.pk} marcado como completado por factura {invoice.pk}"
            )

        AuditLog.log_action(
            request=request,
            user=request.user,
            action="create" if not change else "update",
            model=Invoice,
            obj=invoice,
            description=f"Factura guardada en admin (ID {invoice.pk})"
        )
        self.message_user(request, "Factura guardada y movimientos aplicados.", level=messages.SUCCESS)

    @admin.action(description="Marcar facturas seleccionadas como pagadas")
    def mark_as_paid(self, request, queryset):
        updated = queryset.filter(paid=False).update(paid=True, payment_date=timezone.now())
        self.message_user(request, f"{updated} factura(s) marcadas como pagadas.", level=messages.SUCCESS)

    @admin.action(description="Marcar facturas seleccionadas como no pagadas")
    def mark_as_unpaid(self, request, queryset):
        updated = queryset.update(paid=False, payment_date=None)
        self.message_user(request, f"{updated} factura(s) actualizadas.", level=messages.SUCCESS)

    @admin.action(description="Descargar HTML de factura(s) (abrir en nueva pestaña)")
    def download_invoice_html(self, request, queryset):
        for inv in queryset:
            url = reverse("billing:invoice_detail", kwargs={"pk": inv.pk})
            self.message_user(request, f"Factura {inv.code}: {url}", level=messages.INFO)
