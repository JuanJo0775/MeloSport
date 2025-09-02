from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from .models import Product, ProductVariant, ProductImage, InventoryMovement
from django.contrib import messages
from decimal import Decimal, InvalidOperation



class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ['preview']
    classes = ['collapse']

    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px; '
                'border-radius: 3px; border: 1px solid #ddd;" />',
                obj.image.url
            )
        return "-"

    preview.short_description = "Vista Previa"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    min_num = 1
    fields = ('size', 'color', 'stock', 'price_modifier', 'is_active', 'sku')
    readonly_fields = ('sku',)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form_class = formset.form

        if hasattr(form_class, 'base_fields') and 'sku' in form_class.base_fields:
            form_class.base_fields['sku'].required = False
        elif hasattr(form_class, 'declared_fields') and 'sku' in form_class.declared_fields:
            form_class.declared_fields['sku'].required = False

        return formset


class InventoryMovementInline(admin.TabularInline):
    model = InventoryMovement
    extra = 0
    readonly_fields = ('product', 'variant', 'movement_type', 'quantity', 'user', 'created_at')
    can_delete = False
    classes = ['collapse']

    def has_add_permission(self, request, obj=None):
        return False


class ProductAdminForm(forms.ModelForm):
    TAX_CHOICES = [
        (0.00, '0% (Exento)'),
        (10.00, '10%'),
        (15.00, '15%'),
        (19.00, '19%'),
        (25.00, '25%'),
    ]

    tax_percentage = forms.ChoiceField(choices=TAX_CHOICES)

    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'categories': forms.SelectMultiple(attrs={
                'size': '10',
                'class': 'custom-select-multiple',
                'style': 'min-height: 200px; width: 100%;',
            }),
            'markup_percentage': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'categories' in self.fields:
            self.fields['categories'].queryset = (
                self.fields['categories']
                .queryset
                .select_related('parent')
                .order_by('tree_id', 'lft')
            )
        if not self.instance.pk:
            self.initial.setdefault('cost', 0.00)
            self.initial.setdefault('tax_percentage', 19.00)
            self.initial.setdefault('markup_percentage', 30.00)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = (
        'name',
        'sku',
        'price_display',
        'stock_status',
        'status',
        'stock_display',
        'has_variants',
        'absolute_category',
        'categories_display',
        'updated_at'
    )
    list_filter = ('status', 'categories', 'absolute_category', 'created_at')
    filter_horizontal = ('categories',)
    search_fields = ('name', 'sku', 'description', 'categories__name')
    list_editable = ('status',)
    list_select_related = True
    inlines = [ProductImageInline, ProductVariantInline, InventoryMovementInline]
    fieldsets = (
        ('Información Básica', {
            'fields': ('sku', 'name', 'description', 'absolute_category', 'categories')
        }),
        ('Costos y Precios', {
            'fields': (
                'cost',
                'tax_percentage',
                'cost_with_tax_display',
                'markup_percentage',
                'suggested_price_display',
                'price'
            ),
            'classes': ('collapse',)
        }),
        ('Inventario', {
            'fields': ('has_variants', '_stock', 'stock_display', 'min_stock'),
            'classes': ('collapse',)
        }),
        ('Estado', {
            'fields': ('status', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('stock_display', 'created_at', 'updated_at', 'stock_status', 'sku',
                       'cost_with_tax_display', 'suggested_price_display')
    save_on_top = True
    list_per_page = 25

    def stock_display(self, obj):
        return obj.calculated_stock

    stock_display.short_description = "Stock calculado"
    stock_display.short_description = "Stock total"
    stock_display.admin_order_field = '_stock'

    def stock_editable(self, obj):
        if obj and not obj.has_variants:
            return obj._stock
        return "-"

    stock_editable.short_description = "Stock único (si no tiene variantes)"

    def get_inline_instances(self, request, obj=None):
        inline_instances = []
        for inline in self.inlines:
            if inline.model == ProductImage:
                inline_instances.append(inline(self.model, self.admin_site))
            elif obj:  # Solo mostrar variantes o movimientos si ya existe
                inline_instances.append(inline(self.model, self.admin_site))
        return inline_instances

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_inlines'] = False
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Vista de edición que muestra los inlines"""
        extra_context = extra_context or {}
        extra_context['show_inlines'] = True
        return super().change_view(request, object_id, form_url, extra_context)

    def cost_with_tax_display(self, obj):
        return f"${obj.cost_with_tax:,.2f}"

    cost_with_tax_display.short_description = "Costo con IVA"

    def suggested_price_display(self, obj):
        return f"${obj.suggested_price:,.2f}"

    suggested_price_display.short_description = "Precio Sugerido"

    def price_display(self, obj):
        return f"${obj.price:,.2f}"

    price_display.short_description = "Precio"
    price_display.admin_order_field = 'price'

    def categories_display(self, obj):
        categories = obj.categories.all()[:3]
        display = ", ".join([c.name for c in categories])
        if obj.categories.count() > 3:
            display += f"... (+{obj.categories.count() - 3} más)"
        return display

    categories_display.short_description = "Categorías"

    def stock_status(self, obj):
        if obj.stock < obj.min_stock:
            return format_html(
                '<span style="color: red; font-weight: bold;">'
                '⬇ {} (mín. {})</span>',
                obj.stock,
                obj.min_stock
            )
        elif obj.stock == 0:
            return format_html(
                '<span style="color: #999; font-style: italic;">Agotado</span>'
            )
        return format_html(
            '<span style="color: green;">✔ {}</span>',
            obj.stock
        )

    stock_status.short_description = "Stock"
    stock_status.admin_order_field = 'stock'

    def save_model(self, request, obj, form, change):
        # Generar SKU si no existe
        if not obj.sku:
            obj.sku = obj.generate_product_sku()

        # Guardar el modelo primero
        super().save_model(request, obj, form, change)

        # Si es una creación nueva y tiene variantes, no validamos todavía
        if not change and obj.has_variants:
            self.message_user(
                request,
                "Producto creado correctamente. Ahora puede agregar las variantes necesarias.",
                level=messages.INFO
            )

    def save_related(self, request, form, formsets, change):
        product = form.instance

        # Guardar primero todas las relaciones
        super().save_related(request, form, formsets, change)

        # Solo validar si es una edición (no creación) y el producto tiene has_variants=True
        if change and product.has_variants and not product.variants.exists():
            self.message_user(
                request,
                "Advertencia: Este producto está marcado como 'con variantes' pero no tiene ninguna registrada. "
                "Por favor agregue al menos una variante.",
                level=messages.WARNING
            )
            # No lanzamos excepción, solo mostramos advertencia

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        if formset.model == ProductVariant:
            for instance in instances:
                instance.product = form.instance
                instance.save()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)



    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('categories')

    def response_add(self, request, obj, post_url_continue=None):
        # Redirigir a la página de edición para agregar variantes
        if obj.has_variants:
            return HttpResponseRedirect(
                reverse('admin:products_product_change', args=[obj.pk])
            )
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if obj.has_variants and not obj.variants.exists():
            self.message_user(
                request,
                "Recuerde que este producto está configurado para tener variantes pero aún no tiene ninguna.",
                level=messages.WARNING
            )
        return super().response_change(request, obj)


    def get_readonly_fields(self, request, obj=None):
        base_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.has_variants:
            base_fields.append('_stock')  # Bloquear edición si tiene variantes
        return base_fields





@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        'product_link',
        'sku_display',
        'size',
        'color',
        'stock',
        'price_with_modifier',
        'is_active'
    )
    list_filter = ('is_active', 'product__categories', 'size', 'color')
    search_fields = ('product__name', 'sku', 'size', 'color')
    list_editable = ('is_active', 'size', 'color', 'stock')
    autocomplete_fields = ('product',)
    list_select_related = ('product',)
    list_per_page = 50
    readonly_fields = ('sku', 'product', 'precio_sugerido_display',)
    fieldsets = (
        (None, {
            'fields': ('product', 'sku')
        }),
        ('Variación', {
            'fields': ('size', 'color')
        }),
        ('Inventario y Precio', {
            'fields': ('stock', 'price_modifier')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )

    def precio_sugerido_display(self, obj):
        try:
            return "${:,.2f}".format(obj.suggested_price)
        except:
            return "—"

    precio_sugerido_display.short_description = "Precio Sugerido"

    def get_readonly_fields(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return ('sku', 'product') + super().get_readonly_fields(request, obj)
        elif obj:
            return ('sku', 'product')
        return ('sku', 'precio_sugerido_display')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'product':
            kwargs['queryset'] = Product.objects.filter(has_variants=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def sku_display(self, obj):
        return format_html('<code>{}</code>', obj.sku)

    sku_display.short_description = "SKU"

    def product_link(self, obj):
        url = reverse('admin:products_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)

    product_link.short_description = "Producto"

    def get_changeform_initial_data(self, request):
        # Esto solo aplica al crear una nueva variante
        initial = super().get_changeform_initial_data(request)
        product_id = request.GET.get("product")
        if product_id:
            try:
                product = Product.objects.get(pk=product_id)
                # Calculamos el precio sugerido
                cost = Decimal(product.cost)
                tax = Decimal(product.tax_percentage)
                profit = Decimal(product.profit_margin)
                cost_with_tax = cost * (1 + tax / 100)
                suggested_price = cost_with_tax * (1 + profit / 100)
                initial['price_modifier'] = round(suggested_price - float(product.price), 2)
            except Exception:
                pass
        return initial

    def price_with_modifier(self, obj):
        try:
            product_price = Decimal(obj.product.price)
            modifier = Decimal(obj.price_modifier)
            total = product_price + modifier
        except (InvalidOperation, ValueError, TypeError, AttributeError):
            return "—"

        color = "green" if modifier >= 0 else "red"
        signo = "+" if modifier >= 0 else ""

        # Usa strings intermedios para evitar errores con SafeString
        total_str = f"{total:,.2f}"
        modifier_str = f"{modifier:,.2f}"

        return format_html(
            '<span>${} <small style="color:{};">({}{})</small></span>',
            total_str,
            color,
            signo,
            modifier_str
        )

    def save_model(self, request, obj, form, change):
        # Si no hay price_modifier definido, usar sugerido
        if not obj.price_modifier or obj.price_modifier == 0:
            try:
                suggested = obj.suggested_price
                obj.price_modifier = round(suggested - float(obj.product.price or 0), 2)
            except Exception:
                obj.price_modifier = 0

        # Guardar la variante primero
        super().save_model(request, obj, form, change)

        # También actualizar el precio del producto padre si está vacío o en 0
        if obj.product.price is None or obj.product.price == 0:
            try:
                # Usamos el precio sugerido como nuevo precio base del producto
                obj.product.price = obj.suggested_price
                obj.product.save()
            except Exception:
                pass

    price_with_modifier.short_description = "Precio Final"




@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = (
        'product_link',
        'variant_display',
        'movement_type_display',
        'quantity_display',
        'unit_price_display',
        'discount_display',
        'final_price_display',
        'total_amount_display',
        'user_link',
        'created_at',
    )
    list_filter = ('movement_type', 'created_at', 'user')
    search_fields = (
        'product__name',
        'variant__sku',
        'user__username',
        'user__first_name',
        'user__last_name',
    )
    readonly_fields = ('created_at', 'final_unit_price_display', 'total_amount_display')
    date_hierarchy = 'created_at'
    list_select_related = ('product', 'variant', 'user')
    list_per_page = 50
    fieldsets = (
        (None, {
            'fields': ('product', 'variant', 'movement_type', 'quantity', 'user')
        }),
        ('Información de Venta', {
            'fields': (
                'unit_price',
                'discount_percentage',
                'final_unit_price_display',
                'total_amount_display',
            ),
            'classes': ('collapse',)
        }),
        ('Notas', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # ----------------------
    # Ajustes clave
    # ----------------------
    def get_readonly_fields(self, request, obj=None):
        """
        Los campos calculados siempre deben estar en readonly_fields
        si están en fieldsets.
        """
        return self.readonly_fields

    # ----------------------
    # Displays
    # ----------------------
    def unit_price_display(self, obj):
        return f"${obj.unit_price:,.2f}" if obj.unit_price is not None else "-"
    unit_price_display.short_description = "Precio Unit."

    def discount_display(self, obj):
        return f"{obj.discount_percentage:.2f}%" if obj.discount_percentage else "-"
    discount_display.short_description = "Desc."

    def final_price_display(self, obj):
        return f"${obj.final_unit_price:,.2f}" if obj.final_unit_price else "-"
    final_price_display.short_description = "Precio Final"

    def total_amount_display(self, obj):
        return f"${obj.total_amount:,.2f}" if obj.total_amount else "-"
    total_amount_display.short_description = "Total"

    def final_unit_price_display(self, obj):
        return f"${obj.final_unit_price:,.2f}" if obj.final_unit_price else "-"
    final_unit_price_display.short_description = "Precio con Descuento"

    def product_link(self, obj):
        url = reverse('admin:products_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = "Producto"
    product_link.admin_order_field = 'product__name'

    def variant_display(self, obj):
        if obj.variant:
            attrs = []
            if obj.variant.size:
                attrs.append(obj.variant.size)
            if obj.variant.color:
                attrs.append(obj.variant.color)
            return ", ".join(attrs) or "-"
        return "-"
    variant_display.short_description = "Variante"

    def movement_type_display(self, obj):
        type_map = {
            'in': ('↗', 'Entrada'),
            'out': ('↘', 'Salida'),
            'adjust': ('↔', 'Ajuste'),
        }
        symbol, text = type_map.get(obj.movement_type, ('?', 'Desconocido'))
        return format_html(
            '<span style="font-size: 1.2em;">{} </span>{}',
            symbol,
            text
        )
    movement_type_display.short_description = "Tipo"

    def quantity_display(self, obj):
        # Colores: verde entrada, rojo salida, gris ajuste
        if obj.movement_type == 'in':
            color, sign = 'green', '+'
        elif obj.movement_type == 'out':
            color, sign = 'red', '-'
        else:
            color, sign = 'gray', ''  # ajuste muestra tal cual
        return format_html(
            '<span style="font-weight: bold; color: {};">{}{}</span>',
            color,
            sign,
            obj.quantity
        )
    quantity_display.short_description = "Cantidad"

    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html(
                '<a href="{}">{} {}</a>',
                url,
                obj.user.first_name or obj.user.username,
                obj.user.last_name or ""
            )
        return "-"
    user_link.short_description = "Usuario"