from decimal import Decimal, InvalidOperation

NBSP = "\xa0"  # espacio no separable: evita saltos entre "$" y la cifra

def format_cop(value, symbol=True, decimals=0, nbsp=True):
    """
    Formatea valores numéricos a pesos colombianos.
    120000 -> "$ 120.000" (por defecto sin decimales).
    decimals=2 -> "$ 120.000,00"
    symbol=False -> "120.000"
    """
    if value is None or value == "":
        return "-"
    try:
        q = Decimal(value)
        if decimals == 0:
            q = q.quantize(Decimal("1"))
        else:
            q = q.quantize(Decimal("1." + "0"*decimals))
    except (InvalidOperation, TypeError, ValueError):
        return "-"

    # Usa formateo con coma para miles y punto para decimales y luego hacemos swap.
    txt = f"{q:,.{decimals}f}"              # ej: 120,000.00
    txt = txt.replace(",", "_").replace(".", ",").replace("_", ".")  # -> 120.000,00

    prefix = f"${NBSP}" if symbol and nbsp else ("$ " if symbol else "")
    return f"{prefix}{txt}"
