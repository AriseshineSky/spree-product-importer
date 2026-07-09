import unittest

from spree_product_importer.perfume_title_filter import (
    is_perfume_from_product_titles,
    title_contains_perfume_keyword,
)


class PerfumeTitleFilterTest(unittest.TestCase):
    def test_english_perfume(self):
        self.assertTrue(
            title_contains_perfume_keyword("Dior Sauvage Eau de Parfum 100ml")
        )
        self.assertTrue(title_contains_perfume_keyword("Men's Cologne Spray"))

    def test_spanish_portuguese(self):
        self.assertTrue(
            title_contains_perfume_keyword("Perfume importado colonia")
        )
        self.assertTrue(
            title_contains_perfume_keyword("Fragrância feminina colônia")
        )

    def test_turkish(self):
        self.assertTrue(title_contains_perfume_keyword("Kadın parfüm 50ml"))
        self.assertTrue(title_contains_perfume_keyword("Erkek kolonya"))

    def test_japanese(self):
        self.assertTrue(title_contains_perfume_keyword("シャネル 香水 50ml"))
        self.assertTrue(
            title_contains_perfume_keyword("オードパルファム フレグランス")
        )

    def test_chinese(self):
        self.assertTrue(title_contains_perfume_keyword("香奈儿淡香水50ml"))
        self.assertTrue(title_contains_perfume_keyword("男士古龙水"))

    def test_non_perfume(self):
        self.assertFalse(
            title_contains_perfume_keyword("Wireless Bluetooth Headphones")
        )
        self.assertFalse(title_contains_perfume_keyword("Cotton T-Shirt"))

    def test_product_checks_title_and_title_en(self):
        prod = {"title": "普通商品", "title_en": "Chanel Perfume 50ml"}
        self.assertTrue(is_perfume_from_product_titles(prod))

    def test_product_no_perfume(self):
        prod = {"title": "Running Shoes", "title_en": "Nike Air Max"}
        self.assertFalse(is_perfume_from_product_titles(prod))


if __name__ == "__main__":
    unittest.main()
