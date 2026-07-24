import tempfile
import unittest
from datetime import date
from pathlib import Path

from spree_product_importer.daily_upload_quota import DailyUploadQuota
from spree_product_importer.import_report import ImportReport
from spree_product_importer.import_settings import load_import_job
from spree_product_importer.upload_pipeline import UploadPipeline


def _cfg():
    return {
        "spree.import.em-spree": {
            "merchant_id": "654568556",
            "vendor_id": "24",
            "min_shipping_days": "10",
            "min_price": "15",
            "daily_upload_limit": "5",
            "quota_timezone": "America/Chicago",
            "sources": "amz_ca, amz_uk, ebay_us",
        },
        "spree.import.em-spree.amz_ca": {
            "products_path": "/data/amz_ca.jsonl",
            "stock_location_id": "19",
            "shipping_category_id": "46901",
        },
        "spree.import.em-spree.amz_uk": {
            "products_path": "/data/amz_uk.jsonl",
            "stock_location_id": "41",
            "shipping_category_id": "46873",
        },
        "spree.import.em-spree.ebay_us": {
            "products_path": "/data/ebay_us.jsonl",
            "stock_location_id": "19",
            "shipping_category_id": "46862",
        },
    }


class ImportSettingsTest(unittest.TestCase):
    def test_loads_per_source_overrides(self):
        job = load_import_job("em-spree", config=_cfg())
        self.assertEqual(job.daily_upload_limit, 5)
        self.assertEqual(job.quota_key, "em-spree")
        self.assertEqual(len(job.sources), 3)
        ca, uk, ebay = job.sources
        self.assertEqual(ca.source_name, "amz_ca")
        self.assertEqual(ca.stock_location_id, 19)
        self.assertEqual(ca.shipping_category_id, 46901)
        self.assertEqual(ca.vendor_id, "24")
        self.assertEqual(ca.min_shipping_days, 10)
        self.assertEqual(uk.stock_location_id, 41)
        self.assertEqual(uk.shipping_category_id, 46873)
        self.assertEqual(ebay.shipping_category_id, 46862)

    def test_source_filter(self):
        job = load_import_job(
            "em-spree",
            config=_cfg(),
            source_filter="amz_uk",
        )
        self.assertEqual(len(job.sources), 1)
        self.assertEqual(job.sources[0].source_name, "amz_uk")
        self.assertEqual(job.sources[0].stock_location_id, 41)

    def test_cli_override(self):
        job = load_import_job(
            "em-spree",
            config=_cfg(),
            source_filter="amz_ca",
            cli_overrides={"min_shipping_days": 14},
        )
        self.assertEqual(job.sources[0].min_shipping_days, 14)

    def test_missing_section_raises(self):
        with self.assertRaises(ValueError):
            load_import_job("missing", config={})

    def test_vendor_profile_single_products_path(self):
        cfg = _cfg()
        cfg["spree.import.em-spree.v62"] = {
            "merchant_id": "654568556",
            "vendor_id": "62",
            "stock_location_id": "70",
            "shipping_category_id": "46910",
            "min_shipping_days": "10",
            "min_price": "15",
            "daily_upload_limit": "80000",
            "products_path": (
                "/home/Admin/em-tasks/data/aliexpress/"
                "quality_to_upload.multi_variant.from_prepare.jsonl"
            ),
        }
        job = load_import_job(
            "em-spree",
            config=cfg,
            cli_overrides={"vendor_id": "62"},
        )
        self.assertEqual(job.quota_key, "em-spree.v62")
        self.assertEqual(job.profile_section, "spree.import.em-spree.v62")
        self.assertEqual(len(job.sources), 1)
        src = job.sources[0]
        self.assertEqual(src.vendor_id, "62")
        self.assertEqual(src.stock_location_id, 70)
        self.assertEqual(src.shipping_category_id, 46910)
        self.assertTrue(src.products_path.endswith(
            "quality_to_upload.multi_variant.from_prepare.jsonl"
        ))


class DailyUploadQuotaTest(unittest.TestCase):
    def test_records_and_resets_across_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = DailyUploadQuota(
                "em-spree",
                10,
                state_dir=tmp,
                clock_date=date(2026, 7, 23),
            )
            q.record(4)
            self.assertEqual(q.uploaded, 4)
            self.assertEqual(q.remaining, 6)

            q2 = DailyUploadQuota(
                "em-spree",
                10,
                state_dir=tmp,
                clock_date=date(2026, 7, 23),
            )
            self.assertEqual(q2.uploaded, 4)

            q3 = DailyUploadQuota(
                "em-spree",
                10,
                state_dir=tmp,
                clock_date=date(2026, 7, 24),
            )
            self.assertEqual(q3.uploaded, 0)
            self.assertEqual(q3.remaining, 10)

    def test_unlimited_when_limit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = DailyUploadQuota("em-spree", 0, state_dir=tmp)
            self.assertFalse(q.enabled)
            self.assertIsNone(q.remaining)
            self.assertEqual(q.take(100), 100)


class UploadPipelineQuotaTest(unittest.TestCase):
    def test_stops_at_daily_limit(self):
        uploaded_batches: list[list[dict]] = []

        class FakeLookup:
            def find_existing(self, keys):
                return set()

        with tempfile.TemporaryDirectory() as tmp:
            quota = DailyUploadQuota(
                "em-spree",
                3,
                state_dir=tmp,
                clock_date=date(2026, 7, 23),
            )
            report = ImportReport()
            pipeline = UploadPipeline(
                lookup=FakeLookup(),
                report=report,
                upload_batch=lambda buf: uploaded_batches.append(list(buf)),
                quota=quota,
                lookup_batch_size=10,
                upload_batch_size=2,
            )
            for i in range(10):
                pipeline.add(
                    {
                        "source": "AMZ_CA",
                        "source_product_id": f"p{i}",
                        "product_id": f"p{i}",
                    }
                )
            pipeline.finish()

            total = sum(len(b) for b in uploaded_batches)
            self.assertEqual(total, 3)
            self.assertEqual(report.uploaded, 3)
            self.assertGreaterEqual(report.quota_skipped, 1)
            self.assertTrue(pipeline.quota_exhausted)


if __name__ == "__main__":
    unittest.main()
