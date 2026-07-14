import unittest

from spree_product_importer.product_format_filter import (
    product_format_reject_reason,
)


class ProductFormatFilterTest(unittest.TestCase):
    def test_ok_within_limits(self):
        prod = {
            "options": [{"name": "Color"}, {"name": "Size"}],
            "variants": [{"sku": f"v{i}"} for i in range(10)],
        }
        self.assertIsNone(product_format_reject_reason(prod))

    def test_ok_empty_or_missing(self):
        self.assertIsNone(product_format_reject_reason({}))
        self.assertIsNone(
            product_format_reject_reason({"options": None, "variants": None})
        )
        self.assertIsNone(
            product_format_reject_reason({"options": [], "variants": []})
        )

    def test_too_many_options(self):
        prod = {
            "options": [
                {"name": "Color"},
                {"name": "Size"},
                {"name": "Material"},
            ],
            "variants": [{"sku": "v1"}],
        }
        reason = product_format_reject_reason(prod)
        self.assertIsNotNone(reason)
        self.assertIn("TooManyOptions", reason)

    def test_too_many_variants(self):
        prod = {
            "options": [{"name": "Size"}],
            "variants": [{"sku": f"v{i}"} for i in range(11)],
        }
        reason = product_format_reject_reason(prod)
        self.assertIsNotNone(reason)
        self.assertIn("TooManyVariants", reason)

    def test_options_checked_before_variants(self):
        prod = {
            "options": [{"name": f"o{i}"} for i in range(3)],
            "variants": [{"sku": f"v{i}"} for i in range(20)],
        }
        reason = product_format_reject_reason(prod)
        self.assertIn("TooManyOptions", reason)


if __name__ == "__main__":
    unittest.main()
