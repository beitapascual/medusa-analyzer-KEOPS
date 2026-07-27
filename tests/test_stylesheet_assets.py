import unittest

from medusa_analyzer.frontend.app import _load_stylesheet


class StylesheetAssetTests(unittest.TestCase):
    def test_stylesheet_resolves_style_dir_asset_urls(self):
        stylesheet = _load_stylesheet()

        self.assertNotIn("${STYLE_DIR}", stylesheet)
        self.assertIn("spin_up.xpm", stylesheet)
        self.assertIn("spin_down.xpm", stylesheet)
        self.assertIn("D:/", stylesheet)


if __name__ == "__main__":
    unittest.main()
