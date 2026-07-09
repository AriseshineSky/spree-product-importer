from collections.abc import Callable

from spree_product_importer.app_logging import logger
from spree_product_importer.import_report import ImportReport
from spree_product_importer.product_source_lookup import (
    ProductSourceLookup,
    product_source_key,
)


class UploadPipeline:
    def __init__(
        self,
        lookup: ProductSourceLookup,
        report: ImportReport,
        upload_batch: Callable[[list[dict]], None],
        lookup_batch_size: int = 500,
        upload_batch_size: int = 50,
        max_upload_retries: int = 3,
    ):
        self.lookup = lookup
        self.report = report
        self.upload_batch = upload_batch
        self.lookup_batch_size = lookup_batch_size
        self.upload_batch_size = upload_batch_size
        self.max_upload_retries = max_upload_retries
        self._check_buf: list[dict] = []
        self._upload_buf: list[dict] = []

    def add(self, prod: dict) -> None:
        self._check_buf.append(prod)
        if len(self._check_buf) >= self.lookup_batch_size:
            self.flush_check_buffer()

    def flush_check_buffer(self) -> None:
        if not self._check_buf:
            return

        keys = []
        keyed_products: list[tuple[tuple[str, str], dict]] = []
        for prod in self._check_buf:
            key = product_source_key(prod)
            if key is None:
                self.report.missing_source_info += 1
                logger.debug(
                    "[MissingSourceInfo] ProductID: %s, Source: %r",
                    prod.get("product_id", ""),
                    prod.get("source"),
                )
                continue
            keys.append(key)
            keyed_products.append((key, prod))

        existing = self.lookup.find_existing(keys)
        for key, prod in keyed_products:
            if key in existing:
                self.report.already_exists += 1
                logger.debug(
                    "[AlreadyExists] Source: %s, SourceProductID: %s",
                    key[0],
                    key[1],
                )
                continue

            self.report.to_upload += 1
            self._upload_buf.append(prod)
            if len(self._upload_buf) >= self.upload_batch_size:
                self.flush_upload_buffer()

        self._check_buf.clear()

    def flush_upload_buffer(self) -> None:
        if not self._upload_buf:
            return

        max_retries = self.max_upload_retries
        while max_retries > 0:
            try:
                self.upload_batch(self._upload_buf)
                self._upload_buf.clear()
                return
            except Exception as e:
                logger.exception(e)
                max_retries -= 1

    def finish(self) -> None:
        self.flush_check_buffer()
        self.flush_upload_buffer()
