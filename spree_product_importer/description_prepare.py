"""Source-specific product mutations applied right before Spree upload."""

from __future__ import annotations


def _format_ebay_description(product: dict) -> dict:
    from em_tasks.channels.listing.ebay.config import (
        format_ebay_description,
    )

    return format_ebay_description(product)


def prepare_product_description(prod: dict) -> None:
    """Apply channel description rules in-place before upload.

    Ebay_*: legacy rules from ``format_ebay_description`` —
    strip case-insensitive ``ebay`` substrings, fall back to title when
    empty, and remove ``<a>`` tags from HTML descriptions.
    """
    source = (prod.get("source") or "").strip().lower()
    if source.startswith("ebay"):
        _format_ebay_description(prod)
