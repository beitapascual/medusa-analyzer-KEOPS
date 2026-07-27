import json
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from medusa_analyzer.frontend.experiments.eeg.widgets.eeg_features_widget import (
    EEGFeaturesWidget,
)
from medusa_analyzer.frontend.experiments.eeg.widgets.eeg_preprocessing_widget import (
    EEGPreprocessingWidget,
)


def _eeg_defaults() -> dict:
    defaults_path = (
        Path(__file__).resolve().parents[1]
        / "medusa_analyzer"
        / "frontend"
        / "experiments"
        / "eeg"
        / "defaults.json"
    )
    return json.loads(defaults_path.read_text(encoding="utf-8"))


def _loaded_state() -> dict:
    return {
        "metadata": {
            "n_recordings": 1,
            "subjects": ["01"],
            "sessions": ["01"],
            "datatype": "eeg",
            "task": "test",
            "sampling_frequency": 256.0,
            "n_channels": 1,
            "channel_set": ["C3"],
        },
        "broadband": {"id": "broadband", "title": "Broadband", "enabled": True, "low_cut": 0.1, "high_cut": 128.0},
    }


class EEGFeaturesWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_psd_is_forced_for_other_spectral_features(self):
        defaults = _eeg_defaults()
        state = _loaded_state()

        preprocessing = EEGPreprocessingWidget({}, defaults, state)
        preprocessing.show()
        self.app.processEvents()

        widget = EEGFeaturesWidget({}, defaults, state)
        widget.show()
        self.app.processEvents()

        psd_checkbox = widget.checkboxes["psd"]
        widget.checkboxes["absolute_band_power"].setChecked(True)
        self.app.processEvents()
        self.assertTrue(psd_checkbox.isChecked())
        self.assertFalse(psd_checkbox.isEnabled())

        widget.checkboxes["relative_band_power"].setChecked(True)
        self.app.processEvents()

        widget.checkboxes["absolute_band_power"].setChecked(False)
        self.app.processEvents()
        self.assertFalse(psd_checkbox.isEnabled())

        widget.checkboxes["relative_band_power"].setChecked(False)
        self.app.processEvents()
        self.assertTrue(psd_checkbox.isEnabled())
        self.assertTrue(psd_checkbox.isChecked())

        psd_checkbox.setChecked(False)
        self.app.processEvents()
        self.assertNotIn("psd", state["selected_features"])

    def test_categories_are_rendered_as_tabs_from_defaults(self):
        defaults = _eeg_defaults()
        state = _loaded_state()

        widget = EEGFeaturesWidget({}, defaults, state)
        widget.show()
        self.app.processEvents()

        expected_titles = [
            category["title"]
            for category in defaults["features"]["categories"]
        ]
        self.assertEqual(widget.category_tabs.count(), len(expected_titles))
        self.assertEqual(
            [widget.category_tabs.tabText(index) for index in range(widget.category_tabs.count())],
            expected_titles,
        )

    def test_spectral_band_dependent_features_describe_preprocessing_bands(self):
        defaults = _eeg_defaults()
        spectral_category = next(
            category
            for category in defaults["features"]["categories"]
            if category["id"] == "spectral"
        )
        features = {
            feature["id"]: feature
            for feature in spectral_category["features"]
            if "id" in feature
        }

        self.assertIn(
            "computed in the frequency bands selected during preprocessing",
            features["median_frequency"]["subtitle"],
        )
        self.assertIn(
            "computed in the frequency bands selected during preprocessing",
            features["spectral_entropy"]["subtitle"],
        )

    def test_relative_band_power_uses_preprocessing_selected_bands(self):
        defaults = _eeg_defaults()
        state = _loaded_state()

        preprocessing = EEGPreprocessingWidget({}, defaults, state)
        preprocessing.show()
        self.app.processEvents()

        widget = EEGFeaturesWidget({}, defaults, state)
        widget.show()
        self.app.processEvents()
        widget.checkboxes["absolute_band_power"].setChecked(True)
        widget.checkboxes["relative_band_power"].setChecked(True)
        self.app.processEvents()

        self.assertNotIn("absolute_band_power", state["feature_params"])
        relative_band_power_params = state["feature_params"]["relative_band_power"]
        self.assertEqual(
            relative_band_power_params["selected_frequency_bands"],
            state["preprocessing"]["selected_frequency_bands"][:-1],
        )
        self.assertEqual(list(relative_band_power_params.keys()), ["selected_frequency_bands"])
        self.assertEqual(
            widget._relative_band_power_message.text(),
            "Bandas: Delta (0.5 Hz-4 Hz), Theta (4 Hz-8 Hz), Alpha (8 Hz-13 Hz), Beta (13 Hz-30 Hz), Gamma (30 Hz-45 Hz).",
        )
        self.assertFalse(widget._relative_band_power_table.isVisible())
        self.assertTrue(widget.can_continue())

    def test_relative_band_power_uses_custom_table_when_preprocessing_has_only_broadband(self):
        defaults = _eeg_defaults()
        state = _loaded_state()

        preprocessing = EEGPreprocessingWidget({}, defaults, state)
        preprocessing.show()
        self.app.processEvents()

        for row_widgets in preprocessing.bands.row_widgets:
            row_widgets["enabled"].setChecked(False)
        self.app.processEvents()

        widget = EEGFeaturesWidget({}, defaults, state)
        widget.show()
        self.app.processEvents()
        widget.checkboxes["absolute_band_power"].setChecked(True)
        widget.checkboxes["relative_band_power"].setChecked(True)
        self.app.processEvents()

        self.assertFalse(hasattr(widget, "_relative_band_power_rows"))
        relative_band_power_params = state["feature_params"]["relative_band_power"]
        self.assertTrue(widget._relative_band_power_table.isVisible())
        self.assertEqual(
            relative_band_power_params["selected_frequency_bands"],
            [row for row in widget._relative_band_power_table.rows if row.get("enabled", False)],
        )
        self.assertEqual(list(relative_band_power_params.keys()), ["selected_frequency_bands"])
        self.assertEqual(
            widget._relative_band_power_message.text(),
            "Bandas: Delta (0.5 Hz-4 Hz), Theta (4 Hz-8 Hz), Alpha (8 Hz-13 Hz), Beta (13 Hz-30 Hz), Gamma (30 Hz-45 Hz).",
        )

        for row_widgets in widget._relative_band_power_table.row_widgets[1:]:
            row_widgets["enabled"].setChecked(False)
        self.app.processEvents()

        relative_band_power_params = state["feature_params"]["relative_band_power"]
        self.assertEqual(
            [band["id"] for band in relative_band_power_params["selected_frequency_bands"]],
            ["delta"],
        )
        self.assertEqual(
            widget._relative_band_power_message.text(),
            "Banda: Delta (0.5 Hz-4 Hz).",
        )
        self.assertTrue(widget.can_continue())

        widget._relative_band_power_table.row_widgets[0]["enabled"].setChecked(False)
        self.app.processEvents()

        self.assertFalse(widget.can_continue())
        self.assertIn("select at least one frequency band", widget.error_label.text())

    def test_features_use_metadata_broadband_when_preprocessing_is_missing(self):
        defaults = _eeg_defaults()
        state = _loaded_state()

        widget = EEGFeaturesWidget({}, defaults, state)
        widget.show()
        self.app.processEvents()

        self.assertNotIn("absolute_band_power", state["feature_params"])
        self.assertNotIn("eeg_feature_state", state)

        relative_band_power_params = state["feature_params"]["relative_band_power"]
        self.assertTrue(widget._relative_band_power_table.isVisible())
        self.assertEqual(list(relative_band_power_params.keys()), ["selected_frequency_bands"])
        self.assertEqual(
            widget._relative_band_power_message.text(),
            "Bandas: Delta (0.5 Hz-4 Hz), Theta (4 Hz-8 Hz), Alpha (8 Hz-13 Hz), Beta (13 Hz-30 Hz), Gamma (30 Hz-45 Hz).",
        )
        self.assertTrue(widget.can_continue())

    def test_multiscale_lz_scales_must_follow_bracketed_comma_space_format(self):
        defaults = _eeg_defaults()
        state = _loaded_state()

        preprocessing = EEGPreprocessingWidget({}, defaults, state)
        preprocessing.show()
        self.app.processEvents()

        widget = EEGFeaturesWidget({}, defaults, state)
        widget.show()
        self.app.processEvents()

        widget.checkboxes["multiscale_lempel_ziv_complexity"].setChecked(True)
        self.app.processEvents()

        scales_widget = widget.param_widgets["multiscale_lempel_ziv_complexity"]["scales"]
        scales_widget.setText("[1,3,5]")
        self.app.processEvents()

        self.assertFalse(widget.can_continue())
        self.assertTrue(widget.error_label.isVisible())
        self.assertIn("format [1, 3, 5]", widget.error_label.text())

        scales_widget.setText("[1, 3, 5]")
        self.app.processEvents()

        self.assertTrue(widget.can_continue())
        self.assertFalse(widget.error_label.isVisible())

    def test_psd_overlap_accepts_upper_bound_100(self):
        defaults = _eeg_defaults()
        state = _loaded_state()

        preprocessing = EEGPreprocessingWidget({}, defaults, state)
        preprocessing.show()
        self.app.processEvents()

        widget = EEGFeaturesWidget({}, defaults, state)
        widget.show()
        self.app.processEvents()

        overlap_widget = widget.param_widgets["psd"]["overlap_percent"]
        overlap_widget.setValue(100)
        self.app.processEvents()

        self.assertEqual(state["feature_params"]["psd"]["overlap_percent"], 100)
        self.assertTrue(widget.can_continue())


if __name__ == "__main__":
    unittest.main()
