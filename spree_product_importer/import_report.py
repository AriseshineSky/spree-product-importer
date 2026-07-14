from dataclasses import dataclass

from spree_product_importer.app_logging import logger


@dataclass
class ImportReport:
    invalid_standard_product: int = 0
    non_english_title: int = 0
    blacklisted: int = 0
    perfume_filtered: int = 0
    format_filtered: int = 0
    already_exists: int = 0
    missing_source_info: int = 0
    to_upload: int = 0

    def log_summary(self) -> None:
        logger.info(
            "[ProductAudit] InvalidStandardProduct: %s, "
            "NonEnglishTitle: %s, Blacklisted: %s, PerfumeFiltered: %s, "
            "FormatFiltered: %s, AlreadyExists: %s, "
            "MissingSourceInfo: %s, ToUpload: %s",
            self.invalid_standard_product,
            self.non_english_title,
            self.blacklisted,
            self.perfume_filtered,
            self.format_filtered,
            self.already_exists,
            self.missing_source_info,
            self.to_upload,
        )
