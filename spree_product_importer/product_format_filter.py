MAX_OPTIONS = 2
MAX_VARIANTS = 10

# Ebay_US may carry shipping window; all other sources must leave it empty.
_EBAY_US_SOURCE = "ebay_us"


def _is_empty_shipping_day(value) -> bool:
    return value is None or value == ""


def _shipping_days_must_be_empty(prod: dict) -> bool:
    source = (prod.get("source") or "").strip().lower()
    return source != _EBAY_US_SOURCE


def product_format_reject_reason(prod: dict) -> str | None:
    """Return a skip reason if product format is not uploadable.

    - 3+ options are skipped (>= 3 / more than MAX_OPTIONS).
    - Non-Ebay_US products must have empty shipping_days_min/max.

    Variants over the limit are truncated by
    ``truncate_variants_inplace`` (not rejected here).
    """
    options = prod.get("options") or []
    if not isinstance(options, list):
        options = []

    if len(options) >= 3:
        return f"TooManyOptions ({len(options)} >= 3)"

    if _shipping_days_must_be_empty(prod):
        for key in ("shipping_days_min", "shipping_days_max"):
            if not _is_empty_shipping_day(prod.get(key)):
                return (
                    f"ShippingDaysNotEmpty ({key}={prod.get(key)!r} "
                    f"source={prod.get('source')!r})"
                )

    return None


def truncate_variants_inplace(prod: dict) -> int:
    """Keep at most MAX_VARIANTS variants; return number dropped."""
    variants = prod.get("variants")
    if not isinstance(variants, list):
        return 0
    if len(variants) <= MAX_VARIANTS:
        return 0
    dropped = len(variants) - MAX_VARIANTS
    prod["variants"] = variants[:MAX_VARIANTS]
    return dropped
