from rest_framework import serializers
from apps.products.models import Product, ProductImage, ProductVariant
from apps.categories.models import Category, AbsoluteCategory
from apps.frontend.models import FeaturedProductCarousel, ContactMessage


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'description', 'parent', 'is_active')
        read_only_fields = ('id',)

class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ('id', 'image_url', 'is_main', 'order')
        read_only_fields = ('id','is_main','order')

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        if obj.image:
            return obj.image.url
        return None

class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ('id','sku','size','color','stock','price_modifier','is_active')
        read_only_fields = ('id',)

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    main_image = serializers.SerializerMethodField()   # <-- Nuevo campo
    variants = ProductVariantSerializer(many=True, read_only=True)
    absolute_category = serializers.SerializerMethodField()
    categories = CategorySerializer(many=True, read_only=True)
    stock = serializers.IntegerField(source='_stock', read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'sku', 'name', 'description', 'price', 'cost',
            'tax_percentage', 'markup_percentage', 'stock', 'min_stock', 'status',
            'has_variants', 'absolute_category', 'categories', 'images', 'main_image', 'variants',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_main_image(self, obj):
        request = self.context.get('request', None)
        first = None
        if hasattr(obj, 'images') and getattr(obj, 'images').exists():
            first = obj.images.filter(is_main=True).first() or obj.images.first()
        if first and getattr(first, 'image', None):
            url = first.image.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_absolute_category(self, obj):
        if obj.absolute_category and obj.absolute_category.activo:
            return AbsoluteCategorySerializer(obj.absolute_category).data
        return None


class CarouselItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = FeaturedProductCarousel
        fields = [
            'id', 'custom_title', 'custom_subtitle',
            'display_order', 'is_active', 'created_at',
            'product_id', 'product_name', 'product_price'
        ]
        read_only_fields = fields  # Solo lectura

class ContactoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'phone', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_message(self, value):
        if len(value) < 10:
            raise serializers.ValidationError("El mensaje es demasiado corto.")
        return value

class AbsoluteCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source='get_product_count', read_only=True)

    class Meta:
        model = AbsoluteCategory
        fields = ('id', 'nombre', 'descripcion', 'activo', 'product_count')

