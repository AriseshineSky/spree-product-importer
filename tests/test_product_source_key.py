import unittest

from spree_product_importer.product_source_lookup import product_source_key

class ProductSourceKeyTest(unittest.TestCase):
    def test_uses_product_id_where_source_product_id_is_missing(self):
        prod = {"source": "Ebay_US", "product_id": "123"}
        self.assertEqual(product_source_key(prod), ("Ebay_US", "123"))

if __name__ == "__main__":
    unittest.main()
