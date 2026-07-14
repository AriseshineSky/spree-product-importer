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
from spree_product_importer.import_report import ImportReport
from spree_product_importer.perfume_title_filter import (
    is_perfume_from_product_titles,
)
from spree_product_importer.product_format_filter import (
    product_format_reject_reason,
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


@click.command("Import products to Spree")
@click.option("-s", "--store_code", type=str, required=True)
@click.option(
    "-ms",
    "--min_shipping_days",
    type=int,
    default=7,
    help="Minimum shipping days, default is 7.",
)
@click.option(
    "-tn",
    "--taxonomy_name",
    type=str,
    default="Categories",
    help='Spree taxonomy name, default is "Categories".',
)
@click.option(
    "-m",
    "--merchant_id",
    required=True,
    type=str,
    help="Google Merchant ID to upload to.",
)
@click.option(
    "-v",
    "--vendor_id",
    required=True,
    type=str,
    help="Vendor ID that products belongs to.",
)
@click.option(
    "-tc",
    "--tax_category_id",
    type=int,
    default=1,
    help="Spree tax category ID, default is 1.",
)
@click.option(
    "-sl",
    "--stock_location_id",
    required=True,
    type=int,
    help="Spree stock location ID.",
)
@click.option(
    "-sc",
    "--shipping_category_id",
    required=True,
    type=int,
    help="Spree shipping category ID.",
)
@click.option(
    "-pl",
    "--min_price",
    type=float,
    default=15,
    help="Minimum product price, default is 15.",
)
@click.option(
    "-ph",
    "--max_price",
    type=float,
    default=300,
    help="Maximum product price, default is 300.",
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
@click.argument("products_path")
def import_products(
    store_code,
    products_path,
    shipping_category_id,
    stock_location_id,
    merchant_id,
    vendor_id,
    tax_category_id=1,
    taxonomy_name="Categories",
    min_shipping_days=7,
    min_price=15,
    max_price=300,
    dont_filter_blacklist=False,
    dont_optimize_title=False,
    dont_require_english_title=False,
    allow_perfume=False,
):
    init_db()
    init_pg_db()

    if not products_path:
        return

    products_path = os.path.abspath(os.path.expanduser(products_path))
    if not os.path.isfile(products_path):
        return

    store = StoreUtil.get_store_by_code(store_code)
    if not store:
        return

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

    def upload_batch(products_buf: list[dict]) -> None:
        spree_api.import_products(
            products_buf,
            stock_location_id,
            shipping_category_id,
            vendor_id,
            merchant_id,
            min_shipping_days,
            taxonomy_name,
            tax_category_id,
        )

    pipeline = UploadPipeline(
        lookup=ProductSourceLookup(),
        report=report,
        upload_batch=upload_batch,
    )

    with open(products_path, encoding="utf-8", errors="ignore") as fh:
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

            if "amz" not in prod["source"].lower():
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

            if category_filter(store_code, prod):
                logger.debug(f"[BlacklistCategory] {prod['categories']}")
                continue

            price = prod.get("price", None)
            if not price or price < min_price or price > max_price:
                if not price:
                    logger.debug("[NoPrice]")
                elif price < min_price:
                    logger.debug("[PriceTooLow] Price: %s", price)
                elif price > max_price:
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
                    s = "{} {}".format(brand.lower(), title.lower())
                else:
                    s = title.lower()
                result = blacklist_filter.is_blacklisted(s)
                if result:
                    report.blacklisted += 1
                    logger.debug(
                        "[ProductFiltered] ProductID: %s, "
                        "Reason: Blacklisted - %s, Title: %s",
                        prod.get("source_product_id", ""),
                        result,
                        s,
                    )
                    continue

            prod.pop("categories", None)
            pipeline.add(prod)

    pipeline.finish()
    report.log_summary()


if __name__ == "__main__":
    import_products()
