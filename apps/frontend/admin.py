from django.contrib import admin
from .models import FeaturedProductCarousel, ContactMessage
from django.utils.html import format_html

@admin.register(FeaturedProductCarousel)
class FeaturedProductCarouselAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'image_preview',
        'title',
        'categories_list',  # Nuevo campo para mostrar categorías
        'is_active',
        'display_order'
    )
    list_editable = ('is_active', 'display_order')
    list_filter = ('is_active', 'product__categories')  # Usar 'categories' en plural
    search_fields = (
        'product__name',
        'product__sku',
        'custom_title',
        'custom_subtitle',
        'product__categories__name'  # Búsqueda por nombre de categoría
    )
    readonly_fields = ('image_preview', 'created_at', 'categories_list')
    raw_id_fields = ('product',)

    fieldsets = (
        (None, {
            'fields': (
                'product',
                'is_active',
                'display_order'
            )
        }),
        ('Personalización (opcional)', {
            'fields': (
                'custom_title',
                'custom_subtitle'
            ),
            'classes': ('collapse',)
        }),
        ('Información', {
            'fields': (
                'image_preview',
                'categories_list',  # Mostrar categorías en el detalle
                'created_at'
            ),
            'classes': ('collapse',)
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" height="100" style="border-radius: 5px;"/>',
                obj.image.url
            )
        return "Sin imagen disponible"
    image_preview.short_description = "Vista previa"

    def categories_list(self, obj):
        """Muestra las categorías del producto"""
        categories = obj.product.categories.all()
        if categories:
            return ", ".join([c.name for c in categories])
        return "Sin categorías"
    categories_list.short_description = "Categorías"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'product'
        ).prefetch_related(
            'product__images',
            'product__categories'  # Prefetch para la relación ManyToMany
        )

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at', 'is_answered', 'message_preview')
    list_filter = ('is_answered', 'created_at')
    search_fields = ('name', 'email', 'phone', 'message')
    readonly_fields = ('name', 'email', 'phone', 'message', 'created_at')
    list_editable = ('is_answered',)
    date_hierarchy = 'created_at'

    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message

    message_preview.short_description = "Mensaje"

    def has_add_permission(self, request):
        return False