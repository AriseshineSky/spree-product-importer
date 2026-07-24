import unittest
from unittest.mock import patch

from spree_product_importer.description_prepare import (
    prepare_product_description,
)


class DescriptionPrepareTest(unittest.TestCase):
    def test_non_ebay_unchanged(self):
        prod = {
            "source": "AMZ_US",
            "description": '<p>keep <a href="x">link</a></p>',
        }
        prepare_product_description(prod)
        self.assertIn("<a href", prod["description"])

    def test_ebay_calls_format_ebay_description(self):
        prod = {
            "source": "Ebay_US",
            "description": '<div>ebay <a href="x">click</a> text</div>',
            "title": "Fallback Title",
        }

        def _fake_format(product):
            product["description"] = "<div> cleaned </div>"
            return product

        with patch(
            "spree_product_importer.description_prepare."
            "_format_ebay_description",
            side_effect=_fake_format,
        ) as mocked:
            prepare_product_description(prod)
            mocked.assert_called_once_with(prod)
        self.assertEqual(prod["description"], "<div> cleaned </div>")


if __name__ == "__main__":
    unittest.main()
