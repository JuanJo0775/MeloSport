from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import FeaturedProductCarousel, ContactMessage, InformativeCarousel


# --- Forms con selector de color ---
class FeaturedProductCarouselForm(forms.ModelForm):
    class Meta:
        model = FeaturedProductCarousel
        fields = "__all__"
        widgets = {
            "bg_color": forms.TextInput(attrs={"type": "color"}),
            "layout": forms.Select()
        }


class InformativeCarouselForm(forms.ModelForm):
    class Meta:
        model = InformativeCarousel
        fields = "__all__"
        widgets = {
            "bg_color": forms.TextInput(attrs={"type": "color"}),
            "layout": forms.Select()
        }


# --- Admin de Productos Destacados ---
@admin.register(FeaturedProductCarousel)
class FeaturedProductCarouselAdmin(admin.ModelAdmin):
    form = FeaturedProductCarouselForm

    list_display = (
        'product',
        'image_preview',
        'title',
        'categories_list',
        'layout',
        'is_active',
        'display_order',
        'color_preview',
    )
    list_editable = ('is_active', 'display_order', 'layout')
    list_filter = ('is_active', 'product__categories', 'layout')
    search_fields = (
        'product__name',
        'product__sku',
        'custom_title',
        'custom_subtitle',
        'product__categories__name'
    )
    readonly_fields = ('image_preview', 'created_at', 'categories_list')
    raw_id_fields = ('product',)

    fieldsets = (
        (None, {
            'fields': (
                'product',
                'is_active',
                'display_order',
                'layout',
            )
        }),
        ('Personalización (opcional)', {
            'fields': (
                'custom_title',
                'custom_subtitle',
                'bg_color'
            ),
            'classes': ('collapse',)
        }),
        ('Información', {
            'fields': (
                'image_preview',
                'categories_list',
                'created_at'
            ),
            'classes': ('collapse',)
        }),
    )

    def image_preview(self, obj):
        # mostrar la primera imagen disponible del producto
        if obj.images:
            img = obj.images[0]  # ya devuelve objetos `ImageFieldFile`
            return format_html(
                '<img src="{}" height="100" style="border-radius: 5px;"/>',
                img.url
            )
        return "Sin imagen disponible"
    image_preview.short_description = "Vista previa"

    def categories_list(self, obj):
        categories = obj.product.categories.all()
        if categories:
            return ", ".join([c.name for c in categories])
        return "Sin categorías"
    categories_list.short_description = "Categorías"

    def color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:18px;height:18px;'
            'border-radius:4px;background:{};border:1px solid #ccc;"></span>',
            obj.bg_color or "#0d6efd"
        )
    color_preview.short_description = "Color"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'product'
        ).prefetch_related(
            'product__images',
            'product__categories'
        )


# --- Admin de Tarjetas Informativas ---
@admin.register(InformativeCarousel)
class InformativeCarouselAdmin(admin.ModelAdmin):
    form = InformativeCarouselForm

    list_display = (
        'title',
        'images_preview',
        'layout',
        'is_active',
        'display_order',
        'color_preview',
        'created_at'
    )
    list_editable = ('is_active', 'display_order', 'layout')
    list_filter = ('is_active', 'layout')
    search_fields = ('title', 'description', 'link')
    readonly_fields = ('created_at', 'images_preview')

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'image1', 'image2', 'image3', 'link')
        }),
        ('Apariencia y orden', {
            'fields': ('layout', 'bg_color', 'is_active', 'display_order', 'is_default')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'images_preview'),
            'classes': ('collapse',)
        }),
    )

    def images_preview(self, obj):
        if obj.images:
            html = "".join(
                f'<img src="{img.url}" height="80" style="margin:2px;border-radius:4px;border:1px solid #ccc;"/>'
                for img in obj.images
            )
            return format_html(html)
        return "Sin imágenes"
    images_preview.short_description = "Vista previa"

    def color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:18px;height:18px;'
            'border-radius:4px;background:{};border:1px solid #ccc;"></span>',
            obj.bg_color or "#198754"
        )
    color_preview.short_description = "Color"


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
