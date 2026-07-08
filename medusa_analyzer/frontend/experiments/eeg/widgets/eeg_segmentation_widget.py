from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QListWidget, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

from medusa_analyzer.frontend.validation import Validation


class EEGSegmentationWidget(QScrollArea):
    changed = Signal()

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        step_config = next((step for step in experiment_info.get("workflow", []) if step.get("id") == "segmentation"), {})
        self.config = defaults.get("segmentation", {})
        self.state = state
        self.validation = Validation()
        self.validation_errors: list[str] = []
        self.source_sampling_frequency: float | None = None
        self._updating_events = False
        self._last_event_signature: tuple[tuple[str, ...], tuple[str, ...]] | None = None
        self.state["segmentation"] = {**deepcopy(self.config), **(self.state.get("segmentation") or {})}

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(4, 4, 12, 4)
        root.setSpacing(16)

        title = QLabel(str(step_config.get("title", "Segmentation")))
        title.setObjectName("pageTitle")
        subtitle = QLabel(str(step_config.get("subtitle", "Select events and epoch settings.")))
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        events_panel = self._panel("Signal events")
        events_grid = QGridLayout()
        events_grid.setHorizontalSpacing(24)
        self.events_message = QLabel("Load and select a BIDS configuration first.")
        self.events_message.setObjectName("muted")
        self.events_message.setWordWrap(True)
        self.nested_events = QCheckBox("Instant events inside duration events")
        self.nested_events_panel = QFrame()
        self.nested_events_panel.setStyleSheet("""
            QFrame {
                background: #1F171B;
                border: 1px solid #4A3A42;
                border-radius: 9px;
            }
            QCheckBox {
                background: transparent;
                border: none;
                color: #F7F1F3;
                font-weight: 650;
                padding: 8px 10px;
            }
        """)
        nested_events_layout = QHBoxLayout(self.nested_events_panel)
        nested_events_layout.setContentsMargins(6, 4, 6, 4)
        nested_events_layout.addWidget(self.nested_events)
        self.duration_events_list = QListWidget()
        self.instant_events_list = QListWidget()
        for list_widget in (self.duration_events_list, self.instant_events_list):
            list_widget.setProperty("role", "file-list")
            list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            list_widget.setMinimumHeight(128)
        self.duration_events_list.setStyleSheet("""
            QListWidget {
                color: #F4E9ED;
                background: #1F171B;
                border: 1px solid #3E3036;
                border-radius: 9px;
                padding: 8px;
                outline: none;
            }
            QListWidget::item {
                padding: 7px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                color: #FFD6E1;
                background: rgba(227, 90, 130, 28);
                border: 1px solid rgba(227, 90, 130, 92);
            }
        """)
        self.instant_events_list.setStyleSheet("""
            QListWidget {
                color: #F4E9ED;
                background: #1F171B;
                border: 1px solid #3E3036;
                border-radius: 9px;
                padding: 8px;
                outline: none;
            }
            QListWidget::item {
                padding: 7px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                color: #9BE7E8;
                background: rgba(14, 124, 134, 24);
                border: 1px solid rgba(94, 205, 214, 78);
            }
        """)
        duration_title = QLabel("Duration events")
        duration_title.setObjectName("subgroupTitle")
        instant_title = QLabel("Instant events")
        instant_title.setObjectName("subgroupTitle")
        events_grid.addWidget(duration_title, 0, 0)
        events_grid.addWidget(instant_title, 0, 1)
        events_grid.addWidget(self.duration_events_list, 1, 0)
        events_grid.addWidget(self.instant_events_list, 1, 1)
        events_panel.layout().addWidget(self.events_message)
        events_panel.layout().addLayout(events_grid)
        events_panel.layout().addWidget(self.nested_events_panel)
        root.addWidget(events_panel)

        self.status_label = QLabel("Select at least one event.")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        summary_panel = self._panel("Segmentation summary")
        self.summary_layout = QVBoxLayout()
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_panel.layout().addLayout(self.summary_layout)
        root.addWidget(summary_panel)

        epoch_panel = self._panel("Epoch parameters")
        epoch_grid = QGridLayout()
        epoch_panel.layout().addLayout(epoch_grid)
        epoch_config = self.config.get("epoch_window_ms", {})
        self.epoch_start_label = QLabel("Epoch start")
        self.epoch_end_label = QLabel("Epoch end")
        self.duration_epoch_length_label = QLabel("Epoch length")
        self.epoch_start = self._spin(-60000, 60000, int(epoch_config.get("start", -300)))
        self.epoch_end = self._spin(-60000, 60000, int(epoch_config.get("end", 700)))
        self.duration_epoch_length = self._spin(1, 60000, int(self.config.get("duration_epoch_length_ms", 1000)))
        self.stride = self._spin(0, 100, int(self.config.get("stride_percent", 0)), suffix=" %")
        self.average_epochs = QCheckBox("Average epochs before feature extraction")
        epoch_grid.addWidget(self.epoch_start_label, 0, 0)
        epoch_grid.addWidget(self.epoch_start, 0, 1)
        epoch_grid.addWidget(self.epoch_end_label, 1, 0)
        epoch_grid.addWidget(self.epoch_end, 1, 1)
        epoch_grid.addWidget(self.duration_epoch_length_label, 2, 0)
        epoch_grid.addWidget(self.duration_epoch_length, 2, 1)
        epoch_grid.addWidget(QLabel("Stride"), 3, 0)
        epoch_grid.addWidget(self.stride, 3, 1)
        epoch_grid.addWidget(self.average_epochs, 4, 0, 1, 2)
        root.addWidget(epoch_panel)

        normalization_panel = self._panel("Normalization")
        normalization_grid = QGridLayout()
        normalization_panel.layout().addLayout(normalization_grid)
        normalization_config = self.config.get("normalization", {})
        baseline_config = normalization_config.get("baseline_window_ms", {})
        self.normalization_enabled = QCheckBox("Normalize epochs")
        self.normalization_mode = QComboBox()
        self.normalization_mode.addItem("Mean", "mean")
        self.normalization_mode.addItem("Mean + std", "mean_std")
        self.baseline_start_label = QLabel("Baseline start")
        self.baseline_end_label = QLabel("Baseline end")
        self.baseline_start = self._spin(-60000, 60000, int(baseline_config.get("start", -100)))
        self.baseline_end = self._spin(-60000, 60000, int(baseline_config.get("end", 0)))
        normalization_grid.addWidget(self.normalization_enabled, 0, 0, 1, 2)
        normalization_grid.addWidget(QLabel("Mode"), 1, 0)
        normalization_grid.addWidget(self.normalization_mode, 1, 1)
        normalization_grid.addWidget(self.baseline_start_label, 2, 0)
        normalization_grid.addWidget(self.baseline_start, 2, 1)
        normalization_grid.addWidget(self.baseline_end_label, 3, 0)
        normalization_grid.addWidget(self.baseline_end, 3, 1)
        root.addWidget(normalization_panel)

        threshold_panel = self._panel("Thresholding")
        threshold_grid = QGridLayout()
        threshold_panel.layout().addLayout(threshold_grid)
        self.threshold_enabled = QCheckBox("Discard epochs exceeding threshold")
        threshold_note = QLabel("Reject epochs when enough samples/channels exceed the sigma threshold.")
        threshold_note.setObjectName("muted")
        threshold_note.setWordWrap(True)
        self.threshold_sigma = QDoubleSpinBox()
        self.threshold_sigma.setRange(0.1, 1000.0)
        self.threshold_sigma.setDecimals(2)
        self.threshold_sigma.setSingleStep(0.1)
        self.threshold_samples = self._spin(1, 100000, int(self.config["thresholding"]["samples"]))
        self.threshold_channels = self._spin(1, 100000, int(self.config["thresholding"]["channels"]))
        threshold_grid.addWidget(self.threshold_enabled, 0, 0, 1, 2)
        threshold_grid.addWidget(threshold_note, 1, 0, 1, 2)
        threshold_grid.addWidget(QLabel("Sigma"), 2, 0)
        threshold_grid.addWidget(self.threshold_sigma, 2, 1)
        threshold_grid.addWidget(QLabel("Samples"), 3, 0)
        threshold_grid.addWidget(self.threshold_samples, 3, 1)
        threshold_grid.addWidget(QLabel("Channels"), 4, 0)
        threshold_grid.addWidget(self.threshold_channels, 4, 1)
        root.addWidget(threshold_panel)

        resampling_panel = self._panel("Resampling epochs")
        resampling_grid = QGridLayout()
        resampling_panel.layout().addLayout(resampling_grid)
        self.resampling_enabled = QCheckBox("Resample epochs")
        self.target_sampling_frequency = self._spin(250, 100000,
            int(self.config["resampling"]["target_sampling_frequency"]), suffix=" Hz")
        nyquist_label = QLabel("Minimum 250 Hz (Nyquist).")
        nyquist_label.setObjectName("muted")
        resampling_grid.addWidget(self.resampling_enabled, 0, 0, 1, 2)
        resampling_grid.addWidget(QLabel("Target sample frequency"), 1, 0)
        resampling_grid.addWidget(self.target_sampling_frequency, 1, 1)
        resampling_grid.addWidget(nyquist_label, 2, 0, 1, 2)
        root.addWidget(resampling_panel)
        root.addStretch()
        self.setWidget(content)

        self._load_state()
        for widget in [self.epoch_start, self.epoch_end, self.duration_epoch_length, self.stride,
            self.average_epochs, self.normalization_enabled, self.normalization_mode, self.baseline_start,
            self.baseline_end, self.threshold_enabled, self.threshold_sigma, self.threshold_samples,
            self.threshold_channels, self.resampling_enabled, self.target_sampling_frequency]:
            signal = widget.currentIndexChanged if isinstance(widget, QComboBox) else (
                widget.toggled if isinstance(widget, QCheckBox) else widget.valueChanged)
            signal.connect(self._sync)
        self.nested_events.toggled.connect(self._nested_mode_changed)
        self.duration_events_list.itemSelectionChanged.connect(lambda group="duration": self._event_changed(group))
        self.instant_events_list.itemSelectionChanged.connect(lambda group="instant": self._event_changed(group))
        self.on_step_activated()

    def _panel(self, title: str) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return panel

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int, suffix: str = " ms") -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin

    def _load_state(self) -> None:
        segmentation = self.state["segmentation"]
        epoch = segmentation.get("epoch_window_ms", {})
        normalization = segmentation.get("normalization", {})
        thresholding = segmentation.get("thresholding", {})
        resampling = segmentation.get("resampling", {})
        baseline = normalization.get("baseline_window_ms", {})
        self.epoch_start.setValue(int(epoch.get("start", self.config.get("epoch_window_ms", {}).get("start", -300))))
        self.epoch_end.setValue(int(epoch.get("end", self.config.get("epoch_window_ms", {}).get("end", 700))))
        self.duration_epoch_length.setValue(int(segmentation.get("duration_epoch_length_ms",
            self.config.get("duration_epoch_length_ms", 1000))))
        self.stride.setValue(int(segmentation.get("stride_percent", self.config.get("stride_percent", 0))))
        self.average_epochs.setChecked(bool(segmentation.get("average_epochs", self.config.get("average_epochs", False))))
        self.nested_events.setChecked(bool(segmentation.get("instant_events_inside_duration_events",
            self.config.get("instant_events_inside_duration_events", False))))
        self.normalization_enabled.setChecked(bool(normalization.get("enabled", self.config["normalization"]["enabled"])))
        self.normalization_mode.setCurrentIndex(max(0,
            self.normalization_mode.findData(normalization.get("mode", self.config["normalization"]["mode"]))))
        self.baseline_start.setValue(int(baseline.get("start", self.config["normalization"]["baseline_window_ms"]["start"])))
        self.baseline_end.setValue(int(baseline.get("end", self.config["normalization"]["baseline_window_ms"]["end"])))
        self.threshold_enabled.setChecked(bool(thresholding.get("enabled", self.config["thresholding"]["enabled"])))
        self.threshold_sigma.setValue(float(thresholding.get("sigma", self.config["thresholding"]["sigma"])))
        self.threshold_samples.setValue(int(thresholding.get("samples", self.config["thresholding"]["samples"])))
        self.threshold_channels.setValue(int(thresholding.get("channels", self.config["thresholding"]["channels"])))
        self.resampling_enabled.setChecked(bool(resampling.get("enabled", self.config["resampling"]["enabled"])))
        self.target_sampling_frequency.setValue(int(resampling.get("target_sampling_frequency",
            self.config["resampling"]["target_sampling_frequency"])))

    def _event_names(self) -> tuple[list[str], list[str]]:
        group_id = self.state.get("selected_bids_group")
        for group in self.state.get("bids_groups", []):
            if group.get("id") == group_id:
                duration_events = list(group.get("duration_events") or [])
                instant_events = list(group.get("instant_events") or [])
                if not duration_events and not instant_events:
                    instant_events = list(group.get("event_types") or [])
                return duration_events, instant_events
        return [], []

    def _clear_layout(self, layout: QVBoxLayout | QHBoxLayout | QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            if item.layout():
                self._clear_layout(item.layout())

    def _clear_event_group(self, group: str) -> None:
        list_widget = self.instant_events_list if group == "instant" else self.duration_events_list
        list_widget.blockSignals(True)
        list_widget.clearSelection()
        list_widget.blockSignals(False)

    def _refresh_events(self) -> None:
        duration_events, instant_events = self._event_names()
        signature = (tuple(duration_events), tuple(instant_events))
        segmentation = self.state["segmentation"]
        saved_duration = set(segmentation.get("selected_duration_events") or [])
        saved_instant = set(segmentation.get("selected_instant_events") or [])
        if signature != self._last_event_signature:
            saved_duration &= set(duration_events)
            saved_instant &= set(instant_events)
            if not self.nested_events.isChecked() and saved_duration and saved_instant:
                saved_instant.clear()

        self._updating_events = True
        self.duration_events_list.blockSignals(True)
        self.instant_events_list.blockSignals(True)
        self.duration_events_list.clear()
        self.instant_events_list.clear()
        self.events_message.setVisible(not (duration_events or instant_events))
        for event_name in duration_events:
            self.duration_events_list.addItem(str(event_name))
            self.duration_events_list.item(self.duration_events_list.count() - 1).setSelected(event_name in saved_duration)
        for event_name in instant_events:
            self.instant_events_list.addItem(str(event_name))
            self.instant_events_list.item(self.instant_events_list.count() - 1).setSelected(event_name in saved_instant)
        self.duration_events_list.blockSignals(False)
        self.instant_events_list.blockSignals(False)
        self._last_event_signature = signature
        self._updating_events = False

    def _current_event_selection(self) -> tuple[list[str], list[str]]:
        duration = [item.text() for item in self.duration_events_list.selectedItems()]
        instant = [item.text() for item in self.instant_events_list.selectedItems()]
        return duration, instant

    def _event_changed(self, group: str) -> None:
        if self._updating_events:
            return
        if not self.nested_events.isChecked():
            duration_events, instant_events = self._current_event_selection()
            if group == "duration" and duration_events:
                self._clear_event_group("instant")
            if group == "instant" and instant_events:
                self._clear_event_group("duration")
        self._sync()

    def _nested_mode_changed(self, checked: bool) -> None:
        if not checked:
            duration_events, instant_events = self._current_event_selection()
            if duration_events and instant_events:
                self._clear_event_group("instant")
        self._sync()

    @staticmethod
    def _selection_mode(nested: bool, duration_events: list[str], instant_events: list[str]) -> str:
        if nested:
            return "instant_within_duration"
        if duration_events:
            return "duration"
        if instant_events:
            return "instant"
        return "none"

    @staticmethod
    def _set_visible(widgets: list[QWidget], visible: bool) -> None:
        for widget in widgets:
            widget.setVisible(visible)

    def _set_dependent_enabled(self, mode: str) -> None:
        self.duration_events_list.setEnabled(True)
        self.instant_events_list.setEnabled(True)

        duration_only = mode == "duration"
        normalization = self.normalization_enabled.isChecked()
        thresholding = self.threshold_enabled.isChecked()
        resampling = self.resampling_enabled.isChecked()
        baseline_visible = normalization and not duration_only
        self._set_visible([self.epoch_start_label, self.epoch_start, self.epoch_end_label, self.epoch_end], not duration_only)
        self._set_visible([self.duration_epoch_length_label, self.duration_epoch_length], duration_only)
        self._set_visible([self.baseline_start_label, self.baseline_start, self.baseline_end_label, self.baseline_end],
            baseline_visible)
        self.normalization_mode.setEnabled(normalization)
        self.baseline_start.setEnabled(baseline_visible)
        self.baseline_end.setEnabled(baseline_visible)
        for widget in (self.threshold_sigma, self.threshold_samples, self.threshold_channels):
            widget.setEnabled(thresholding)
        self.target_sampling_frequency.setEnabled(resampling)

    def _refresh_status_style(self) -> None:
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _update_status_label(self, mode: str, duration_events: list[str], instant_events: list[str]) -> None:
        available_duration_events, available_instant_events = self._event_names()
        if not available_duration_events and not available_instant_events:
            text = "Load and select a BIDS configuration first."
            status = "idle"
        elif self.validation_errors:
            text = self.validation_errors[0]
            status = "idle"
        elif mode == "instant_within_duration":
            text = f"{len(duration_events)} duration event(s) with {len(instant_events)} instant event(s)."
            status = "ready"
        elif mode == "duration":
            text = f"{len(duration_events)} duration event(s) selected."
            status = "ready"
        elif mode == "instant":
            text = f"{len(instant_events)} instant event(s) selected."
            status = "ready"
        else:
            text = "Select at least one event."
            status = "idle"
        self.status_label.setText(text)
        self.status_label.setProperty("status", status)
        self._refresh_status_style()

    def _summary_chip(self, text: str, kind: str) -> QFrame:
        chip = QFrame()
        chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        if kind == "duration":
            chip.setObjectName("summaryDurationChip")
            chip.setStyleSheet("""
                QFrame#summaryDurationChip {
                    background: rgba(227, 90, 130, 28);
                    border: 1px solid rgba(227, 90, 130, 92);
                    border-radius: 9px;
                }
                QFrame#summaryDurationChip QLabel {
                    background: transparent;
                    border: none;
                    color: #FFD6E1;
                    font-weight: 650;
                }
            """)
        else:
            chip.setObjectName("summaryInstantChip")
            chip.setStyleSheet("""
                QFrame#summaryInstantChip {
                    background: rgba(14, 124, 134, 24);
                    border: 1px solid rgba(94, 205, 214, 78);
                    border-radius: 9px;
                }
                QFrame#summaryInstantChip QLabel {
                    background: transparent;
                    border: none;
                    color: #9BE7E8;
                    font-weight: 600;
                }
            """)
        layout = QVBoxLayout(chip)
        layout.setContentsMargins(10, 6, 10, 6)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        return chip

    def _refresh_summary(self, mode: str, duration_events: list[str], instant_events: list[str]) -> None:
        self._clear_layout(self.summary_layout)
        if mode == "none" or not (duration_events or instant_events):
            empty = QLabel("No events selected.")
            empty.setObjectName("muted")
            self.summary_layout.addWidget(empty)
            return
        if mode == "instant_within_duration":
            if not duration_events:
                empty = QLabel("No duration events selected.")
                empty.setObjectName("muted")
                self.summary_layout.addWidget(empty)
                return
            summary_row = QHBoxLayout()
            for duration_event in duration_events:
                card = self._summary_chip(duration_event, "duration")
                row = QHBoxLayout()
                for instant_event in instant_events:
                    row.addWidget(self._summary_chip(instant_event, "instant"))
                if not instant_events:
                    empty = QLabel("No instant events selected.")
                    empty.setObjectName("muted")
                    row.addWidget(empty)
                row.addStretch()
                card.layout().addLayout(row)
                summary_row.addWidget(card)
            summary_row.addStretch()
            self.summary_layout.addLayout(summary_row)
            return
        row = QHBoxLayout()
        chip_kind = "duration" if mode == "duration" else "instant"
        for event_name in duration_events + instant_events:
            row.addWidget(self._summary_chip(event_name, chip_kind))
        row.addStretch()
        self.summary_layout.addLayout(row)

    def _sync(self, *_: Any) -> None:
        duration_events, instant_events = self._current_event_selection()
        nested = self.nested_events.isChecked()
        mode = self._selection_mode(nested, duration_events, instant_events)
        self.state["segmentation"] = {
            "selection_mode": mode,
            "instant_events_inside_duration_events": nested,
            "selected_duration_events": duration_events,
            "selected_instant_events": instant_events,
            "epoch_window_ms": {"start": self.epoch_start.value(), "end": self.epoch_end.value()},
            "duration_epoch_length_ms": self.duration_epoch_length.value(),
            "stride_percent": self.stride.value(),
            "average_epochs": self.average_epochs.isChecked(),
            "normalization": {
                "enabled": self.normalization_enabled.isChecked(),
                "mode": self.normalization_mode.currentData(),
                "baseline_window_ms": {"start": self.baseline_start.value(), "end": self.baseline_end.value()},
            },
            "thresholding": {
                "enabled": self.threshold_enabled.isChecked(),
                "sigma": self.threshold_sigma.value(),
                "samples": self.threshold_samples.value(),
                "channels": self.threshold_channels.value(),
            },
            "resampling": {
                "enabled": self.resampling_enabled.isChecked(),
                "target_sampling_frequency": self.target_sampling_frequency.value(),
            },
        }
        self._set_dependent_enabled(mode)
        self._refresh_summary(mode, duration_events, instant_events)
        self.validation_errors = self._validate()
        self._update_status_label(mode, duration_events, instant_events)
        self.changed.emit()

    def _validate(self) -> list[str]:
        segmentation = self.state["segmentation"]
        mode = segmentation["selection_mode"]
        errors: list[str] = []
        if mode == "duration":
            errors.extend(self.validation.validate_many(segmentation["selected_duration_events"],
                [("minimum_length", {"minimum": 1, "item_name": "duration event", "action": "select"})],
                label="Duration events"))
            errors.extend(self.validation.validate_many(segmentation["duration_epoch_length_ms"],
                ["integer", ("greater_than", {"minimum": 0, "suffix": " ms"})],
                label="Epoch length", stop_on_first_error=False))
        elif mode == "instant":
            errors.extend(self.validation.validate_many(segmentation["selected_instant_events"],
                [("minimum_length", {"minimum": 1, "item_name": "instant event", "action": "select"})],
                label="Instant events"))
        elif mode == "instant_within_duration":
            errors.extend(self.validation.validate_many(segmentation["selected_duration_events"],
                [("minimum_length", {"minimum": 1, "item_name": "duration event", "action": "select"})],
                label="Duration events"))
            errors.extend(self.validation.validate_many(segmentation["selected_instant_events"],
                [("minimum_length", {"minimum": 1, "item_name": "instant event", "action": "select"})],
                label="Instant events"))
        else:
            errors.append("Signal events: select at least one event.")

        start = segmentation["epoch_window_ms"]["start"]
        end = segmentation["epoch_window_ms"]["end"]
        if mode != "duration":
            errors.extend(self.validation.validate_many(start, ["integer"], label="Epoch start"))
            errors.extend(self.validation.validate_many(end, ["integer"], label="Epoch end"))
            if end <= start:
                errors.append("Epoch window: end must be greater than start.")
        errors.extend(self.validation.validate_many(segmentation["stride_percent"],
            ["integer", ("greater_or_equal", {"minimum": 0, "suffix": " %"}),
             ("less_or_equal", {"maximum": 100, "suffix": " %"})], label="Stride", stop_on_first_error=False))

        normalization = segmentation["normalization"]
        if normalization["enabled"]:
            errors.extend(self.validation.validate_many(normalization["mode"],
                [("one_of", {"options": ["mean", "mean_std"]})], label="Normalization mode"))
            if mode != "duration":
                base_start = normalization["baseline_window_ms"]["start"]
                base_end = normalization["baseline_window_ms"]["end"]
                if base_end <= base_start:
                    errors.append("Baseline window: end must be greater than start.")
                if base_start < start or base_end > end:
                    errors.append("Baseline window must be inside the epoch window.")

        epoch_ms = segmentation["duration_epoch_length_ms"] if mode == "duration" else max(0, end - start)
        epoch_samples = int(epoch_ms * float(self.source_sampling_frequency or 0) / 1000) if epoch_ms > 0 else 0
        n_channels = int((self.state.get("metadata") or {}).get("n_channels") or 0)
        thresholding = segmentation["thresholding"]
        if thresholding["enabled"]:
            errors.extend(self.validation.validate_many(thresholding["sigma"],
                ["finite_number", ("greater_than", {"minimum": 0})], label="Threshold sigma",
                stop_on_first_error=False))
            errors.extend(self.validation.validate_many(thresholding["samples"],
                ["integer", ("greater_or_equal", {"minimum": 1})], label="Threshold samples",
                stop_on_first_error=False))
            errors.extend(self.validation.validate_many(thresholding["channels"],
                ["integer", ("greater_or_equal", {"minimum": 1})], label="Threshold channels",
                stop_on_first_error=False))
            if epoch_samples and thresholding["samples"] > epoch_samples:
                errors.append("Threshold samples cannot exceed the epoch sample count.")
            if n_channels and thresholding["channels"] > n_channels:
                errors.append("Threshold channels cannot exceed the loaded channel count.")

        resampling = segmentation["resampling"]
        if resampling["enabled"]:
            target = resampling["target_sampling_frequency"]
            errors.extend(self.validation.validate_many(target,
                ["integer", ("greater_or_equal", {"minimum": 250, "suffix": " Hz"})],
                label="Target sample frequency", stop_on_first_error=False))
            if self.source_sampling_frequency is not None:
                errors.extend(self.validation.validate_many(target,
                    [("less_or_equal", {"maximum": self.source_sampling_frequency, "suffix": " Hz"})],
                    label="Target sample frequency"))
        return errors

    def on_step_activated(self) -> None:
        metadata = self.state.get("metadata") or {}
        self.source_sampling_frequency = metadata.get("sampling_frequency")
        if self.source_sampling_frequency is not None:
            self.target_sampling_frequency.setMaximum(max(250, int(self.source_sampling_frequency)))
        self._refresh_events()
        self._sync()

    def can_continue(self) -> bool:
        return not self.validation_errors


__all__ = ["EEGSegmentationWidget"]
