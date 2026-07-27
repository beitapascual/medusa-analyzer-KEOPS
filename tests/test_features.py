import unittest

from PySide6.QtWidgets import QApplication, QScrollArea, QTabWidget

from medusa_analyzer.frontend.widgets.features import FeaturesWidget


class FeaturesWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_widget_uses_scroll_and_collects_default_selection_recursively(self):
        config = {
            "categories": [
                {
                    "id": "spectral",
                    "title": "Spectral features",
                    "features": [
                        {
                            "id": "psd",
                            "title": "PSD",
                            "checked_by_default": True,
                        },
                        {
                            "id": "nested_group",
                            "title": "Nested group",
                            "features": [
                                {
                                    "id": "nested_feature",
                                    "title": "Nested feature",
                                    "checked_by_default": True,
                                }
                            ],
                        },
                    ],
                    "subcategories": [
                        {
                            "id": "phase",
                            "title": "Phase connectivity",
                            "features": [
                                {
                                    "id": "pli",
                                    "title": "PLI",
                                    "checked_by_default": True,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        state = {}

        widget = FeaturesWidget(config, state, "Features", "Description")
        widget.show()
        self.app.processEvents()

        self.assertIsInstance(widget, QScrollArea)
        self.assertEqual(
            state["selected_features"],
            ["psd", "nested_feature", "pli"],
        )

    def test_selected_feature_params_are_synced_from_widgets(self):
        config = {
            "categories": [
                {
                    "id": "spectral",
                    "title": "Spectral features",
                    "features": [
                        {
                            "id": "psd",
                            "title": "PSD",
                            "checked_by_default": True,
                            "params": [
                                {
                                    "id": "segment_percent",
                                    "title": "Segment (%)",
                                    "type": "int",
                                    "default": 80,
                                    "min": 1,
                                    "max": 100,
                                },
                                {
                                    "id": "window",
                                    "title": "Window",
                                    "type": "combo",
                                    "default": "hamming",
                                    "options": [
                                        {"id": "hamming", "title": "Hamming"},
                                        {"id": "bartlett", "title": "Bartlett"},
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ]
        }
        state = {}

        widget = FeaturesWidget(config, state, "Features", "Description")
        widget.show()
        self.app.processEvents()

        params = widget.param_widgets["psd"]
        self.assertTrue(widget.param_containers["psd"].isVisible())
        params["segment_percent"].setValue(60)
        params["window"].setCurrentIndex(1)
        self.app.processEvents()

        self.assertEqual(
            state["feature_params"]["psd"],
            {"segment_percent": 60, "window": "bartlett"},
        )

        widget.checkboxes["psd"].setChecked(False)
        self.app.processEvents()

        self.assertEqual(state["selected_features"], [])
        self.assertEqual(state["feature_params"], {})
        self.assertFalse(widget.param_containers["psd"].isVisible())
        self.assertEqual(params["segment_percent"].value(), 80)
        self.assertEqual(params["window"].currentData(), "hamming")

        widget.checkboxes["psd"].setChecked(True)
        self.app.processEvents()

        self.assertTrue(widget.param_containers["psd"].isVisible())
        self.assertEqual(
            state["feature_params"]["psd"],
            {"segment_percent": 80, "window": "hamming"},
        )

    def test_derived_params_are_not_rendered_as_editable_controls(self):
        config = {
            "categories": [
                {
                    "id": "spectral",
                    "title": "Spectral features",
                    "features": [
                        {
                            "id": "absolute_band_power",
                            "title": "Absolute band power",
                            "checked_by_default": True,
                            "params": [
                                {
                                    "id": "selected_frequency_bands",
                                    "title": "bands",
                                    "type": "derived",
                                    "source": "preprocessing.selected_frequency_bands",
                                    "format": "bands",
                                    "default": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        state = {}

        widget = FeaturesWidget(config, state, "Features", "Description")
        widget.show()
        self.app.processEvents()

        self.assertEqual(state["selected_features"], ["absolute_band_power"])
        self.assertNotIn("absolute_band_power", widget.param_widgets)
        self.assertNotIn("absolute_band_power", widget.param_containers)
        self.assertEqual(state["feature_params"], {})

    def test_categories_are_rendered_as_tabs_from_config(self):
        config = {
            "categories": [
                {"id": "spectral", "title": "Spectral", "features": []},
                {"id": "statistical", "title": "Statistical", "features": []},
                {"id": "nonlinear", "title": "Nonlinear", "features": []},
            ]
        }
        state = {}

        widget = FeaturesWidget(config, state, "Features", "Description")
        widget.show()
        self.app.processEvents()

        self.assertIsInstance(widget.category_tabs, QTabWidget)
        self.assertEqual(widget.category_tabs.count(), 3)
        self.assertEqual(
            [widget.category_tabs.tabText(index) for index in range(widget.category_tabs.count())],
            ["Spectral", "Statistical", "Nonlinear"],
        )
        self.assertEqual(len(widget.category_panels), 3)
        self.assertEqual(
            [widget.category_tabs.widget(index) for index in range(widget.category_tabs.count())],
            widget.category_panels,
        )
        self.assertEqual(widget.category_panels[-1].minimumHeight(), widget._tab_min_height)
        root_layout = widget.widget().layout()
        self.assertIsNotNone(root_layout.itemAt(root_layout.count() - 1).spacerItem())


if __name__ == "__main__":
    unittest.main()
