import unittest

from spree_product_importer.product_format_filter import (
    product_format_reject_reason,
    truncate_variants_inplace,
)


class ProductFormatFilterTest(unittest.TestCase):
    def test_ok_within_limits(self):
        prod = {
            "options": [{"name": "Color"}, {"name": "Size"}],
            "variants": [{"sku": f"v{i}"} for i in range(10)],
        }
        self.assertIsNone(product_format_reject_reason(prod))
        self.assertEqual(truncate_variants_inplace(prod), 0)

    def test_ok_empty_or_missing(self):
        self.assertIsNone(product_format_reject_reason({}))
        self.assertIsNone(
            product_format_reject_reason({"options": None, "variants": None})
        )
        self.assertIsNone(
            product_format_reject_reason({"options": [], "variants": []})
        )

    def test_three_or_more_options_filtered(self):
        for count in (3, 4):
            with self.subTest(count=count):
                prod = {
                    "options": [{"name": f"o{i}"} for i in range(count)],
                    "variants": [{"sku": "v1"}],
                }
                reason = product_format_reject_reason(prod)
                self.assertIsNotNone(reason)
                self.assertIn("TooManyOptions", reason)

    def test_variants_over_limit_are_truncated_not_rejected(self):
        prod = {
            "options": [{"name": "Size"}],
            "variants": [{"sku": f"v{i}"} for i in range(15)],
        }
        self.assertIsNone(product_format_reject_reason(prod))
        dropped = truncate_variants_inplace(prod)
        self.assertEqual(dropped, 5)
        self.assertEqual(len(prod["variants"]), 10)
        self.assertEqual(prod["variants"][0]["sku"], "v0")
        self.assertEqual(prod["variants"][-1]["sku"], "v9")

    def test_options_still_reject_even_with_many_variants(self):
        prod = {
            "options": [{"name": f"o{i}"} for i in range(3)],
            "variants": [{"sku": f"v{i}"} for i in range(20)],
        }
        reason = product_format_reject_reason(prod)
        self.assertIn("TooManyOptions", reason)

    def test_non_ebay_requires_empty_shipping_days(self):
        for source in ("AMZ_US", "AMZ_UK", "www_books_com_tw"):
            with self.subTest(source=source):
                reason = product_format_reject_reason(
                    {
                        "source": source,
                        "shipping_days_min": 3,
                        "shipping_days_max": None,
                    }
                )
                self.assertIsNotNone(reason)
                self.assertIn("ShippingDaysNotEmpty", reason)
                self.assertIn("shipping_days_min", reason)

                reason = product_format_reject_reason(
                    {
                        "source": source,
                        "shipping_days_min": None,
                        "shipping_days_max": 10,
                    }
                )
                self.assertIsNotNone(reason)
                self.assertIn("shipping_days_max", reason)

    def test_non_ebay_ok_when_shipping_days_empty(self):
        for prod in (
            {"source": "AMZ_US"},
            {
                "source": "AMZ_US",
                "shipping_days_min": None,
                "shipping_days_max": None,
            },
            {
                "source": "AMZ_US",
                "shipping_days_min": "",
                "shipping_days_max": "",
            },
        ):
            with self.subTest(prod=prod):
                self.assertIsNone(product_format_reject_reason(prod))

    def test_ebay_us_allows_shipping_days(self):
        for source in ("Ebay_US", "ebay_us", "EBAY_US"):
            with self.subTest(source=source):
                self.assertIsNone(
                    product_format_reject_reason(
                        {
                            "source": source,
                            "shipping_days_min": 2,
                            "shipping_days_max": 5,
                        }
                    )
                )


if __name__ == "__main__":
    unittest.main()
