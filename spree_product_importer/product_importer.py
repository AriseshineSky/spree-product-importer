import json
import os
import re

import click
from em_product.product import StandardProduct
from em_tasks.amazon.listing.import_root_category import (
    is_blocked_import_root_category,
)
from em_tasks.channels.listing.shared.upload_title import (
    upload_title_is_english,
)
from em_tasks.spree.api import SpreeApi
from em_tasks.store.store_util import StoreUtil
from em_tasks.utils.blacklist_filter import BlacklistFilter

from spree_product_importer.app_logging import logger
from spree_product_importer.config import init_db, init_pg_db
from spree_product_importer.daily_upload_quota import DailyUploadQuota
from spree_product_importer.import_report import ImportReport
from spree_product_importer.import_settings import (
    ImportSettings,
    load_import_job,
)
from spree_product_importer.description_prepare import (
    prepare_product_description,
)
from spree_product_importer.perfume_title_filter import (
    is_perfume_from_product_titles,
)
from spree_product_importer.product_format_filter import (
    product_format_reject_reason,
    truncate_variants_inplace,
)
from spree_product_importer.product_source_lookup import ProductSourceLookup
from spree_product_importer.upload_pipeline import UploadPipeline

_SPRAY_WORD_RE = re.compile(r"\bspray\b", re.IGNORECASE)


def is_spray_from_product_titles(prod: dict) -> bool:
    source = (prod.get("source") or "").lower()
    if source.startswith("amz_"):
        return False

    for key in ("title", "title_en"):
        title = prod.get(key)
        if title and _SPRAY_WORD_RE.search(title):
            return True

    return False


def category_filter(store_code: str, prod: dict):
    return is_blocked_import_root_category(
        prod.get("categories"),
        store_code=store_code,
    )


def _process_file(
    *,
    store_code: str,
    settings: ImportSettings,
    spree_api: SpreeApi,
    pipeline: UploadPipeline,
    report: ImportReport,
    blacklist_filter: BlacklistFilter | None,
    require_english_title: bool,
    allow_perfume: bool,
) -> bool:
    """Process one products file. Returns False if quota exhausted."""
    path = settings.products_path
    assert path
    label = settings.source_name or path
    logger.info(
        "[ImportSource] name=%s path=%s vendor_id=%s "
        "stock_location_id=%s shipping_category_id=%s "
        "min_shipping_days=%s min_price=%s",
        label,
        path,
        settings.vendor_id,
        settings.stock_location_id,
        settings.shipping_category_id,
        settings.min_shipping_days,
        settings.min_price,
    )

    if not os.path.isfile(path):
        report.files_missing += 1
        logger.warning("[ImportSourceMissing] %s", path)
        return True

    def upload_batch(products_buf: list[dict]) -> None:
        spree_api.import_products(
            products_buf,
            settings.stock_location_id,
            settings.shipping_category_id,
            settings.vendor_id,
            settings.merchant_id,
            settings.min_shipping_days,
            settings.taxonomy_name,
            settings.tax_category_id,
        )

    pipeline.upload_batch = upload_batch

    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue

            prod = None
            try:
                prod = json.loads(s)
            except Exception as e:
                logger.exception(e)

            if not prod:
                continue

            # Ebay (and other channel) description cleanup must run before
            # StandardProduct validation, which rejects residual <a> tags.
            prepare_product_description(prod)

            if category_filter(store_code, prod):
                logger.debug(f"[BlacklistCategory] {prod.get('categories')}")
                continue

            # Drop categories before StandardProduct — Spree upload does not
            # use them, and duplicate path segments fail validation.
            prod.pop("categories", None)

            if "amz" not in str(prod.get("source", "")).lower():
                try:
                    StandardProduct(**prod)
                except Exception as e:
                    report.invalid_standard_product += 1
                    logger.debug(
                        "[InvalidStandardProduct] ProductID: %s, Error: %s",
                        prod.get("product_id", ""),
                        e,
                    )
                    continue

            price = prod.get("price", None)
            if (
                not price
                or price < settings.min_price
                or price > settings.max_price
            ):
                if not price:
                    logger.debug("[NoPrice]")
                elif price < settings.min_price:
                    logger.debug("[PriceTooLow] Price: %s", price)
                elif price > settings.max_price:
                    logger.debug("[PriceTooHigh] Price: %s", price)
                continue

            if is_spray_from_product_titles(prod):
                report.blacklisted += 1
                logger.debug(
                    "[ProductFiltered] ProductID: %s, "
                    "Reason: Blacklisted - Spray, Title: %s",
                    prod.get("source_product_id", ""),
                    prod.get("title_en") or prod.get("title") or "",
                )
                continue

            if not allow_perfume and is_perfume_from_product_titles(prod):
                report.perfume_filtered += 1
                logger.debug(
                    "[ProductFiltered] ProductID: %s, "
                    "Reason: Perfume - Title keyword, Title: %s",
                    prod.get("source_product_id", ""),
                    prod.get("title_en") or prod.get("title") or "",
                )
                continue

            format_reason = product_format_reject_reason(prod)
            if format_reason:
                report.format_filtered += 1
                logger.debug(
                    "[ProductFiltered] ProductID: %s, "
                    "Reason: Format - %s, Options: %s, Variants: %s",
                    prod.get("source_product_id", ""),
                    format_reason,
                    len(prod.get("options") or []),
                    len(prod.get("variants") or []),
                )
                continue

            dropped = truncate_variants_inplace(prod)
            if dropped:
                report.variants_truncated += 1
                logger.debug(
                    "[VariantsTruncated] ProductID: %s, "
                    "Dropped: %s, Kept: %s",
                    prod.get("source_product_id", ""),
                    dropped,
                    len(prod.get("variants") or []),
                )

            if require_english_title and not upload_title_is_english(prod):
                report.non_english_title += 1
                logger.debug(
                    "[NonEnglishTitle] ProductID: %s, "
                    "SourceProductID: %s, Title: %r",
                    prod.get("product_id", ""),
                    prod.get("source_product_id", ""),
                    (prod.get("title_en") or prod.get("title") or "")[:120],
                )
                continue

            if blacklist_filter:
                brand = prod.get("brand", None)
                title = prod.get("title_en", None) or prod.get("title", "")
                if brand:
                    bl_s = "{} {}".format(brand.lower(), title.lower())
                else:
                    bl_s = title.lower()
                result = blacklist_filter.is_blacklisted(bl_s)
                if result:
                    report.blacklisted += 1
                    logger.debug(
                        "[ProductFiltered] ProductID: %s, "
                        "Reason: Blacklisted - %s, Title: %s",
                        prod.get("source_product_id", ""),
                        result,
                        bl_s,
                    )
                    continue

            if not pipeline.add(prod):
                logger.info(
                    "[DailyQuotaReached] Stopping file %s",
                    label,
                )
                pipeline.finish()
                return False

    pipeline.finish()
    return not pipeline.quota_exhausted


@click.command("Import products to Spree")
@click.option("-s", "--store_code", type=str, required=True)
@click.option(
    "-src",
    "--source",
    "source_name",
    type=str,
    default=None,
    help="Only upload one configured source (e.g. amz_ca, amz_uk).",
)
@click.option(
    "-ms",
    "--min_shipping_days",
    type=int,
    default=None,
    help="Minimum shipping days (default from config or 7).",
)
@click.option(
    "-tn",
    "--taxonomy_name",
    type=str,
    default=None,
    help='Spree taxonomy name (default from config or "Categories").',
)
@click.option(
    "-m",
    "--merchant_id",
    required=False,
    default=None,
    type=str,
    help="Google Merchant ID (default from config).",
)
@click.option(
    "-v",
    "--vendor_id",
    required=False,
    default=None,
    type=str,
    help="Vendor ID (default from config).",
)
@click.option(
    "-tc",
    "--tax_category_id",
    type=int,
    default=None,
    help="Spree tax category ID (default from config or 1).",
)
@click.option(
    "-sl",
    "--stock_location_id",
    required=False,
    default=None,
    type=int,
    help="Spree stock location ID (default from config/source).",
)
@click.option(
    "-sc",
    "--shipping_category_id",
    required=False,
    default=None,
    type=int,
    help="Spree shipping category ID (default from config/source).",
)
@click.option(
    "-pl",
    "--min_price",
    type=float,
    default=None,
    help="Minimum product price (default from config or 15).",
)
@click.option(
    "-ph",
    "--max_price",
    type=float,
    default=None,
    help="Maximum product price (default from config or 300).",
)
@click.option(
    "-dl",
    "--daily_upload_limit",
    type=int,
    default=None,
    help="Max successful uploads per day (0=unlimited).",
)
@click.option(
    "-nb",
    "--dont_filter_blacklist",
    is_flag=True,
    default=False,
    help="Dont filter blacklist products.",
)
@click.option(
    "-ne",
    "--dont_require_english_title",
    is_flag=True,
    default=False,
    help=(
        "Allow upload when title/title_en is missing or not "
        "detected as English."
    ),
)
@click.option(
    "-ap",
    "--allow_perfume",
    is_flag=True,
    default=False,
    help=(
        "Allow perfume products to upload (default: filter by title keywords)."
    ),
)
@click.argument("products_path", required=False, default=None)
def import_products(
    store_code,
    products_path,
    source_name,
    shipping_category_id,
    stock_location_id,
    merchant_id,
    vendor_id,
    tax_category_id,
    taxonomy_name,
    min_shipping_days,
    min_price,
    max_price,
    daily_upload_limit,
    dont_filter_blacklist=False,
    dont_require_english_title=False,
    allow_perfume=False,
):
    init_db()
    init_pg_db()

    cli_overrides = {
        "merchant_id": merchant_id,
        "vendor_id": vendor_id,
        "stock_location_id": stock_location_id,
        "shipping_category_id": shipping_category_id,
        "tax_category_id": tax_category_id,
        "taxonomy_name": taxonomy_name,
        "min_shipping_days": min_shipping_days,
        "min_price": min_price,
        "max_price": max_price,
        "daily_upload_limit": daily_upload_limit,
    }

    try:
        job = load_import_job(
            store_code,
            source_filter=source_name,
            cli_overrides=cli_overrides,
            products_path=(
                os.path.abspath(os.path.expanduser(products_path))
                if products_path
                else None
            ),
        )
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    store = StoreUtil.get_store_by_code(store_code)
    if not store:
        raise click.ClickException(f"Store not found: {store_code}")

    if dont_filter_blacklist:
        blacklist_filter = None
    else:
        blacklist_filter = BlacklistFilter()

    credential = json.loads(store.api_credential)
    spree_api = SpreeApi(
        credential["endpoint"],
        credential["api_key"],
        credential.get("api_version", "v1"),
    )

    report = ImportReport()
    require_english_title = not dont_require_english_title
    quota = DailyUploadQuota(
        job.quota_key,
        job.daily_upload_limit,
        timezone=job.quota_timezone,
    )
    logger.info(
        "[ImportJob] store=%s profile=%s quota_key=%s sources=%s "
        "daily_limit=%s quota_used=%s timezone=%s",
        store_code,
        job.profile_section,
        job.quota_key,
        [s.source_name or s.products_path for s in job.sources],
        job.daily_upload_limit or "unlimited",
        quota.uploaded,
        job.quota_timezone,
    )
    if quota.is_exhausted:
        logger.info(
            "[DailyQuotaReached] quota_key=%s uploaded=%s limit=%s — skipping",
            job.quota_key,
            quota.uploaded,
            quota.limit,
        )
        report.log_summary()
        return

    pipeline = UploadPipeline(
        lookup=ProductSourceLookup(),
        report=report,
        upload_batch=lambda _buf: None,
        quota=quota,
    )

    for settings in job.sources:
        still_ok = _process_file(
            store_code=store_code,
            settings=settings,
            spree_api=spree_api,
            pipeline=pipeline,
            report=report,
            blacklist_filter=blacklist_filter,
            require_english_title=require_english_title,
            allow_perfume=allow_perfume,
        )
        if not still_ok:
            break

    if quota.enabled:
        logger.info(
            "[DailyQuota] quota_key=%s uploaded_today=%s limit=%s remaining=%s",
            job.quota_key,
            quota.uploaded,
            quota.limit,
            quota.remaining,
        )
    report.log_summary()


if __name__ == "__main__":
    import_products()
