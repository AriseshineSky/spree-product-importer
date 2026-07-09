import unittest

from spree_product_importer.product_importer import is_spray_from_product_titles

class SprayCheckTest(unittest.TestCase):
    def test_is_spray_from_product_titles(self):
        product = {
            "title": "Man with Flowers Keratin Super Strong Hair Spray 300ml 5 Pieces Add to Wishlist Share",
        }
        self.assertTrue(is_spray_from_product_titles(product))

if __name__ == "__main__":
    unittest.main()
