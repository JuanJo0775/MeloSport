from django.apps import AppConfig
from django.db.models import CharField, TextField
from django.db.models.lookups import IContains


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.products'

    def ready(self):
        # Registrar señales (limpieza de imágenes, etc.)
        import apps.products.signals


@CharField.register_lookup
@TextField.register_lookup
class UnaccentIContains(IContains):
    lookup_name = "unaccent__icontains"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return f"unaccent({lhs}) ILIKE unaccent({rhs})", params