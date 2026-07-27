import json
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QLabel, QPushButton, QWidget

from medusa_analyzer.frontend.experiments.eeg.widgets.eeg_segmentation_widget import (
    EEGSegmentationWidget,
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
            "sampling_frequency": 250.0,
            "n_channels": 2,
            "channel_set": ["C3", "C4"],
        },
        "selected_bids_group": "group-1",
        "duration_events": ["full_recording", "trial"],
        "instant_events": ["stimulus"],
    }


def _loaded_state_with_events(duration_events: list[str], instant_events: list[str]) -> dict:
    state = _loaded_state()
    state["duration_events"] = duration_events
    state["instant_events"] = instant_events
    return state


def _has_ancestor_with_role(widget, role: str) -> bool:
    parent = widget.parent()
    while parent is not None:
        if hasattr(parent, "property") and parent.property("role") == role:
            return True
        parent = parent.parent()
    return False


class EEGSegmentationWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_nested_mode_uses_single_child_type_without_dual_parameter_selectors(self):
        state = _loaded_state_with_events(["full_recording", "trial"], ["stimulus", "response"])
        widget = EEGSegmentationWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        self.assertFalse(hasattr(widget, "_epoch_parameters"))
        self.assertFalse(hasattr(widget, "_normalization_parameters"))
        self.assertEqual(state["segmentation"]["epoch_parameters"], {"duration": {}, "instant": {}})
        self.assertEqual(state["segmentation"]["normalization"], {"duration": {}, "instant": {}})
        self.assertEqual(widget.independent_mode_button.property("role"), "segmentation-mode-button")
        self.assertEqual(widget.epoch_duration_target_button.property("role"), "segmentation-target-button")
        self.assertTrue(widget.nested_mode_button.isEnabled())

        widget.nested_mode_button.click()
        state["segmentation"]["event_groups"] = [
            {
                "base_event": "trial",
                "duration_events": [],
                "instant_events": ["stimulus"],
            }
        ]
        widget._sync()
        self.app.processEvents()

        self.assertFalse(widget.epoch_target_panel.isVisible())
        self.assertFalse(widget.normalization_target_panel.isVisible())
        add_instant_buttons = [
            button
            for button in widget.findChildren(QPushButton)
            if button.text() == "+ Add instant event"
        ]
        add_duration_buttons = [
            button
            for button in widget.findChildren(QPushButton)
            if button.text() == "+ Add duration event"
        ]
        self.assertTrue(add_duration_buttons)
        self.assertEqual(
            add_duration_buttons[0].property("role"),
            "segmentation-duration-action",
        )
        self.assertFalse(_has_ancestor_with_role(add_duration_buttons[0], "nested-base-event"))
        self.assertFalse(add_duration_buttons[0].isEnabled())
        self.assertIn("already using instant", add_duration_buttons[0].toolTip())
        self.assertTrue(add_instant_buttons)
        self.assertEqual(
            add_instant_buttons[0].property("role"),
            "segmentation-instant-action",
        )
        self.assertFalse(_has_ancestor_with_role(add_instant_buttons[0], "nested-base-event"))
        self.assertTrue(add_instant_buttons[0].isEnabled())
        self.assertTrue(
            any(
                label.objectName() == "nestedBaseEventTitle"
                and label.text() == "trial"
                for label in widget.findChildren(QLabel)
            )
        )
        self.assertFalse(widget.summary_panel.isVisible())
        self.assertTrue(
            any(
                frame.property("role") == "nested-base-event"
                for frame in widget.findChildren(QFrame)
            )
        )
        self.assertTrue(
            any(
                child.property("role") == "nested-group-editor"
                for child in widget.findChildren(QWidget)
            )
        )
        self.assertTrue(
            any(
                frame.property("role") == "nested-contained-events"
                for frame in widget.findChildren(QFrame)
            )
        )
        self.assertTrue(
            any(
                frame.objectName() == "summaryInstantChip"
                and frame.property("compact") == "true"
                and _has_ancestor_with_role(frame, "nested-contained-events")
                and _has_ancestor_with_role(frame, "nested-base-event")
                for frame in widget.findChildren(QFrame)
            )
        )
        self.assertFalse(any(frame.objectName() == "summaryDurationChip" for frame in widget.findChildren(QFrame)))

        self.assertTrue(widget.epoch_start.isVisible())
        self.assertFalse(widget.duration_epoch_length.isVisible())
        widget.epoch_start.setValue(-120)
        widget.epoch_end.setValue(380)
        widget.stride.setValue(0)
        widget.average_epochs.setChecked(False)
        self.app.processEvents()

        segmentation = state["segmentation"]
        self.assertEqual(segmentation["segmentation_mode"], "nested")
        self.assertNotIn("selection_mode", segmentation)
        self.assertNotIn("selected_duration_events", segmentation)
        self.assertNotIn("selected_instant_events", segmentation)
        self.assertNotIn("nested_epoch", segmentation)
        self.assertNotIn("nested_normalization", segmentation)
        self.assertNotIn("nested_groups", segmentation)
        self.assertNotIn("epoch_window_ms", segmentation)
        self.assertNotIn("duration_epoch_length_ms", segmentation)
        self.assertNotIn("stride_percent", segmentation)
        self.assertNotIn("average_epochs", segmentation)
        self.assertEqual(segmentation["epoch_parameters"]["duration"], {})
        self.assertEqual(
            segmentation["epoch_parameters"]["instant"]["epoch_window_ms"],
            {"start": -120, "end": 380},
        )
        self.assertEqual(segmentation["epoch_parameters"]["instant"]["stride_percent"], 0)
        self.assertFalse(segmentation["epoch_parameters"]["instant"]["average_epochs"])

        widget.normalization_enabled.setChecked(True)
        widget.normalization_mode.setCurrentIndex(widget.normalization_mode.findData("mean_std"))
        widget.baseline_start.setValue(-50)
        widget.baseline_end.setValue(0)
        self.app.processEvents()
        self.assertTrue(widget.baseline_start.isVisible())

        segmentation = state["segmentation"]
        self.assertEqual(segmentation["normalization"]["duration"], {})
        self.assertEqual(
            segmentation["normalization"]["instant"],
            {
                "enabled": True,
                "mode": "mean_std",
                "baseline_window_ms": {"start": -50, "end": 0},
            },
        )
        self.assertEqual(widget.normalization_mode.itemText(widget.normalization_mode.findData("mean_std")), "Z-score")
        self.assertTrue(widget.can_continue())

    def test_segmentation_widget_has_no_inline_stylesheet(self):
        widget_path = (
            Path(__file__).resolve().parents[1]
            / "medusa_analyzer"
            / "frontend"
            / "experiments"
            / "eeg"
            / "widgets"
            / "eeg_segmentation_widget.py"
        )
        self.assertNotIn("setStyleSheet", widget_path.read_text(encoding="utf-8"))
        segmentation_defaults = _eeg_defaults()["segmentation"]
        self.assertNotIn("selection_mode", segmentation_defaults)
        self.assertNotIn("selected_duration_events", segmentation_defaults)
        self.assertNotIn("selected_instant_events", segmentation_defaults)
        self.assertNotIn("nested_groups", segmentation_defaults)
        self.assertNotIn("nested_epoch", segmentation_defaults)
        self.assertNotIn("nested_normalization", segmentation_defaults)
        self.assertNotIn("epoch_window_ms", segmentation_defaults)
        self.assertNotIn("duration_epoch_length_ms", segmentation_defaults)
        self.assertNotIn("stride_percent", segmentation_defaults)
        self.assertNotIn("average_epochs", segmentation_defaults)

    def test_independent_mode_stores_selection_as_event_group(self):
        state = _loaded_state()
        widget = EEGSegmentationWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        widget.duration_events_list.item(0).setSelected(True)
        self.app.processEvents()

        segmentation = state["segmentation"]
        self.assertEqual(segmentation["segmentation_mode"], "independent")
        self.assertEqual(segmentation["segmentation_strategy"], "window")
        self.assertTrue(widget.strategy_panel.isVisible())
        self.assertTrue(widget.window_strategy_button.isVisible())
        self.assertTrue(widget.window_strategy_button.isChecked())
        self.assertTrue(widget.window_segmentation_widget.isVisible())
        self.assertFalse(widget.epoch_start.isVisible())
        self.assertTrue(widget.duration_epoch_length.isVisible())
        self.assertEqual(
            segmentation["event_groups"],
            [{
                "base_event": None,
                "duration_events": ["full_recording"],
                "instant_events": [],
            }],
        )
        self.assertNotIn("selected_duration_events", segmentation)
        self.assertNotIn("selected_instant_events", segmentation)
        self.assertNotIn("nested_groups", segmentation)

    def test_duration_strategy_switches_controls_and_window_preview_stays_in_sync(self):
        state = _loaded_state()
        widget = EEGSegmentationWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        widget.duration_events_list.item(0).setSelected(True)
        self.app.processEvents()

        widget.duration_epoch_length.setValue(1400)
        widget.stride.setValue(35)
        self.app.processEvents()
        self.assertEqual(widget.window_segmentation_widget.epoch_slider.value(), 1400)
        self.assertEqual(widget.window_segmentation_widget.overlap_slider.value(), 35)

        widget.window_segmentation_widget.epoch_slider.setValue(1800)
        widget.window_segmentation_widget.overlap_slider.setValue(55)
        self.app.processEvents()
        self.assertEqual(widget.duration_epoch_length.value(), 1800)
        self.assertEqual(widget.stride.value(), 55)
        self.assertEqual(state["segmentation"]["epoch_parameters"]["duration"]["duration_epoch_length_ms"], 1800)
        self.assertEqual(state["segmentation"]["epoch_parameters"]["duration"]["stride_percent"], 55)

        widget.onset_strategy_button.click()
        self.app.processEvents()
        self.assertEqual(state["segmentation"]["segmentation_strategy"], "onset")
        self.assertFalse(widget.window_segmentation_widget.isVisible())
        self.assertTrue(widget.onset_segmentation_widget.isVisible())
        self.assertTrue(widget.epoch_start.isVisible())
        self.assertFalse(widget.duration_epoch_length.isVisible())

        widget.epoch_start.setValue(-200)
        widget.epoch_end.setValue(600)
        widget.normalization_enabled.setChecked(True)
        widget.baseline_start.setValue(-100)
        widget.baseline_end.setValue(0)
        self.app.processEvents()

        self.assertEqual(
            state["segmentation"]["epoch_parameters"]["duration"]["epoch_window_ms"],
            {"start": -200, "end": 600},
        )
        self.assertEqual(
            state["segmentation"]["normalization"]["duration"]["baseline_window_ms"],
            {"start": -100, "end": 0},
        )
        self.assertEqual(widget.onset_segmentation_widget.window_start_slider.value(), -200)
        self.assertEqual(widget.onset_segmentation_widget.window_end_slider.value(), 600)
        self.assertEqual(widget.onset_segmentation_widget.baseline_start_slider.value(), -100)
        self.assertEqual(widget.onset_segmentation_widget.baseline_end_slider.value(), 0)

        widget.onset_segmentation_widget.window_start_slider.setValue(-150)
        widget.onset_segmentation_widget.window_end_slider.setValue(500)
        widget.onset_segmentation_widget.baseline_start_slider.setValue(-125)
        widget.onset_segmentation_widget.baseline_end_slider.setValue(-25)
        self.app.processEvents()

        self.assertEqual(widget.epoch_start.value(), -150)
        self.assertEqual(widget.epoch_end.value(), 500)
        self.assertEqual(widget.baseline_start.value(), -125)
        self.assertEqual(widget.baseline_end.value(), -25)
        self.assertEqual(
            state["segmentation"]["epoch_parameters"]["duration"]["epoch_window_ms"],
            {"start": -150, "end": 500},
        )
        self.assertEqual(
            state["segmentation"]["normalization"]["duration"]["baseline_window_ms"],
            {"start": -125, "end": -25},
        )
        self.assertTrue(widget.baseline_start.isVisible())
        self.assertTrue(widget.can_continue())

    def test_instant_events_force_onset_strategy_without_window_preview(self):
        state = _loaded_state()
        widget = EEGSegmentationWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        widget.instant_events_list.item(0).setSelected(True)
        self.app.processEvents()

        self.assertEqual(state["segmentation"]["segmentation_strategy"], "onset")
        self.assertFalse(widget.window_strategy_button.isVisible())
        self.assertTrue(widget.onset_strategy_button.isChecked())
        self.assertFalse(widget.window_segmentation_widget.isVisible())
        self.assertTrue(widget.onset_segmentation_widget.isVisible())
        self.assertTrue(widget.epoch_start.isVisible())
        self.assertFalse(widget.duration_epoch_length.isVisible())

    def test_nested_mode_is_unavailable_only_for_single_duration_without_instant_events(self):
        invalid_state = _loaded_state_with_events(["full_recording"], [])
        invalid_widget = EEGSegmentationWidget({}, _eeg_defaults(), invalid_state)
        invalid_widget.show()
        self.app.processEvents()
        self.assertFalse(invalid_widget.nested_mode_button.isEnabled())

        instant_state = _loaded_state_with_events(["full_recording"], ["stimulus"])
        instant_widget = EEGSegmentationWidget({}, _eeg_defaults(), instant_state)
        instant_widget.show()
        self.app.processEvents()
        self.assertTrue(instant_widget.nested_mode_button.isEnabled())

        duration_state = _loaded_state_with_events(["full_recording", "trial"], [])
        duration_widget = EEGSegmentationWidget({}, _eeg_defaults(), duration_state)
        duration_widget.show()
        self.app.processEvents()
        self.assertTrue(duration_widget.nested_mode_button.isEnabled())

    def test_nested_add_buttons_follow_global_child_type_lock(self):
        state = _loaded_state_with_events(["full_recording", "trial"], ["stimulus", "response"])
        widget = EEGSegmentationWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        widget.nested_mode_button.click()
        state["segmentation"]["event_groups"] = [
            {
                "base_event": "full_recording",
                "duration_events": [],
                "instant_events": ["stimulus"],
            },
            {
                "base_event": "trial",
                "duration_events": [],
                "instant_events": [],
            }
        ]
        widget._sync()
        self.app.processEvents()

        add_duration_buttons = [
            button
            for button in widget.findChildren(QPushButton)
            if button.text() == "+ Add duration event"
        ]
        add_instant_buttons = [
            button
            for button in widget.findChildren(QPushButton)
            if button.text() == "+ Add instant event"
        ]

        self.assertFalse(widget.add_base_event_button.isEnabled())
        self.assertIn("already configured", widget.add_base_event_button.toolTip())
        self.assertTrue(add_duration_buttons)
        self.assertTrue(all(button.property("role") == "segmentation-duration-action" for button in add_duration_buttons))
        self.assertTrue(all(not button.isEnabled() for button in add_duration_buttons))
        self.assertTrue(all("already using instant" in button.toolTip() for button in add_duration_buttons))
        self.assertTrue(add_instant_buttons)
        self.assertTrue(all(button.property("role") == "segmentation-instant-action" for button in add_instant_buttons))
        self.assertTrue(all(button.isEnabled() for button in add_instant_buttons))

        widget._add_nested_events("full_recording", "duration")
        self.assertEqual(state["segmentation"]["event_groups"][0]["duration_events"], [])

    def test_nested_chip_close_button_removes_only_that_nested_event(self):
        state = _loaded_state_with_events(["full_recording", "trial"], ["stimulus", "response"])
        widget = EEGSegmentationWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        widget.nested_mode_button.click()
        state["segmentation"]["event_groups"] = [
            {
                "base_event": "trial",
                "duration_events": [],
                "instant_events": ["stimulus", "response"],
            }
        ]
        widget._sync()
        self.app.processEvents()

        nested_chips = [
            frame
            for frame in widget.findChildren(QFrame)
            if frame.objectName() == "summaryInstantChip"
            and frame.property("compact") == "true"
            and _has_ancestor_with_role(frame, "nested-contained-events")
        ]
        self.assertEqual(len(nested_chips), 2)
        self.assertTrue(all(isinstance(chip.layout(), QGridLayout) for chip in nested_chips))

        stimulus_remove_button = next(
            button
            for button in widget.findChildren(QPushButton)
            if button.property("role") == "chip-remove-button"
            and button.toolTip() == "Remove stimulus"
        )
        stimulus_remove_button.click()
        self.app.processEvents()

        self.assertEqual(
            state["segmentation"]["event_groups"],
            [
                {
                    "base_event": "trial",
                    "duration_events": [],
                    "instant_events": ["response"],
                }
            ],
        )

    def test_nested_parameter_selectors_stay_hidden_and_targets_follow_child_type(self):
        duration_events = [f"base_{index}" for index in range(7)] + [f"duration_child_{index}" for index in range(7)]
        duration_state = _loaded_state_with_events(duration_events, [])
        duration_widget = EEGSegmentationWidget({}, _eeg_defaults(), duration_state)
        duration_widget.show()
        self.app.processEvents()

        duration_widget.nested_mode_button.click()
        duration_widget._epoch_target = "instant"
        duration_widget._normalization_target = "instant"
        duration_state["segmentation"]["event_groups"] = [
            {
                "base_event": f"base_{index}",
                "duration_events": [f"duration_child_{index}"],
                "instant_events": [],
            }
            for index in range(7)
        ]
        duration_widget._sync()
        self.app.processEvents()

        self.assertFalse(duration_widget.epoch_target_panel.isVisible())
        self.assertFalse(duration_widget.normalization_target_panel.isVisible())
        self.assertTrue(duration_widget.duration_epoch_length.isVisible())
        self.assertFalse(duration_widget.epoch_start.isVisible())
        self.assertEqual(duration_state["segmentation"]["segmentation_strategy"], "window")
        self.assertTrue(duration_widget.window_segmentation_widget.isVisible())
        self.assertEqual(duration_widget._epoch_target, "duration")
        self.assertEqual(duration_widget._normalization_target, "duration")
        self.assertEqual(duration_state["segmentation"]["epoch_parameters"]["instant"], {})
        self.assertEqual(duration_state["segmentation"]["normalization"]["instant"], {})

        instant_events = [f"instant_child_{index}" for index in range(7)]
        instant_state = _loaded_state_with_events([f"base_{index}" for index in range(7)], instant_events)
        instant_widget = EEGSegmentationWidget({}, _eeg_defaults(), instant_state)
        instant_widget.show()
        self.app.processEvents()

        instant_widget.nested_mode_button.click()
        instant_widget._epoch_target = "duration"
        instant_widget._normalization_target = "duration"
        instant_state["segmentation"]["event_groups"] = [
            {
                "base_event": f"base_{index}",
                "duration_events": [],
                "instant_events": [f"instant_child_{index}"],
            }
            for index in range(7)
        ]
        instant_widget._sync()
        instant_widget.normalization_enabled.setChecked(True)
        self.app.processEvents()

        self.assertFalse(instant_widget.epoch_target_panel.isVisible())
        self.assertFalse(instant_widget.normalization_target_panel.isVisible())
        self.assertTrue(instant_widget.epoch_start.isVisible())
        self.assertFalse(instant_widget.duration_epoch_length.isVisible())
        self.assertTrue(instant_widget.baseline_start.isVisible())
        self.assertEqual(instant_state["segmentation"]["segmentation_strategy"], "onset")
        self.assertFalse(instant_widget.window_segmentation_widget.isVisible())
        self.assertEqual(instant_widget._epoch_target, "instant")
        self.assertEqual(instant_widget._normalization_target, "instant")
        self.assertEqual(instant_state["segmentation"]["epoch_parameters"]["duration"], {})
        self.assertEqual(instant_state["segmentation"]["normalization"]["duration"], {})

    def test_nested_mode_rejects_mixed_child_event_types(self):
        state = _loaded_state()
        widget = EEGSegmentationWidget({}, _eeg_defaults(), state)
        widget.show()
        self.app.processEvents()

        widget.nested_mode_button.click()
        state["segmentation"]["event_groups"] = [
            {
                "base_event": "trial",
                "duration_events": ["full_recording"],
                "instant_events": ["stimulus"],
            }
        ]
        widget._sync()
        self.app.processEvents()

        self.assertFalse(widget.epoch_target_panel.isVisible())
        self.assertFalse(widget.normalization_target_panel.isVisible())
        self.assertFalse(widget.can_continue())
        self.assertIn(
            "Nested mode supports either duration or instant nested events, not both.",
            widget.validation_errors,
        )


if __name__ == "__main__":
    unittest.main()
