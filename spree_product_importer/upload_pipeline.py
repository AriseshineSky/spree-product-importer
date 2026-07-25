import re
import time
from collections.abc import Callable

from spree_product_importer.app_logging import logger
from spree_product_importer.daily_upload_quota import DailyUploadQuota
from spree_product_importer.import_report import ImportReport
from spree_product_importer.product_source_lookup import (
    ProductSourceLookup,
    product_source_key,
)

# Spree / GCLB HTML body: "Please try again in 30 seconds."
_TRANSIENT_HTTP_RE = re.compile(r"HTTP (429|500|502|503|504)\b")
_TRANSIENT_TEXT_RE = re.compile(
    r"(timed out|timeout|connection (reset|aborted|refused)|temporarily)",
    re.IGNORECASE,
)


def is_transient_upload_error(exc: BaseException) -> bool:
    """True for temporary Spree / network failures worth waiting to retry."""
    if isinstance(
        exc,
        (TimeoutError, ConnectionError, ConnectionResetError, BrokenPipeError),
    ):
        return True
    msg = str(exc)
    if _TRANSIENT_HTTP_RE.search(msg):
        return True
    if _TRANSIENT_TEXT_RE.search(msg):
        return True
    name = type(exc).__name__
    return name in {
        "ConnectTimeout",
        "ReadTimeout",
        "Timeout",
        "ConnectionError",
        "ProxyError",
        "SSLError",
    }


class UploadPipeline:
    def __init__(
        self,
        lookup: ProductSourceLookup,
        report: ImportReport,
        upload_batch: Callable[[list[dict]], None],
        quota: DailyUploadQuota | None = None,
        lookup_batch_size: int = 500,
        upload_batch_size: int = 50,
        max_upload_retries: int = 5,
        retry_wait_seconds: float = 30.0,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.lookup = lookup
        self.report = report
        self.upload_batch = upload_batch
        self.quota = quota
        self.lookup_batch_size = lookup_batch_size
        self.upload_batch_size = upload_batch_size
        self.max_upload_retries = max_upload_retries
        self.retry_wait_seconds = retry_wait_seconds
        self.sleeper = sleeper
        self._check_buf: list[dict] = []
        self._upload_buf: list[dict] = []
        self.quota_exhausted = False

    def add(self, prod: dict) -> bool:
        """Queue a product. Returns False when daily quota is exhausted."""
        if self.quota_exhausted:
            self.report.quota_skipped += 1
            return False

        self._check_buf.append(prod)
        if len(self._check_buf) >= self.lookup_batch_size:
            self.flush_check_buffer()
        return not self.quota_exhausted

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
            if self.quota_exhausted:
                self.report.quota_skipped += 1
                continue

            if key in existing:
                self.report.already_exists += 1
                logger.debug(
                    "[AlreadyExists] Source: %s, SourceProductID: %s",
                    key[0],
                    key[1],
                )
                continue

            if self.quota and self.quota.enabled:
                allowed = self.quota.take(len(self._upload_buf) + 1)
                if allowed <= len(self._upload_buf):
                    self.quota_exhausted = True
                    self.report.quota_skipped += 1
                    continue

            self.report.to_upload += 1
            self._upload_buf.append(prod)
            if len(self._upload_buf) >= self.upload_batch_size:
                self.flush_upload_buffer()

        self._check_buf.clear()

    def flush_upload_buffer(self) -> None:
        if not self._upload_buf:
            return

        batch = list(self._upload_buf)
        if self.quota and self.quota.enabled:
            allowed = self.quota.take(len(batch))
            if allowed <= 0:
                self.report.quota_skipped += len(batch)
                self.report.to_upload -= len(batch)
                self._upload_buf.clear()
                self.quota_exhausted = True
                return
            if allowed < len(batch):
                skipped = len(batch) - allowed
                self.report.quota_skipped += skipped
                self.report.to_upload -= skipped
                batch = batch[:allowed]
                self.quota_exhausted = True

        attempts = max(1, self.max_upload_retries)
        last_error: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                self.upload_batch(batch)
                self.report.uploaded += len(batch)
                if self.quota:
                    self.quota.record(len(batch))
                self._upload_buf.clear()
                return
            except Exception as e:
                last_error = e
                logger.exception(e)
                if attempt >= attempts:
                    break
                if is_transient_upload_error(e):
                    # 30s, 60s, 90s, ... (matches Spree "try again in 30 seconds")
                    wait = self.retry_wait_seconds * attempt
                    logger.warning(
                        "[UploadRetry] attempt %s/%s failed; waiting %.0fs "
                        "before retry (%s)",
                        attempt,
                        attempts,
                        wait,
                        e,
                    )
                    self.sleeper(wait)
                else:
                    logger.warning(
                        "[UploadRetry] non-transient error on attempt %s/%s; "
                        "retrying immediately (%s)",
                        attempt,
                        attempts,
                        e,
                    )

        # Keep buffer so a later finish()/manual re-run can retry; surface failure.
        assert last_error is not None
        raise last_error

    def finish(self) -> None:
        self.flush_check_buffer()
        self.flush_upload_buffer()
