MAX_OPTIONS = 2
MAX_VARIANTS = 10


def product_format_reject_reason(prod: dict) -> str | None:
    """Return a skip reason if options/variants exceed supported limits.

    Products with more than 2 options or more than 10 variants are
    skipped for now (not uploaded).
    """
    options = prod.get("options") or []
    variants = prod.get("variants") or []

    if not isinstance(options, list):
        options = []
    if not isinstance(variants, list):
        variants = []

    if len(options) > MAX_OPTIONS:
        return f"TooManyOptions ({len(options)} > {MAX_OPTIONS})"
    if len(variants) > MAX_VARIANTS:
        return f"TooManyVariants ({len(variants)} > {MAX_VARIANTS})"
    return None
