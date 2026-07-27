import json
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel

from medusa_analyzer.frontend.experiments import (
    _resolve_widget_class,
    discover_experiments,
)
from medusa_analyzer.frontend.experiments.eeg.widgets.frequency_bands_table import (
    EEGFrequencyBandsTable,
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
        "broadband": {"id": "broadband", "title": "Broadband", "enabled": True,
            "low_cut": 0.1, "high_cut": 128.0},
    }


class EEGPreprocessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_experiment_definition_resolves_preprocessing_widget(self):
        definition = next(
            experiment
            for experiment in discover_experiments()
            if experiment.id == "eeg"
        )
        preprocessing_step = next(
            step
            for step in definition.info["workflow"]
            if step["id"] == "preprocessing"
        )

        widget_class = _resolve_widget_class(definition, preprocessing_step["widget"])

        self.assertIs(widget_class, EEGPreprocessingWidget)

    def test_widget_syncs_state_and_filter_plots(self):
        state = _loaded_state()

        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)
        widget.resize(1440, 960)
        widget.show()
        self.app.processEvents()

        self.assertIs(widget.state["preprocessing"], state["preprocessing"])
        self.assertIsInstance(widget.bands, EEGFrequencyBandsTable)
        self.assertFalse(hasattr(widget, "frequency_bands"))
        self.assertNotIn("frequency_bands", state["preprocessing"])
        self.assertTrue(widget.can_continue())
        self.assertTrue(state["preprocessing"]["car"])
        self.assertEqual(
            set(state["preprocessing"]),
            {"car", "filters", "selected_frequency_bands"},
        )
        expected_filter_keys = {
            "enabled",
            "low_cut",
            "high_cut",
            "filter_type",
            "filter_design",
            "order",
            "window",
        }
        for filter_state in state["preprocessing"]["filters"].values():
            self.assertEqual(set(filter_state), expected_filter_keys)
        self.assertEqual(state["preprocessing"]["filters"]["notch"]["filter_type"], "bandstop")
        self.assertEqual(state["preprocessing"]["filters"]["bandpass"]["filter_type"], "bandpass")
        self.assertEqual(state["preprocessing"]["filters"]["bandpass"]["filter_design"], "fir")
        self.assertEqual(state["preprocessing"]["filters"]["bandpass"]["order"], 1000)
        self.assertEqual(state["preprocessing"]["filters"]["bandpass"]["window"], "hamming")

        design_combo = widget.filters["bandpass"].kind
        design_combo.setCurrentIndex(design_combo.findData("iir"))
        self.app.processEvents()
        bandpass_filter = state["preprocessing"]["filters"]["bandpass"]
        self.assertEqual(set(bandpass_filter), expected_filter_keys)
        self.assertEqual(bandpass_filter["filter_type"], "bandpass")
        self.assertEqual(bandpass_filter["filter_design"], "iir")
        self.assertEqual(bandpass_filter["order"], 4)
        self.assertEqual(bandpass_filter["window"], "butter")

        design_combo.setCurrentIndex(design_combo.findData("fir"))
        self.app.processEvents()
        bandpass_filter = state["preprocessing"]["filters"]["bandpass"]
        self.assertEqual(bandpass_filter["filter_design"], "fir")
        self.assertEqual(bandpass_filter["order"], 1000)
        self.assertEqual(bandpass_filter["window"], "hamming")
        self.assertEqual(state["broadband"]["id"], "broadband")
        self.assertEqual(state["broadband"]["low_cut"], 0.5)
        self.assertEqual(state["broadband"]["high_cut"], 60.0)
        self.assertEqual(
            len(state["preprocessing"]["selected_frequency_bands"]),
            len(widget.bands.rows) + 1,
        )
        self.assertEqual(
            state["preprocessing"]["selected_frequency_bands"][-1]["id"],
            "broadband",
        )
        self.assertEqual(widget.car_checkbox.text(), "Apply common average reference")
        self.assertTrue(
            any(
                label.text() == "CAR" and label.objectName() == "panelTitle"
                for label in widget.findChildren(QLabel)
            )
        )
        self.assertIsNotNone(widget.filter_plots["notch"].response)
        self.assertLess(widget.filter_plots["notch"].response.frequencies[-1], 128.0)

        low_spin = widget.bands.row_widgets[0]["low_cut"]
        high_spin = widget.bands.row_widgets[0]["high_cut"]
        self.assertEqual(low_spin.minimum(), 0.0)
        self.assertEqual(high_spin.maximum(), 10000.0)

        high_spin.setValue(200.0)
        self.app.processEvents()
        self.assertEqual(high_spin.value(), 200.0)
        self.assertFalse(widget.bands.is_valid())
        self.assertTrue(
            any("60 Hz" in error for error in widget.bands.validation_errors())
        )
        high_spin.setValue(45.0)
        self.app.processEvents()
        self.assertTrue(widget.bands.is_valid())

        widget.car_checkbox.setChecked(False)
        self.app.processEvents()
        self.assertFalse(state["preprocessing"]["car"])

        widget.filters["bandpass"].high.setValue(200.0)
        self.app.processEvents()
        self.assertIsNone(widget.filter_plots["bandpass"].response)
        self.assertIn("128 Hz", widget.filter_plots["bandpass"].empty_message)
        self.assertEqual(widget.filters["bandpass"].high.maximum(), 128.0)
        self.assertTrue(widget.filters["bandpass"].error_label.isVisible())
        self.assertIn("128 Hz", widget.filters["bandpass"].error_label.text())
        self.assertFalse(widget.can_continue())
        self.assertEqual(high_spin.maximum(), 10000.0)
        low_spin.setValue(0.0)
        self.app.processEvents()
        self.assertEqual(low_spin.value(), 0.0)
        self.assertEqual(widget.bands.rows[0]["low_cut"], 0.0)
        self.assertFalse(widget.bands.is_valid())
        self.assertTrue(
            any("0.5 Hz" in error for error in widget.bands.validation_errors())
        )
        low_spin.setValue(0.5)
        self.app.processEvents()

        high_spin.setValue(200.0)
        self.app.processEvents()
        self.assertEqual(high_spin.value(), 200.0)
        self.assertEqual(
            widget.bands.rows[0]["high_cut"],
            200.0,
        )
        self.assertFalse(widget.bands.is_valid())
        self.assertTrue(
            any("60 Hz" in error for error in widget.bands.validation_errors())
        )

        high_spin.setValue(45.0)
        low_spin.setValue(1.0)
        self.app.processEvents()
        self.assertEqual(widget.bands.rows[0]["low_cut"], 1.0)
        self.assertTrue(widget.bands.is_valid())

        title_edit = widget.bands.row_widgets[0]["title"]
        title_edit.setText("alpha band")
        self.app.processEvents()
        self.assertFalse(widget.bands.is_valid())
        self.assertFalse(widget.can_continue())
        self.assertTrue(
            any(
                "must not contain spaces" in error
                for error in widget.bands.validation_errors()
            )
        )

        widget.filters["bandpass"].enabled.setChecked(False)
        title_edit.setText("Alpha")
        self.app.processEvents()
        self.assertFalse(widget.filters["bandpass"].error_label.isVisible())
        self.assertEqual(high_spin.maximum(), 10000.0)
        high_spin.setValue(200.0)
        self.app.processEvents()
        self.assertEqual(high_spin.value(), 200.0)
        self.assertEqual(
            widget.bands.rows[0]["high_cut"],
            200.0,
        )
        self.assertFalse(widget.bands.is_valid())
        self.assertTrue(
            any("60 Hz" in error for error in widget.bands.validation_errors())
        )

    def test_widget_restores_saved_preprocessing_state_with_current_schema(self):
        state = _loaded_state()
        state["preprocessing"] = {
            "car": False,
            "filters": {
                "bandpass": {
                    "enabled": True,
                    "filter_type": "bandpass",
                    "filter_design": "iir",
                    "low_cut": 2.0,
                    "high_cut": 30.0,
                    "order": 5,
                    "window": "bessel",
                }
            },
        }

        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        self.assertFalse(state["preprocessing"]["car"])
        bandpass_state = state["preprocessing"]["filters"]["bandpass"]
        self.assertEqual(
            bandpass_state,
            {
                "enabled": True,
                "low_cut": 2.0,
                "high_cut": 30.0,
                "filter_type": "bandpass",
                "filter_design": "iir",
                "order": 5,
                "window": "bessel",
            },
        )

    def test_widget_blocks_without_loaded_recordings(self):
        state = {}
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        self.assertFalse(widget.can_continue())
        self.assertFalse(widget.car_checkbox.isEnabled())
        self.assertFalse(widget.filters["notch"].isEnabled())
        self.assertFalse(widget.filters["bandpass"].isEnabled())
        self.assertFalse(widget.bands.isEnabled())
        self.assertIsNone(widget.filter_plots["notch"].response)
        self.assertEqual(
            widget.filter_plots["notch"].empty_message,
            "Load recordings first to preview the filter response.",
        )
        self.assertIsNone(widget.filter_plots["bandpass"].response)

    def test_notch_must_stay_within_active_bandpass(self):
        state = _loaded_state()
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        widget.filters["bandpass"].low.setValue(1.0)
        widget.filters["bandpass"].high.setValue(50.0)
        self.app.processEvents()

        self.assertTrue(widget.filters["notch"].error_label.isVisible())
        self.assertIn("1-50 Hz", widget.filters["notch"].error_label.text())
        self.assertIsNone(widget.filter_plots["notch"].response)
        self.assertIn("1-50 Hz", widget.filter_plots["notch"].empty_message)
        self.assertFalse(widget.can_continue())

        widget.filters["notch"].low.setValue(45.0)
        widget.filters["notch"].high.setValue(49.0)
        widget.bands.row_widgets[0]["low_cut"].setValue(1.0)
        self.app.processEvents()

        self.assertFalse(widget.filters["notch"].error_label.isVisible())
        self.assertIsNotNone(widget.filter_plots["notch"].response)
        self.assertTrue(widget.can_continue())

    def test_narrowing_bandpass_invalidates_out_of_range_frequency_bands(self):
        state = _loaded_state()
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        low_spin = widget.bands.row_widgets[0]["low_cut"]
        high_spin = widget.bands.row_widgets[0]["high_cut"]

        low_spin.setValue(1.0)
        high_spin.setValue(55.0)
        self.app.processEvents()

        self.assertTrue(widget.bands.is_valid())

        widget.filters["bandpass"].low.setValue(1.0)
        widget.filters["bandpass"].high.setValue(50.0)
        self.app.processEvents()

        self.assertFalse(widget.bands.is_valid())
        self.assertTrue(
            any("50 Hz" in error for error in widget.bands.validation_errors())
        )
        self.assertFalse(widget.can_continue())

    def test_preprocessing_tracks_broadband_only_when_no_band_is_enabled(self):
        state = _loaded_state()
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        for row_widgets in widget.bands.row_widgets:
            row_widgets["enabled"].setChecked(False)
        self.app.processEvents()

        self.assertEqual(
            state["preprocessing"]["selected_frequency_bands"],
            [state["broadband"]],
        )

    def test_preprocessing_broadband_follows_active_bandpass_range(self):
        state = _loaded_state()
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        widget.filters["bandpass"].low.setValue(1.0)
        widget.filters["bandpass"].high.setValue(50.0)
        self.app.processEvents()

        self.assertEqual(
            state["broadband"],
            {
                "id": "broadband",
                "title": "Broadband",
                "enabled": True,
                "low_cut": 1.0,
                "high_cut": 50.0,
            },
        )

    def test_bandpass_control_bounds_do_not_follow_effective_broadband(self):
        state = _loaded_state()
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        bandpass = widget.filters["bandpass"]
        source_low = bandpass.low.minimum()
        source_high = bandpass.high.maximum()

        bandpass.low.setValue(40.0)
        self.app.processEvents()

        self.assertEqual(state["broadband"]["low_cut"], 40.0)
        self.assertEqual(bandpass.low.minimum(), source_low)

        bandpass.low.setValue(0.5)
        self.app.processEvents()

        self.assertEqual(bandpass.low.value(), 0.5)
        self.assertEqual(state["broadband"]["low_cut"], 0.5)

        bandpass.high.setValue(50.0)
        self.app.processEvents()

        self.assertEqual(state["broadband"]["high_cut"], 50.0)
        self.assertEqual(bandpass.high.maximum(), source_high)

        bandpass.high.setValue(60.0)
        self.app.processEvents()

        self.assertEqual(bandpass.high.value(), 60.0)
        self.assertEqual(state["broadband"]["high_cut"], 60.0)

    def test_frequency_bands_table_can_add_new_row(self):
        state = _loaded_state()
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)

        initial_count = len(widget.bands.rows)
        widget.bands.add_row_button.click()
        self.app.processEvents()

        self.assertEqual(len(widget.bands.rows), initial_count + 1)
        self.assertNotIn("frequency_bands", state["preprocessing"])
        new_row = widget.bands.rows[-1]
        self.assertEqual(new_row["id"], "")
        self.assertEqual(new_row["title"], "Band")
        self.assertEqual(new_row["low_cut"], 0.5)
        self.assertEqual(new_row["high_cut"], 1.0)
        self.assertTrue(widget.bands.is_valid())

    def test_frequency_bands_table_reorders_rows(self):
        state = _loaded_state()
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)

        original_titles = [
            row["title"] for row in widget.bands.rows
        ]
        widget.bands.move_row(0, 3)
        self.app.processEvents()

        reordered_titles = [
            row["title"] for row in widget.bands.rows
        ]
        self.assertEqual(
            reordered_titles[:3],
            [original_titles[1], original_titles[2], original_titles[0]],
        )

    def test_frequency_bands_table_can_reset_to_defaults(self):
        state = _loaded_state()
        widget = EEGPreprocessingWidget({}, _eeg_defaults(), state)

        defaults = _eeg_defaults()["preprocessing"]["bands"]["available"]
        widget.bands.add_row_button.click()
        widget.bands.move_row(0, 3)
        widget.bands.row_widgets[0]["title"].setText("custom")
        widget.bands.row_widgets[0]["low_cut"].setValue(9.5)
        self.app.processEvents()

        widget.bands.reset_button.click()
        self.app.processEvents()

        rows = widget.bands.rows
        self.assertNotIn("frequency_bands", state["preprocessing"])
        self.assertEqual(len(rows), len(defaults))
        self.assertEqual(
            [row["title"] for row in rows],
            [band["title"] for band in defaults],
        )
        self.assertEqual(rows[0]["enabled"], defaults[0]["enabled"])
        self.assertEqual(rows[0]["low_cut"], defaults[0]["low_cut"])
        self.assertEqual(rows[0]["high_cut"], defaults[0]["high_cut"])
        self.assertTrue(widget.bands.is_valid())


if __name__ == "__main__":
    unittest.main()
