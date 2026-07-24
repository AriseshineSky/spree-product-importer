"""Resolve per-store / per-vendor Spree import settings from config.ini."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace

STORE_SECTION_PREFIX = "spree.import."

REQUIRED_KEYS = (
    "merchant_id",
    "vendor_id",
    "stock_location_id",
    "shipping_category_id",
)

_INT_KEYS = frozenset(
    {
        "stock_location_id",
        "shipping_category_id",
        "tax_category_id",
        "min_shipping_days",
        "daily_upload_limit",
    }
)
_FLOAT_KEYS = frozenset({"min_price", "max_price"})
_VENDOR_KEY_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ImportSettings:
    merchant_id: str
    vendor_id: str
    stock_location_id: int
    shipping_category_id: int
    tax_category_id: int = 1
    taxonomy_name: str = "Categories"
    min_shipping_days: int = 7
    min_price: float = 15.0
    max_price: float = 300.0
    daily_upload_limit: int = 0
    quota_timezone: str = "America/Chicago"
    products_path: str | None = None
    source_name: str | None = None
    vendor_name: str | None = None
    vendor_key: str | None = None
    # Product ``source`` field prefixes that skip title spray/perfume filters.
    skip_spray_source_prefixes: tuple[str, ...] = ()
    skip_perfume_source_prefixes: tuple[str, ...] = ()
    # Product ``source`` prefixes that skip English-title requirement.
    skip_english_title_source_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImportJob:
    """One store+vendor run: shared defaults + ordered per-source jobs."""

    store_code: str
    vendor_name: str
    vendor_key: str
    sources: tuple[ImportSettings, ...]
    daily_upload_limit: int
    quota_timezone: str
    profile_section: str
    quota_key: str


def store_section_name(store_code: str) -> str:
    return f"{STORE_SECTION_PREFIX}{store_code}"


def normalize_vendor_key(name: str | None) -> str:
    text = (name or "").strip().lower()
    text = _VENDOR_KEY_RE.sub("-", text).strip("-")
    return text


def vendor_profile_section_name(store_code: str, vendor_key: str) -> str:
    key = normalize_vendor_key(vendor_key)
    return f"{store_section_name(store_code)}.{key}"


def source_section_name(profile_section: str, source: str) -> str:
    return f"{profile_section}.{source}"


def parse_csv_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts: list[str] = []
    for line in str(raw).replace(",", "\n").splitlines():
        item = line.strip()
        if item:
            parts.append(item)
    return parts


def _coerce_section(raw: dict | None) -> dict:
    if not raw:
        return {}
    out: dict = {}
    for key, value in raw.items():
        if value is None:
            continue
        text = str(value).strip()
        if text == "":
            continue
        if key in _INT_KEYS:
            out[key] = int(float(text))
        elif key in _FLOAT_KEYS:
            out[key] = float(text)
        else:
            out[key] = text
    return out


def _section(config: dict, name: str) -> dict:
    return _coerce_section(config.get(name) or {})


def _merge_dicts(*parts: dict) -> dict:
    merged: dict = {}
    for part in parts:
        merged.update(part)
    return merged


def parse_prefix_list(raw) -> tuple[str, ...]:
    if raw is None or raw == "":
        return ()
    if isinstance(raw, (list, tuple)):
        return tuple(
            str(item).strip().lower() for item in raw if str(item).strip()
        )
    return tuple(p.lower() for p in parse_csv_list(str(raw)))


def source_matches_prefixes(
    source: str | None,
    prefixes: tuple[str, ...] | list[str],
) -> bool:
    text = (source or "").strip().lower()
    if not text or not prefixes:
        return False
    return any(text.startswith(prefix) for prefix in prefixes if prefix)


def _settings_from_dict(
    data: dict,
    source_name: str | None = None,
) -> ImportSettings:
    missing = [
        k for k in REQUIRED_KEYS if k not in data or data[k] in (None, "")
    ]
    if missing:
        raise ValueError(
            "Missing required import settings: "
            + ", ".join(missing)
            + (f" (source={source_name})" if source_name else "")
        )
    kwargs = {
        f.name: data[f.name] for f in fields(ImportSettings) if f.name in data
    }
    kwargs["merchant_id"] = str(data["merchant_id"])
    kwargs["vendor_id"] = str(data["vendor_id"])
    kwargs["source_name"] = source_name
    if "products_path" in data:
        kwargs["products_path"] = str(data["products_path"])
    vendor_name = data.get("vendor_name") or data.get("vendor_key")
    vendor_key = normalize_vendor_key(
        data.get("vendor_key") or data.get("vendor_name") or ""
    )
    kwargs["vendor_name"] = str(vendor_name) if vendor_name else None
    kwargs["vendor_key"] = vendor_key or None
    kwargs["skip_spray_source_prefixes"] = parse_prefix_list(
        data.get("skip_spray_source_prefixes")
    )
    kwargs["skip_perfume_source_prefixes"] = parse_prefix_list(
        data.get("skip_perfume_source_prefixes")
    )
    kwargs["skip_english_title_source_prefixes"] = parse_prefix_list(
        data.get("skip_english_title_source_prefixes")
    )
    return ImportSettings(**kwargs)


def list_vendor_profile_sections(config: dict, store_code: str) -> list[str]:
    """Return vendor profile section names under a store (one key segment)."""
    prefix = store_section_name(store_code) + "."
    out: list[str] = []
    for name in config:
        if not str(name).startswith(prefix):
            continue
        rest = str(name)[len(prefix) :]
        if not rest or "." in rest:
            continue
        out.append(str(name))
    return sorted(out)


def resolve_profile_section(
    config: dict,
    store_code: str,
    vendor_name: str | None,
) -> tuple[str, str, str]:
    """Resolve vendor profile by key, display name, or vendor_id.

    Returns ``(section_name, vendor_key, vendor_name_display)``.
    """
    if not vendor_name or not str(vendor_name).strip():
        raise ValueError(
            "Vendor name is required. Use -vn/--vendor "
            "(e.g. topselected, em-hu, jp-cmedia)."
        )

    wanted = normalize_vendor_key(vendor_name)
    if not wanted:
        raise ValueError(f"Invalid vendor name: {vendor_name!r}")
    raw = str(vendor_name).strip()

    direct = vendor_profile_section_name(store_code, wanted)
    if _section(config, direct):
        sec = _section(config, direct)
        display = str(sec.get("vendor_name") or wanted)
        return direct, wanted, display

    for section in list_vendor_profile_sections(config, store_code):
        rest = section[len(store_section_name(store_code)) + 1 :]
        sec = _section(config, section)
        candidates = {
            normalize_vendor_key(rest),
            normalize_vendor_key(sec.get("vendor_name")),
            normalize_vendor_key(sec.get("vendor_key")),
        }
        vendor_id = str(sec.get("vendor_id") or "").strip()
        if vendor_id:
            candidates.add(normalize_vendor_key(vendor_id))
            candidates.add(vendor_id.lower())
        if wanted in candidates or raw.lower() == vendor_id.lower():
            display = str(sec.get("vendor_name") or rest)
            return section, normalize_vendor_key(rest), display

    available = [
        section[len(store_section_name(store_code)) + 1 :]
        for section in list_vendor_profile_sections(config, store_code)
    ]
    raise ValueError(
        f"No import profile for store={store_code!r} vendor={vendor_name!r}. "
        f"Expected section [{direct}]"
        + (f"; available: {', '.join(available)}" if available else "")
    )


def validate_source_for_profile(
    profile_section: str,
    allowed_sources: list[str],
    source: str,
) -> None:
    """Ensure ``source`` is listed under the vendor profile ``sources``."""
    if not allowed_sources:
        return
    if source in allowed_sources:
        return
    raise ValueError(
        f"Source {source!r} is not configured for "
        f"[{profile_section}]. Allowed sources: " + ", ".join(allowed_sources)
    )


def quota_key_for_profile(store_code: str, vendor_key: str) -> str:
    return f"{store_code}.{normalize_vendor_key(vendor_key)}"


def load_import_job(
    store_code: str,
    *,
    vendor_name: str | None,
    config: dict | None = None,
    source_filter: str | None = None,
    cli_overrides: dict | None = None,
    products_path: str | None = None,
) -> ImportJob:
    """Load store defaults + required vendor profile + per-source sections.

    Config layout::

        [spree.import.em-spree]
        merchant_id = ...
        min_shipping_days = 10

        [spree.import.em-spree.topselected]
        vendor_name = TopSelected
        vendor_id = 24
        sources = amz_ca, amz_uk, ebay_us

        [spree.import.em-spree.topselected.amz_ca]
        products_path = ...
        stock_location_id = 19
        shipping_category_id = 46901
    """
    cfg = config if config is not None else None
    if cfg is None:
        from spree_product_importer.config import get_config

        cfg = get_config()

    cli = {k: v for k, v in (cli_overrides or {}).items() if v is not None}
    # Profile selection is by vendor name only (not numeric vendor_id).
    cli.pop("vendor_id", None)

    profile_name, vendor_key, vendor_display = resolve_profile_section(
        cfg,
        store_code,
        vendor_name,
    )
    store_defaults = _section(cfg, store_section_name(store_code))
    profile_sec = _merge_dicts(
        store_defaults,
        _section(cfg, profile_name),
        {
            "vendor_key": vendor_key,
            "vendor_name": vendor_display,
        },
    )
    quota_key = quota_key_for_profile(store_code, vendor_key)

    source_names = parse_csv_list(profile_sec.get("sources"))

    if source_filter:
        validate_source_for_profile(profile_name, source_names, source_filter)

    def _job(sources: tuple[ImportSettings, ...], data: dict) -> ImportJob:
        return ImportJob(
            store_code=store_code,
            vendor_name=vendor_display,
            vendor_key=vendor_key,
            sources=sources,
            daily_upload_limit=int(data.get("daily_upload_limit", 0) or 0),
            quota_timezone=str(data.get("quota_timezone", "America/Chicago")),
            profile_section=profile_name,
            quota_key=quota_key,
        )

    if products_path:
        source_sec = (
            _section(cfg, source_section_name(profile_name, source_filter))
            if source_filter
            else {}
        )
        data = _merge_dicts(profile_sec, source_sec, cli)
        data["products_path"] = products_path
        settings = _settings_from_dict(data, source_filter)
        return _job((settings,), data)

    if source_filter:
        source_names = [source_filter]

    if source_names:
        sources_list: list[ImportSettings] = []
        for name in source_names:
            source_sec = _section(cfg, source_section_name(profile_name, name))
            if not source_sec:
                raise ValueError(
                    "Missing config section "
                    f"[{source_section_name(profile_name, name)}]"
                )
            data = _merge_dicts(profile_sec, source_sec, cli)
            if not data.get("products_path"):
                raise ValueError(
                    f"[{source_section_name(profile_name, name)}] "
                    "missing products_path"
                )
            sources_list.append(_settings_from_dict(data, name))
        return _job(tuple(sources_list), _merge_dicts(profile_sec, cli))

    paths = parse_csv_list(profile_sec.get("products_paths"))
    single = profile_sec.get("products_path")
    if single:
        paths = [str(single)] + paths
    if not paths:
        raise ValueError(
            f"[{profile_name}] needs `sources`, `products_path`, "
            "or `products_paths`"
        )
    data = _merge_dicts(profile_sec, cli)
    sources = tuple(
        replace(
            _settings_from_dict(data),
            products_path=path,
            source_name=None,
        )
        for path in paths
    )
    return _job(sources, data)
