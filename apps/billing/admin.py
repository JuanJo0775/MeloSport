from django.contrib import admin
from django.utils.html import format_html

from .models import Invoice, InvoiceItem, Reservation, ReservationItem


# ==========================
# Inline para items de facturas
# ==========================
class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    autocomplete_fields = ["product", "variant"]
    fields = ["product", "variant", "quantity", "unit_price", "subtotal"]
    readonly_fields = ["subtotal"]

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.pk:  # Si ya existe la factura
            return self.readonly_fields + ["product", "variant", "quantity", "unit_price"]
        return self.readonly_fields


# ==========================
# Facturas
# ==========================
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "client_name",
        "subtotal",
        "discount_percentage",
        "discount_amount",
        "total",
        "paid",
        "created_at",
    )
    list_filter = ("paid", "created_at")
    search_fields = ("code", "client_first_name", "client_last_name", "client_phone")
    date_hierarchy = "created_at"
    inlines = [InvoiceItemInline]

    fieldsets = (
        ("Cliente", {
            "fields": ("client_first_name", "client_last_name", "client_phone", "reservation")
        }),
        ("Factura", {
            "fields": (
                "discount_percentage",
                "discount_amount",
                "subtotal",
                "total",
                "notes",
                "paid",
                "payment_date",
            )
        }),
        ("Control", {
            "fields": ("code", "inventory_moved", "created_at"),
        }),
    )

    readonly_fields = ("subtotal", "discount_amount", "total", "code", "created_at", "inventory_moved")

    def save_model(self, request, obj, form, change):
        """Recalcular totales al guardar."""
        super().save_model(request, obj, form, change)
        obj.compute_totals()
        obj.save()

    def client_name(self, obj):
        return f"{obj.client_first_name or ''} {obj.client_last_name or ''}".strip()
    client_name.short_description = "Cliente"


# ==========================
# Inline para items de apartados
# ==========================
class ReservationItemInline(admin.TabularInline):
    model = ReservationItem
    extra = 1
    autocomplete_fields = ["product", "variant"]
    fields = ["product", "variant", "quantity", "unit_price", "subtotal"]
    readonly_fields = ["subtotal"]

    def subtotal(self, obj):
        return obj.subtotal() if obj.pk else "-"


# ==========================
# Apartados
# ==========================
@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client_name",
        "amount_deposited",
        "due_date",
        "status",
        "created_at",
        "movement_created",
    )
    list_filter = ("status", "created_at")
    search_fields = ("client_first_name", "client_last_name", "client_phone")
    date_hierarchy = "created_at"
    inlines = [ReservationItemInline]

    fieldsets = (
        ("Cliente", {
            "fields": ("client_first_name", "client_last_name", "client_phone")
        }),
        ("Apartado", {
            "fields": ("amount_deposited", "due_date", "status", "movement_created")
        }),
        ("Control", {
            "fields": ("created_at",),
        }),
    )

    readonly_fields = ("created_at", "movement_created")

    def client_name(self, obj):
        return f"{obj.client_first_name or ''} {obj.client_last_name or ''}".strip()
    client_name.short_description = "Cliente"
