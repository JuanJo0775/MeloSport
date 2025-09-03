# apps/products/urls_inventory.py
from django.urls import path
from . import views_inventory as views

app_name = "inventory"

urlpatterns = [
    path("", views.InventoryIndexView.as_view(), name="index"),

    # Listado principal de productos
    path("productos/", views.ProductsInventoryListView.as_view(), name="products_inventory_list"),
    path("productos/<int:pk>/variantes/", views.ProductVariantsView.as_view(), name="product_variants"),
    path("productos/<int:pk>/variantes/json/", views.ProductVariantsJSONView.as_view(), name="product_variants_json"),

    # Acciones masivas
    path("bulk/add-products/", views.BulkAddStockView.as_view(), name="bulk_add_products"),
    path("bulk/add-variants/", views.BulkVariantsStockView.as_view(), name="bulk_add_variants"),

    # CRUD movimientos
    path("movimientos/", views.InventoryListView.as_view(), name="inventory_list"),
    path("movimientos/crear/", views.InventoryCreateFromProductView.as_view(), name="inventory_create"),
    path("movimientos/ajuste/", views.InventoryAdjustView.as_view(), name="inventory_adjust"),
    path("movimientos/<int:pk>/editar/", views.InventoryUpdateView.as_view(), name="inventory_update"),
    path("movimientos/<int:pk>/eliminar/", views.InventoryDeleteView.as_view(), name="inventory_delete"),
]
