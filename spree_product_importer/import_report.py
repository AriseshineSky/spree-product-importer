from dataclasses import dataclass

from spree_product_importer.app_logging import logger


@dataclass
class ImportReport:
    invalid_standard_product: int = 0
    non_english_title: int = 0
    blacklisted: int = 0
    perfume_filtered: int = 0
    format_filtered: int = 0
    variants_truncated: int = 0
    already_exists: int = 0
    missing_source_info: int = 0
    to_upload: int = 0
    uploaded: int = 0
    quota_skipped: int = 0
    files_missing: int = 0

    def log_summary(self) -> None:
        logger.info(
            "[ProductAudit] InvalidStandardProduct: %s, "
            "NonEnglishTitle: %s, Blacklisted: %s, PerfumeFiltered: %s, "
            "FormatFiltered: %s, VariantsTruncated: %s, AlreadyExists: %s, "
            "MissingSourceInfo: %s, ToUpload: %s, Uploaded: %s, "
            "QuotaSkipped: %s, FilesMissing: %s",
            self.invalid_standard_product,
            self.non_english_title,
            self.blacklisted,
            self.perfume_filtered,
            self.format_filtered,
            self.variants_truncated,
            self.already_exists,
            self.missing_source_info,
            self.to_upload,
            self.uploaded,
            self.quota_skipped,
            self.files_missing,
        )
