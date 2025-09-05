from django.db.models import Lookup, TextField, CharField
from django.db.models.lookups import IContains

class UnaccentIContains(IContains):
    lookup_name = "unaccent_icontains"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)

        lhs = f"unaccent({lhs})"
        rhs = f"unaccent({rhs})"
        return f"{lhs} ILIKE {rhs}", lhs_params + rhs_params

# ✅ Registrar lookup en CharField y TextField
CharField.register_lookup(UnaccentIContains)
TextField.register_lookup(UnaccentIContains)
