"""Resolve per-store / per-source Spree import settings from config.ini."""

from __future__ import annotations

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
    # Product ``source`` field prefixes that skip title spray/perfume filters.
    skip_spray_source_prefixes: tuple[str, ...] = ()
    skip_perfume_source_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImportJob:
    """One store run: shared defaults + ordered per-source jobs."""

    store_code: str
    sources: tuple[ImportSettings, ...]
    daily_upload_limit: int
    quota_timezone: str
    profile_section: str
    quota_key: str


def store_section_name(store_code: str) -> str:
    return f"{STORE_SECTION_PREFIX}{store_code}"


def vendor_section_name(store_code: str, vendor_id: str | int) -> str:
    return f"{STORE_SECTION_PREFIX}{store_code}.v{vendor_id}"


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
            str(item).strip().lower()
            for item in raw
            if str(item).strip()
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


def _settings_from_dict(data: dict, source_name: str | None = None) -> ImportSettings:
    missing = [k for k in REQUIRED_KEYS if k not in data or data[k] in (None, "")]
    if missing:
        raise ValueError(
            "Missing required import settings: "
            + ", ".join(missing)
            + (f" (source={source_name})" if source_name else "")
        )
    kwargs = {f.name: data[f.name] for f in fields(ImportSettings) if f.name in data}
    kwargs["merchant_id"] = str(data["merchant_id"])
    kwargs["vendor_id"] = str(data["vendor_id"])
    kwargs["source_name"] = source_name
    if "products_path" in data:
        kwargs["products_path"] = str(data["products_path"])
    kwargs["skip_spray_source_prefixes"] = parse_prefix_list(
        data.get("skip_spray_source_prefixes")
    )
    kwargs["skip_perfume_source_prefixes"] = parse_prefix_list(
        data.get("skip_perfume_source_prefixes")
    )
    return ImportSettings(**kwargs)


def resolve_profile_section(
    config: dict,
    store_code: str,
    vendor_id: str | int | None = None,
) -> str:
    """Prefer [spree.import.{store}.v{vendor}] when present, else store section."""
    if vendor_id is not None and str(vendor_id).strip() != "":
        vendor_sec = vendor_section_name(store_code, vendor_id)
        if _section(config, vendor_sec):
            return vendor_sec

    store_sec = store_section_name(store_code)
    if _section(config, store_sec):
        return store_sec

    if vendor_id is not None and str(vendor_id).strip() != "":
        raise ValueError(
            "Missing config section "
            f"[{vendor_section_name(store_code, vendor_id)}] "
            f"(or [{store_section_name(store_code)}])"
        )
    raise ValueError(
        f"Missing config section [{store_section_name(store_code)}]"
    )


def quota_key_for_profile(store_code: str, profile_section: str) -> str:
    prefix = store_section_name(store_code)
    if profile_section == prefix:
        return store_code
    if profile_section.startswith(prefix + "."):
        return f"{store_code}.{profile_section[len(prefix) + 1 :]}"
    return profile_section.replace(STORE_SECTION_PREFIX, "", 1)


def load_import_job(
    store_code: str,
    *,
    config: dict | None = None,
    source_filter: str | None = None,
    cli_overrides: dict | None = None,
    products_path: str | None = None,
) -> ImportJob:
    """Load store/vendor profile and per-source sections.

    Config layout::

        [spree.import.em-spree]
        vendor_id = 24
        sources = amz_ca, amz_uk

        [spree.import.em-spree.amz_ca]
        products_path = ...
        stock_location_id = 19
        shipping_category_id = 46901

        [spree.import.em-spree.v62]
        vendor_id = 62
        stock_location_id = 70
        shipping_category_id = 46910
        products_path = /path/aliexpress.jsonl
    """
    cfg = config if config is not None else None
    if cfg is None:
        from spree_product_importer.config import get_config

        cfg = get_config()

    cli = {k: v for k, v in (cli_overrides or {}).items() if v is not None}
    profile_name = resolve_profile_section(
        cfg,
        store_code,
        vendor_id=cli.get("vendor_id"),
    )
    profile_sec = _section(cfg, profile_name)
    quota_key = quota_key_for_profile(store_code, profile_name)

    source_names = parse_csv_list(profile_sec.get("sources"))

    if products_path:
        source_sec = (
            _section(cfg, source_section_name(profile_name, source_filter))
            if source_filter
            else {}
        )
        data = _merge_dicts(profile_sec, source_sec, cli)
        data["products_path"] = products_path
        settings = _settings_from_dict(data, source_filter)
        return ImportJob(
            store_code=store_code,
            sources=(settings,),
            daily_upload_limit=int(
                data.get("daily_upload_limit", settings.daily_upload_limit)
                or 0
            ),
            quota_timezone=str(
                data.get("quota_timezone", settings.quota_timezone)
            ),
            profile_section=profile_name,
            quota_key=quota_key,
        )

    if source_filter:
        source_names = [source_filter]

    if source_names:
        sources_list: list[ImportSettings] = []
        for name in source_names:
            source_sec = _section(
                cfg, source_section_name(profile_name, name)
            )
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
        sources = tuple(sources_list)
    else:
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

    base = _merge_dicts(profile_sec, cli)
    return ImportJob(
        store_code=store_code,
        sources=sources,
        daily_upload_limit=int(base.get("daily_upload_limit", 0) or 0),
        quota_timezone=str(
            base.get("quota_timezone", "America/Chicago")
        ),
        profile_section=profile_name,
        quota_key=quota_key,
    )
