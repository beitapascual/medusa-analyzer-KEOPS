from __future__ import annotations

from copy import deepcopy
from typing import Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QScrollArea,
    QSizePolicy, QSpinBox, QVBoxLayout, QWidget)
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
        self._updating_mode = False
        self._updating_epoch_scope = False
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

        # ------------------------------------------------------------------
        # Signal events
        # ------------------------------------------------------------------
        events_panel = self._panel("Signal events")

        mode_label = QLabel("Segmentation mode")
        mode_label.setObjectName("subgroupTitle")
        events_panel.layout().addWidget(mode_label)

        mode_row = QHBoxLayout()
        self.independent_mode_button = QPushButton("Independent events")
        self.nested_mode_button = QPushButton("Nested events")
        for button in (self.independent_mode_button, self.nested_mode_button):
            button.setObjectName("segmentationModeButton")
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setStyleSheet(self._segmentation_mode_button_style())

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.independent_mode_button)
        self.mode_group.addButton(self.nested_mode_button)

        mode_row.addWidget(self.independent_mode_button)
        mode_row.addWidget(self.nested_mode_button)
        events_panel.layout().addLayout(mode_row)

        self.mode_help = QLabel()
        self.mode_help.setObjectName("muted")
        self.mode_help.setWordWrap(True)
        events_panel.layout().addWidget(self.mode_help)

        self.events_message = QLabel("Load and select a BIDS configuration first.")
        self.events_message.setObjectName("muted")
        self.events_message.setWordWrap(True)
        events_panel.layout().addWidget(self.events_message)

        # Independent mode
        self.independent_panel = QFrame()
        independent_layout = QVBoxLayout(self.independent_panel)
        independent_layout.setContentsMargins(0, 8, 0, 0)

        independent_grid = QGridLayout()
        independent_grid.setHorizontalSpacing(24)

        self.duration_events_list = QListWidget()
        self.instant_events_list = QListWidget()
        for list_widget in (self.duration_events_list, self.instant_events_list):
            list_widget.setProperty("role", "file-list")
            list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            list_widget.setMinimumHeight(128)
         # TODO: hacer con el qss
        self.duration_events_list.setStyleSheet("""
            QListWidget {color: #F4E9ED; background: #1F171B;
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

        independent_grid.addWidget(duration_title, 0, 0)
        independent_grid.addWidget(instant_title, 0, 1)
        independent_grid.addWidget(self.duration_events_list, 1, 0)
        independent_grid.addWidget(self.instant_events_list, 1, 1)
        independent_layout.addLayout(independent_grid)
        events_panel.layout().addWidget(self.independent_panel)

        # Nested mode
        self.nested_panel = QFrame()
        nested_layout = QVBoxLayout(self.nested_panel)
        nested_layout.setContentsMargins(0, 8, 0, 0)
        nested_layout.setSpacing(12)

        nested_note = QLabel("Add a duration event as the base and then assign duration or instant events contained within it.")
        nested_note.setObjectName("muted")
        nested_note.setWordWrap(True)
        nested_layout.addWidget(nested_note)

        self.add_base_event_button = QPushButton("+ Add base duration event")
        self.add_base_event_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        nested_layout.addWidget(self.add_base_event_button)

        self.nested_groups_layout = QVBoxLayout()
        self.nested_groups_layout.setContentsMargins(0, 0, 0, 0)
        self.nested_groups_layout.setSpacing(10)
        nested_layout.addLayout(self.nested_groups_layout)
        events_panel.layout().addWidget(self.nested_panel)

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

        # ------------------------------------------------------------------
        # Epoch parameters
        # ------------------------------------------------------------------
        epoch_panel = self._panel("Epoch parameters")

        self.epoch_scope_panel = QWidget()
        epoch_scope_layout = QVBoxLayout(self.epoch_scope_panel)
        epoch_scope_layout.setContentsMargins(0, 0, 0, 8)
        epoch_scope_layout.setSpacing(8)

        self.epoch_scope_message = QLabel()
        self.epoch_scope_message.setObjectName("muted")
        self.epoch_scope_message.setWordWrap(True)
        epoch_scope_layout.addWidget(self.epoch_scope_message)

        self.epoch_scope_buttons = QWidget()
        epoch_scope_buttons_layout = QHBoxLayout(self.epoch_scope_buttons)
        epoch_scope_buttons_layout.setContentsMargins(0, 0, 0, 0)
        epoch_scope_buttons_layout.setSpacing(8)

        self.instant_epoch_scope_button = QPushButton("Instant nested events")
        self.duration_epoch_scope_button = QPushButton("Duration nested events")
        self.instant_epoch_scope_button.setProperty("kind", "instant")
        self.duration_epoch_scope_button.setProperty("kind", "duration")
        for button in (self.instant_epoch_scope_button, self.duration_epoch_scope_button):
            button.setObjectName("epochScopeButton")
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setStyleSheet(self._epoch_scope_button_style())

        self.epoch_scope_group = QButtonGroup(self)
        self.epoch_scope_group.setExclusive(True)
        self.epoch_scope_group.addButton(self.instant_epoch_scope_button)
        self.epoch_scope_group.addButton(self.duration_epoch_scope_button)

        epoch_scope_buttons_layout.addWidget(self.instant_epoch_scope_button)
        epoch_scope_buttons_layout.addWidget(self.duration_epoch_scope_button)
        epoch_scope_layout.addWidget(self.epoch_scope_buttons)
        epoch_panel.layout().addWidget(self.epoch_scope_panel)

        epoch_grid = QGridLayout()
        epoch_panel.layout().addLayout(epoch_grid)

        epoch_config = self.config.get("epoch_window_ms", {})
        self.epoch_start_label = QLabel("Epoch start")
        self.epoch_end_label = QLabel("Epoch end")
        self.duration_epoch_length_label = QLabel("Epoch length")
        self.stride_label = QLabel("Stride")

        self.epoch_start = self._spin(-60000, 60000, int(epoch_config.get("start", -300)))
        self.epoch_end = self._spin(-60000, 60000, int(epoch_config.get("end", 700)))
        self.duration_epoch_length = self._spin(1, 60000,
            int(self.config.get("duration_epoch_length_ms", 1000)))
        self.stride = self._spin(0,100, int(self.config.get("stride_percent", 0)),
            suffix=" %")
        self.average_epochs = QCheckBox("Average epochs before feature extraction")

        epoch_grid.addWidget(self.epoch_start_label, 0, 0)
        epoch_grid.addWidget(self.epoch_start, 0, 1)
        epoch_grid.addWidget(self.epoch_end_label, 1, 0)
        epoch_grid.addWidget(self.epoch_end, 1, 1)
        epoch_grid.addWidget(self.duration_epoch_length_label, 2, 0)
        epoch_grid.addWidget(self.duration_epoch_length, 2, 1)
        epoch_grid.addWidget(self.stride_label, 3, 0)
        epoch_grid.addWidget(self.stride, 3, 1)
        epoch_grid.addWidget(self.average_epochs, 4, 0, 1, 2)
        root.addWidget(epoch_panel)

        # ------------------------------------------------------------------
        # Normalization
        # ------------------------------------------------------------------
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
        self.baseline_start = self._spin(-60000,60000, int(baseline_config.get("start", -100)))
        self.baseline_end = self._spin(-60000,60000, int(baseline_config.get("end", 0)))

        normalization_grid.addWidget(self.normalization_enabled, 0, 0, 1, 2)
        normalization_grid.addWidget(QLabel("Mode"), 1, 0)
        normalization_grid.addWidget(self.normalization_mode, 1, 1)
        normalization_grid.addWidget(self.baseline_start_label, 2, 0)
        normalization_grid.addWidget(self.baseline_start, 2, 1)
        normalization_grid.addWidget(self.baseline_end_label, 3, 0)
        normalization_grid.addWidget(self.baseline_end, 3, 1)
        root.addWidget(normalization_panel)

        # ------------------------------------------------------------------
        # Thresholding
        # ------------------------------------------------------------------
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

        self.threshold_samples = self._spin(1,100000, int(self.config["thresholding"]["samples"]))
        self.threshold_channels = self._spin(1,100000, int(self.config["thresholding"]["channels"]))

        threshold_grid.addWidget(self.threshold_enabled, 0, 0, 1, 2)
        threshold_grid.addWidget(threshold_note, 1, 0, 1, 2)
        threshold_grid.addWidget(QLabel("Sigma"), 2, 0)
        threshold_grid.addWidget(self.threshold_sigma, 2, 1)
        threshold_grid.addWidget(QLabel("Samples"), 3, 0)
        threshold_grid.addWidget(self.threshold_samples, 3, 1)
        threshold_grid.addWidget(QLabel("Channels"), 4, 0)
        threshold_grid.addWidget(self.threshold_channels, 4, 1)
        root.addWidget(threshold_panel)

        # ------------------------------------------------------------------
        # Resampling
        # ------------------------------------------------------------------
        resampling_panel = self._panel("Resampling epochs")
        resampling_grid = QGridLayout()
        resampling_panel.layout().addLayout(resampling_grid)

        self.resampling_enabled = QCheckBox("Resample epochs")
        self.target_sampling_frequency = self._spin(
            250,
            100000,
            int(self.config["resampling"]["target_sampling_frequency"]),
            suffix=" Hz",
        )

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

        for widget in [
            self.epoch_start,
            self.epoch_end,
            self.duration_epoch_length,
            self.stride,
            self.average_epochs,
            self.normalization_enabled,
            self.normalization_mode,
            self.baseline_start,
            self.baseline_end,
            self.threshold_enabled,
            self.threshold_sigma,
            self.threshold_samples,
            self.threshold_channels,
            self.resampling_enabled,
            self.target_sampling_frequency,
        ]:
            signal = (
                widget.currentIndexChanged
                if isinstance(widget, QComboBox)
                else widget.toggled
                if isinstance(widget, QCheckBox)
                else widget.valueChanged
            )
            signal.connect(self._sync)

        self.independent_mode_button.toggled.connect(self._segmentation_mode_changed)
        self.nested_mode_button.toggled.connect(self._segmentation_mode_changed)
        self.instant_epoch_scope_button.toggled.connect(self._epoch_scope_changed)
        self.duration_epoch_scope_button.toggled.connect(self._epoch_scope_changed)
        self.duration_events_list.itemSelectionChanged.connect(
            lambda group="duration": self._independent_event_changed(group)
        )
        self.instant_events_list.itemSelectionChanged.connect(
            lambda group="instant": self._independent_event_changed(group)
        )
        self.add_base_event_button.clicked.connect(self._add_base_events)

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
    def _spin(
        minimum: int,
        maximum: int,
        value: int,
        suffix: str = " ms",
    ) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin

    @staticmethod
    def _segmentation_mode_button_style() -> str:
        return """
            QPushButton#segmentationModeButton {
                min-height: 38px;
                padding: 0 16px;
                color: #C5B7BE;
                background: #1B1318;
                border: 2px solid #4A3039;
                border-radius: 9px;
                font-weight: 650;
            }
            QPushButton#segmentationModeButton:hover {
                color: #FFD6E1;
                background: #2A1D23;
                border-color: #734052;
            }
            QPushButton#segmentationModeButton:focus {
                border-color: #39B8C1;
            }
            QPushButton#segmentationModeButton:checked {
                color: #FFF7FA;
                background: #A61E4D;
                border-color: #E35A82;
            }
            QPushButton#segmentationModeButton:checked:focus {
                border-color: #FFB0C4;
            }
            QPushButton#segmentationModeButton:disabled {
                color: #756B70;
                background: #2A2528;
                border-color: #2A2528;
            }
        """

    @staticmethod
    def _epoch_scope_button_style() -> str:
        return """
            QPushButton#epochScopeButton {
                min-height: 34px;
                padding: 0 12px;
                color: #C5B7BE;
                background: #1B1318;
                border: 2px solid #3E3036;
                border-radius: 8px;
                font-weight: 650;
            }
            QPushButton#epochScopeButton:hover {
                color: #F4E9ED;
                background: #2A1D23;
                border-color: #734052;
            }
            QPushButton#epochScopeButton:focus {
                border-color: #39B8C1;
            }
            QPushButton#epochScopeButton[kind="instant"]:checked {
                color: #9BE7E8;
                background: #173A3F;
                border-color: #39B8C1;
            }
            QPushButton#epochScopeButton[kind="duration"]:checked {
                color: #FFD6E1;
                background: #3B1D27;
                border-color: #E35A82;
            }
        """

    def _load_state(self) -> None:
        segmentation = self.state["segmentation"]
        epoch = segmentation.get("epoch_window_ms", {})
        normalization = segmentation.get("normalization", {})
        thresholding = segmentation.get("thresholding", {})
        resampling = segmentation.get("resampling", {})
        baseline = normalization.get("baseline_window_ms", {})

        self.epoch_start.setValue(
            int(epoch.get("start", self.config.get("epoch_window_ms", {}).get("start", -300)))
        )
        self.epoch_end.setValue(
            int(epoch.get("end", self.config.get("epoch_window_ms", {}).get("end", 700)))
        )
        self.duration_epoch_length.setValue(
            int(
                segmentation.get(
                    "duration_epoch_length_ms",
                    self.config.get("duration_epoch_length_ms", 1000),
                )
            )
        )
        self.stride.setValue(
            int(segmentation.get("stride_percent", self.config.get("stride_percent", 0)))
        )
        self.average_epochs.setChecked(
            bool(segmentation.get("average_epochs", self.config.get("average_epochs", False)))
        )
        self.normalization_enabled.setChecked(
            bool(normalization.get("enabled", self.config["normalization"]["enabled"]))
        )
        self.normalization_mode.setCurrentIndex(
            max(
                0,
                self.normalization_mode.findData(
                    normalization.get("mode", self.config["normalization"]["mode"])
                ),
            )
        )
        self.baseline_start.setValue(
            int(
                baseline.get(
                    "start",
                    self.config["normalization"]["baseline_window_ms"]["start"],
                )
            )
        )
        self.baseline_end.setValue(
            int(
                baseline.get(
                    "end",
                    self.config["normalization"]["baseline_window_ms"]["end"],
                )
            )
        )
        self.threshold_enabled.setChecked(
            bool(thresholding.get("enabled", self.config["thresholding"]["enabled"]))
        )
        self.threshold_sigma.setValue(
            float(thresholding.get("sigma", self.config["thresholding"]["sigma"]))
        )
        self.threshold_samples.setValue(
            int(thresholding.get("samples", self.config["thresholding"]["samples"]))
        )
        self.threshold_channels.setValue(
            int(thresholding.get("channels", self.config["thresholding"]["channels"]))
        )
        self.resampling_enabled.setChecked(
            bool(resampling.get("enabled", self.config["resampling"]["enabled"]))
        )
        self.target_sampling_frequency.setValue(
            int(
                resampling.get(
                    "target_sampling_frequency",
                    self.config["resampling"]["target_sampling_frequency"],
                )
            )
        )

        # Backward-compatible migration from the old checkbox-based nested mode.
        nested_groups = deepcopy(segmentation.get("nested_groups") or [])
        old_nested = bool(segmentation.get("instant_events_inside_duration_events", False))
        if not nested_groups and old_nested:
            old_duration = list(segmentation.get("selected_duration_events") or [])
            old_instant = list(segmentation.get("selected_instant_events") or [])
            nested_groups = [
                {
                    "base_event": base_event,
                    "nested_duration_events": [],
                    "nested_instant_events": list(old_instant),
                }
                for base_event in old_duration
            ]
        segmentation["nested_groups"] = nested_groups

        requested_mode = segmentation.get("segmentation_mode")
        if requested_mode not in {"independent", "nested"}:
            requested_mode = "nested" if nested_groups else "independent"

        self._updating_mode = True
        self.independent_mode_button.setChecked(requested_mode == "independent")
        self.nested_mode_button.setChecked(requested_mode == "nested")
        self._updating_mode = False

        requested_epoch_scope = segmentation.get("nested_epoch_parameter_scope")
        if requested_epoch_scope not in {"instant", "duration"}:
            requested_epoch_scope = "instant"

        self._updating_epoch_scope = True
        self.instant_epoch_scope_button.setChecked(requested_epoch_scope == "instant")
        self.duration_epoch_scope_button.setChecked(requested_epoch_scope == "duration")
        self._updating_epoch_scope = False

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

    def _current_segmentation_mode(self) -> str:
        return "nested" if self.nested_mode_button.isChecked() else "independent"

    def _nested_mode_available(self) -> bool:
        duration_events, _ = self._event_names()
        # The only duration event is the automatically-added full-signal event.
        return len(duration_events) > 1

    def _clear_layout(self, layout: QVBoxLayout | QHBoxLayout | QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            if item.layout():
                self._clear_layout(item.layout())

    def _clear_event_group(self, group: str) -> None:
        list_widget = (
            self.instant_events_list if group == "instant" else self.duration_events_list
        )
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

            if saved_duration and saved_instant:
                saved_instant.clear()

            valid_nested_groups = []
            for group in segmentation.get("nested_groups") or []:
                base_event = group.get("base_event")
                if base_event not in duration_events:
                    continue

                nested_duration = [
                    event
                    for event in group.get("nested_duration_events") or []
                    if event in duration_events and event != base_event
                ]
                nested_instant = [
                    event
                    for event in group.get("nested_instant_events") or []
                    if event in instant_events
                ]

                valid_nested_groups.append(
                    {
                        "base_event": base_event,
                        "nested_duration_events": list(dict.fromkeys(nested_duration)),
                        "nested_instant_events": list(dict.fromkeys(nested_instant)),
                    }
                )

            segmentation["nested_groups"] = valid_nested_groups

        self._updating_events = True
        self.duration_events_list.blockSignals(True)
        self.instant_events_list.blockSignals(True)

        self.duration_events_list.clear()
        self.instant_events_list.clear()

        self.events_message.setVisible(not (duration_events or instant_events))

        for event_name in duration_events:
            self.duration_events_list.addItem(str(event_name))
            self.duration_events_list.item(
                self.duration_events_list.count() - 1
            ).setSelected(event_name in saved_duration)

        for event_name in instant_events:
            self.instant_events_list.addItem(str(event_name))
            self.instant_events_list.item(
                self.instant_events_list.count() - 1
            ).setSelected(event_name in saved_instant)

        self.duration_events_list.blockSignals(False)
        self.instant_events_list.blockSignals(False)

        self._last_event_signature = signature
        self._updating_events = False

        self._update_nested_mode_availability()
        self._refresh_nested_groups_editor()

    def _update_nested_mode_availability(self) -> None:
        available = self._nested_mode_available()
        self.nested_mode_button.setEnabled(available)

        if available:
            self.nested_mode_button.setToolTip(
                "Create relationships between a base duration event and nested duration or instant events."
            )
        else:
            self.nested_mode_button.setToolTip(
                "Nested mode requires at least one duration event in addition to the full-signal event."
            )

        if not available and self.nested_mode_button.isChecked():
            self._updating_mode = True
            self.independent_mode_button.setChecked(True)
            self._updating_mode = False
            self.state["segmentation"]["nested_groups"] = []

    def _current_event_selection(self) -> tuple[list[str], list[str]]:
        duration = [item.text() for item in self.duration_events_list.selectedItems()]
        instant = [item.text() for item in self.instant_events_list.selectedItems()]
        return duration, instant

    def _independent_event_changed(self, group: str) -> None:
        if self._updating_events or self._current_segmentation_mode() != "independent":
            return

        duration_events, instant_events = self._current_event_selection()
        if group == "duration" and duration_events:
            self._clear_event_group("instant")
        elif group == "instant" and instant_events:
            self._clear_event_group("duration")

        self._sync()

    def _segmentation_mode_changed(self, checked: bool) -> None:
        if self._updating_mode or not checked:
            return

        if self.nested_mode_button.isChecked() and not self._nested_mode_available():
            self._updating_mode = True
            self.independent_mode_button.setChecked(True)
            self._updating_mode = False

        self._sync()

    def _epoch_scope_changed(self, checked: bool) -> None:
        if self._updating_epoch_scope or not checked:
            return

        self._sync()

    def _current_epoch_parameter_scope(self) -> str:
        return "duration" if self.duration_epoch_scope_button.isChecked() else "instant"

    def _nested_groups(self) -> list[dict[str, Any]]:
        return self.state["segmentation"].setdefault("nested_groups", [])

    def _add_base_events(self) -> None:
        duration_events, _ = self._event_names()
        existing_bases = {
            group.get("base_event")
            for group in self._nested_groups()
        }
        available_events = [
            event for event in duration_events if event not in existing_bases
        ]

        selected_events = self._select_multiple_events(
            title="Add base duration events",
            description="Select one or more duration events to use as bases.",
            events=available_events,
            kind="duration",
        )
        if not selected_events:
            return

        for event_name in selected_events:
            self._nested_groups().append(
                {
                    "base_event": event_name,
                    "nested_duration_events": [],
                    "nested_instant_events": [],
                }
            )

        self._sync()

    def _add_nested_events(self, base_event: str, kind: str) -> None:
        duration_events, instant_events = self._event_names()
        group = next(
            (
                nested_group
                for nested_group in self._nested_groups()
                if nested_group.get("base_event") == base_event
            ),
            None,
        )
        if group is None:
            return

        state_key = (
            "nested_duration_events"
            if kind == "duration"
            else "nested_instant_events"
        )
        already_selected = set(group.get(state_key) or [])

        if kind == "duration":
            available_events = [
                event
                for event in duration_events
                if event != base_event and event not in already_selected
            ]
            description = f"Select duration events contained within {base_event}."
            title = "Add nested duration events"
        else:
            available_events = [
                event
                for event in instant_events
                if event not in already_selected
            ]
            description = f"Select instant events contained within {base_event}."
            title = "Add nested instant events"

        selected_events = self._select_multiple_events(
            title=title,
            description=description,
            events=available_events,
            kind=kind,
        )
        if not selected_events:
            return

        group[state_key] = list(dict.fromkeys([
            *(group.get(state_key) or []),
            *selected_events,
        ]))
        self._sync()

    def _remove_base_event(self, base_event: str) -> None:
        self.state["segmentation"]["nested_groups"] = [
            group
            for group in self._nested_groups()
            if group.get("base_event") != base_event
        ]
        self._sync()

    def _remove_nested_event(
        self,
        base_event: str,
        event_name: str,
        kind: str,
    ) -> None:
        state_key = (
            "nested_duration_events"
            if kind == "duration"
            else "nested_instant_events"
        )
        for group in self._nested_groups():
            if group.get("base_event") == base_event:
                group[state_key] = [
                    event
                    for event in group.get(state_key) or []
                    if event != event_name
                ]
                break
        self._sync()

    def _select_multiple_events(
        self,
        title: str,
        description: str,
        events: list[str],
        kind: str,
    ) -> list[str]:
        if not events:
            return []

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(420)

        layout = QVBoxLayout(dialog)
        message = QLabel(description)
        message.setWordWrap(True)
        layout.addWidget(message)

        event_list = QListWidget()
        event_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        event_list.setMinimumHeight(180)
        event_list.setStyleSheet(
            self.duration_events_list.styleSheet()
            if kind == "duration"
            else self.instant_events_list.styleSheet()
        )
        event_list.addItems(events)
        layout.addWidget(event_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []

        return [item.text() for item in event_list.selectedItems()]

    def _refresh_nested_groups_editor(self) -> None:
        self._clear_layout(self.nested_groups_layout)
        nested_groups = self._nested_groups()

        if not nested_groups:
            empty = QLabel("No base events added.")
            empty.setObjectName("muted")
            self.nested_groups_layout.addWidget(empty)
            return

        for group in nested_groups:
            base_event = str(group.get("base_event", ""))
            card = QFrame()
            card.setProperty("role", "surface-panel")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(10)

            header = QHBoxLayout()
            header.addWidget(self._summary_chip(base_event, "duration", removable=False))
            header.addStretch()

            remove_base_button = QPushButton("Remove base")
            remove_base_button.clicked.connect(
                lambda _=False, event=base_event: self._remove_base_event(event)
            )
            header.addWidget(remove_base_button)
            card_layout.addLayout(header)

            children_row = QHBoxLayout()
            nested_duration = list(group.get("nested_duration_events") or [])
            nested_instant = list(group.get("nested_instant_events") or [])

            for event_name in nested_duration:
                children_row.addWidget(
                    self._summary_chip(
                        event_name,
                        "duration",
                        removable=True,
                        on_remove=lambda event=event_name, base=base_event: self._remove_nested_event(
                            base,
                            event,
                            "duration",
                        ),
                    )
                )

            for event_name in nested_instant:
                children_row.addWidget(
                    self._summary_chip(
                        event_name,
                        "instant",
                        removable=True,
                        on_remove=lambda event=event_name, base=base_event: self._remove_nested_event(
                            base,
                            event,
                            "instant",
                        ),
                    )
                )

            if not nested_duration and not nested_instant:
                empty = QLabel("No nested events selected.")
                empty.setObjectName("muted")
                children_row.addWidget(empty)

            children_row.addStretch()
            card_layout.addLayout(children_row)

            actions = QHBoxLayout()
            add_duration_button = QPushButton("+ Add duration event")
            add_instant_button = QPushButton("+ Add instant event")

            add_duration_button.clicked.connect(
                lambda _=False, base=base_event: self._add_nested_events(base, "duration")
            )
            add_instant_button.clicked.connect(
                lambda _=False, base=base_event: self._add_nested_events(base, "instant")
            )

            actions.addWidget(add_duration_button)
            actions.addWidget(add_instant_button)
            actions.addStretch()
            card_layout.addLayout(actions)

            self.nested_groups_layout.addWidget(card)

    def _nested_event_types(self) -> tuple[bool, bool]:
        has_duration = any(
            group.get("nested_duration_events")
            for group in self._nested_groups()
        )
        has_instant = any(
            group.get("nested_instant_events")
            for group in self._nested_groups()
        )
        return has_duration, has_instant

    def _nested_event_counts(self) -> tuple[int, int]:
        duration_count = sum(
            len(group.get("nested_duration_events") or [])
            for group in self._nested_groups()
        )
        instant_count = sum(
            len(group.get("nested_instant_events") or [])
            for group in self._nested_groups()
        )
        return duration_count, instant_count

    def _nested_epoch_type_mode(self) -> str:
        has_duration, has_instant = self._nested_event_types()
        if has_duration and has_instant:
            return "mixed"
        if has_duration:
            return "duration"
        if has_instant:
            return "instant"
        return "none"

    @staticmethod
    def _set_visible(widgets: list[QWidget], visible: bool) -> None:
        for widget in widgets:
            widget.setVisible(visible)

    def _set_dependent_enabled(self, mode: str) -> None:
        independent = mode == "independent"
        nested = mode == "nested"

        self.independent_panel.setVisible(independent)
        self.nested_panel.setVisible(nested)

        if independent:
            self.epoch_scope_panel.setVisible(False)
            duration_events, instant_events = self._current_event_selection()
            visible_duration_epochs = bool(duration_events)
            visible_instant_epochs = bool(instant_events)
        else:
            epoch_type_mode = self._nested_epoch_type_mode()
            selected_scope = self._current_epoch_parameter_scope()
            show_scope_buttons = epoch_type_mode == "mixed"
            self.epoch_scope_panel.setVisible(True)
            self.epoch_scope_buttons.setVisible(show_scope_buttons)

            if epoch_type_mode == "none":
                visible_duration_epochs = False
                visible_instant_epochs = False
                self.epoch_scope_message.setText(
                    "Add nested events to define the epoch parameter type."
                )
            elif epoch_type_mode == "instant":
                visible_duration_epochs = False
                visible_instant_epochs = True
                self.epoch_scope_message.setText(
                    "Epoch parameters apply to instant nested events."
                )
            elif epoch_type_mode == "duration":
                visible_duration_epochs = True
                visible_instant_epochs = False
                self.epoch_scope_message.setText(
                    "Epoch parameters apply to duration nested events."
                )
            else:
                visible_duration_epochs = selected_scope == "duration"
                visible_instant_epochs = selected_scope == "instant"
                self.epoch_scope_message.setText(
                    "Mixed nested event types detected. Select the parameter set to edit."
                )

        normalization = self.normalization_enabled.isChecked()
        thresholding = self.threshold_enabled.isChecked()
        resampling = self.resampling_enabled.isChecked()

        self._set_visible(
            [
                self.epoch_start_label,
                self.epoch_start,
                self.epoch_end_label,
                self.epoch_end,
            ],
            visible_instant_epochs,
        )
        self._set_visible(
            [
                self.duration_epoch_length_label,
                self.duration_epoch_length,
                self.stride_label,
                self.stride,
            ],
            visible_duration_epochs,
        )

        baseline_visible = normalization and visible_instant_epochs
        self._set_visible(
            [
                self.baseline_start_label,
                self.baseline_start,
                self.baseline_end_label,
                self.baseline_end,
            ],
            baseline_visible,
        )

        self.normalization_mode.setEnabled(normalization)
        self.baseline_start.setEnabled(baseline_visible)
        self.baseline_end.setEnabled(baseline_visible)

        for widget in (
            self.threshold_sigma,
            self.threshold_samples,
            self.threshold_channels,
        ):
            widget.setEnabled(thresholding)

        self.target_sampling_frequency.setEnabled(resampling)

        if independent:
            self.mode_help.setText(
                "Select either duration events or instant events. The two lists are mutually exclusive."
            )
        else:
            self.mode_help.setText(
                "Create explicit parent-child relationships between base duration events and nested events."
            )

    def _refresh_status_style(self) -> None:
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _update_status_label(
        self,
        mode: str,
        duration_events: list[str],
        instant_events: list[str],
    ) -> None:
        available_duration_events, available_instant_events = self._event_names()

        if not available_duration_events and not available_instant_events:
            text = "Load and select a BIDS configuration first."
            status = "idle"
        elif self.validation_errors:
            text = self.validation_errors[0]
            status = "idle"
        elif mode == "nested":
            nested_groups = self._nested_groups()
            nested_duration_count, nested_instant_count = self._nested_event_counts()
            relation_count = sum(
                len(group.get("nested_duration_events") or [])
                + len(group.get("nested_instant_events") or [])
                for group in nested_groups
            )
            event_type_text = (
                "mixed nested event types"
                if nested_duration_count and nested_instant_count
                else "duration nested events"
                if nested_duration_count
                else "instant nested events"
                if nested_instant_count
                else "no nested event type"
            )
            text = (
                f"{len(nested_groups)} nested group(s) with "
                f"{relation_count} relationship(s) configured: {event_type_text}."
            )
            status = "ready"
        elif duration_events:
            text = f"{len(duration_events)} duration event(s) selected."
            status = "ready"
        elif instant_events:
            text = f"{len(instant_events)} instant event(s) selected."
            status = "ready"
        else:
            text = "Select at least one event."
            status = "idle"

        self.status_label.setText(text)
        self.status_label.setProperty("status", status)
        self._refresh_status_style()

    def _summary_chip(
        self,
        text: str,
        kind: str,
        removable: bool = False,
        on_remove: Any | None = None,
    ) -> QFrame:
        chip = QFrame()
        chip.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Preferred,
        )

        if kind == "duration":
            chip.setObjectName("summaryDurationChip")
            chip.setStyleSheet("""
                QFrame#summaryDurationChip {
                    background: rgba(227, 90, 130, 28);
                    border: 1px solid rgba(227, 90, 130, 92);
                    border-radius: 9px;
                }
                QFrame#summaryDurationChip QLabel,
                QFrame#summaryDurationChip QPushButton {
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
                QFrame#summaryInstantChip QLabel,
                QFrame#summaryInstantChip QPushButton {
                    background: transparent;
                    border: none;
                    color: #9BE7E8;
                    font-weight: 600;
                }
            """)

        layout = QHBoxLayout(chip)
        layout.setContentsMargins(10, 6, 8 if removable else 10, 6)
        layout.setSpacing(5)

        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)

        if removable and on_remove is not None:
            remove_button = QPushButton("×")
            remove_button.setFixedWidth(22)
            remove_button.setToolTip(f"Remove {text}")
            remove_button.clicked.connect(on_remove)
            layout.addWidget(remove_button)

        return chip

    def _refresh_summary(
        self,
        mode: str,
        duration_events: list[str],
        instant_events: list[str],
    ) -> None:
        self._clear_layout(self.summary_layout)

        if mode == "nested":
            nested_groups = self._nested_groups()
            if not nested_groups:
                empty = QLabel("No nested groups configured.")
                empty.setObjectName("muted")
                self.summary_layout.addWidget(empty)
                return

            for group in nested_groups:
                base_event = str(group.get("base_event", ""))
                card = QFrame()
                card.setProperty("role", "surface-panel")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(14, 12, 14, 12)

                card_layout.addWidget(
                    self._summary_chip(base_event, "duration")
                )

                children = QHBoxLayout()
                nested_duration = list(group.get("nested_duration_events") or [])
                nested_instant = list(group.get("nested_instant_events") or [])

                for event_name in nested_duration:
                    children.addWidget(self._summary_chip(event_name, "duration"))

                for event_name in nested_instant:
                    children.addWidget(self._summary_chip(event_name, "instant"))

                if not nested_duration and not nested_instant:
                    empty = QLabel("No nested events selected.")
                    empty.setObjectName("muted")
                    children.addWidget(empty)

                children.addStretch()
                card_layout.addLayout(children)
                self.summary_layout.addWidget(card)
            return

        if not (duration_events or instant_events):
            empty = QLabel("No events selected.")
            empty.setObjectName("muted")
            self.summary_layout.addWidget(empty)
            return

        row = QHBoxLayout()
        chip_kind = "duration" if duration_events else "instant"
        for event_name in duration_events + instant_events:
            row.addWidget(self._summary_chip(event_name, chip_kind))
        row.addStretch()
        self.summary_layout.addLayout(row)

    def _sync(self, *_: Any) -> None:
        mode = self._current_segmentation_mode()
        duration_events, instant_events = self._current_event_selection()

        if mode == "nested":
            selected_duration_events: list[str] = []
            selected_instant_events: list[str] = []
        else:
            selected_duration_events = duration_events
            selected_instant_events = instant_events

        self.state["segmentation"] = {
            "segmentation_mode": mode,
            "selection_mode": (
                "nested"
                if mode == "nested"
                else "duration"
                if selected_duration_events
                else "instant"
                if selected_instant_events
                else "none"
            ),
            "selected_duration_events": selected_duration_events,
            "selected_instant_events": selected_instant_events,
            "nested_groups": deepcopy(self._nested_groups()),
            "nested_epoch_parameter_scope": self._current_epoch_parameter_scope(),
            "epoch_window_ms": {
                "start": self.epoch_start.value(),
                "end": self.epoch_end.value(),
            },
            "duration_epoch_length_ms": self.duration_epoch_length.value(),
            "stride_percent": self.stride.value(),
            "average_epochs": self.average_epochs.isChecked(),
            "normalization": {
                "enabled": self.normalization_enabled.isChecked(),
                "mode": self.normalization_mode.currentData(),
                "baseline_window_ms": {
                    "start": self.baseline_start.value(),
                    "end": self.baseline_end.value(),
                },
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
        self._refresh_nested_groups_editor()
        self._refresh_summary(mode, selected_duration_events, selected_instant_events)
        self.validation_errors = self._validate()
        self._update_status_label(mode, selected_duration_events, selected_instant_events)
        self.changed.emit()

    def _validate(self) -> list[str]:
        segmentation = self.state["segmentation"]
        mode = segmentation["segmentation_mode"]
        selection_mode = segmentation["selection_mode"]
        errors: list[str] = []

        if mode == "nested":
            if not self._nested_mode_available():
                errors.append(
                    "Nested mode requires at least one duration event in addition to the full-signal event."
                )
            else:
                nested_groups = segmentation.get("nested_groups") or []
                errors.extend(
                    self.validation.validate_many(
                        nested_groups,
                        [
                            (
                                "minimum_length",
                                {
                                    "minimum": 1,
                                    "item_name": "base duration event",
                                    "action": "add",
                                },
                            )
                        ],
                        label="Nested groups",
                    )
                )

                seen_bases: set[str] = set()
                for group in nested_groups:
                    base_event = group.get("base_event")
                    if not base_event:
                        errors.append("Nested group: base duration event is missing.")
                        continue
                    if base_event in seen_bases:
                        errors.append(
                            f"Nested groups: base event '{base_event}' is duplicated."
                        )
                    seen_bases.add(base_event)

                    nested_duration = list(
                        group.get("nested_duration_events") or []
                    )
                    nested_instant = list(
                        group.get("nested_instant_events") or []
                    )

                    if base_event in nested_duration:
                        errors.append(
                            f"{base_event}: a base event cannot contain itself."
                        )
                    if not nested_duration and not nested_instant:
                        errors.append(
                            f"{base_event}: select at least one nested event."
                        )

        elif selection_mode == "duration":
            errors.extend(
                self.validation.validate_many(
                    segmentation["selected_duration_events"],
                    [
                        (
                            "minimum_length",
                            {
                                "minimum": 1,
                                "item_name": "duration event",
                                "action": "select",
                            },
                        )
                    ],
                    label="Duration events",
                )
            )
        elif selection_mode == "instant":
            errors.extend(
                self.validation.validate_many(
                    segmentation["selected_instant_events"],
                    [
                        (
                            "minimum_length",
                            {
                                "minimum": 1,
                                "item_name": "instant event",
                                "action": "select",
                            },
                        )
                    ],
                    label="Instant events",
                )
            )
        else:
            errors.append("Signal events: select at least one event.")

        has_duration_epochs: bool
        has_instant_epochs: bool
        if mode == "nested":
            has_duration_epochs, has_instant_epochs = self._nested_event_types()
        else:
            has_duration_epochs = selection_mode == "duration"
            has_instant_epochs = selection_mode == "instant"

        start = segmentation["epoch_window_ms"]["start"]
        end = segmentation["epoch_window_ms"]["end"]

        if has_instant_epochs:
            errors.extend(
                self.validation.validate_many(
                    start,
                    ["integer"],
                    label="Epoch start",
                )
            )
            errors.extend(
                self.validation.validate_many(
                    end,
                    ["integer"],
                    label="Epoch end",
                )
            )
            if end <= start:
                errors.append("Epoch window: end must be greater than start.")

        if has_duration_epochs:
            errors.extend(
                self.validation.validate_many(
                    segmentation["duration_epoch_length_ms"],
                    ["integer", ("greater_than", {"minimum": 0, "suffix": " ms"})],
                    label="Epoch length",
                    stop_on_first_error=False,
                )
            )
            errors.extend(
                self.validation.validate_many(
                    segmentation["stride_percent"],
                    [
                        "integer",
                        ("greater_or_equal", {"minimum": 0, "suffix": " %"}),
                        ("less_or_equal", {"maximum": 100, "suffix": " %"}),
                    ],
                    label="Stride",
                    stop_on_first_error=False,
                )
            )

        normalization = segmentation["normalization"]
        if normalization["enabled"]:
            errors.extend(
                self.validation.validate_many(
                    normalization["mode"],
                    [("one_of", {"options": ["mean", "mean_std"]})],
                    label="Normalization mode",
                )
            )

            if has_instant_epochs:
                base_start = normalization["baseline_window_ms"]["start"]
                base_end = normalization["baseline_window_ms"]["end"]

                if base_end <= base_start:
                    errors.append(
                        "Baseline window: end must be greater than start."
                    )
                if base_start < start or base_end > end:
                    errors.append(
                        "Baseline window must be inside the epoch window."
                    )

        epoch_lengths_ms: list[int] = []
        if has_duration_epochs:
            epoch_lengths_ms.append(segmentation["duration_epoch_length_ms"])
        if has_instant_epochs and end > start:
            epoch_lengths_ms.append(end - start)

        smallest_epoch_ms = min(epoch_lengths_ms) if epoch_lengths_ms else 0
        epoch_samples = (
            int(
                smallest_epoch_ms
                * float(self.source_sampling_frequency or 0)
                / 1000
            )
            if smallest_epoch_ms > 0
            else 0
        )

        n_channels = int(
            (self.state.get("metadata") or {}).get("n_channels") or 0
        )
        thresholding = segmentation["thresholding"]

        if thresholding["enabled"]:
            errors.extend(
                self.validation.validate_many(
                    thresholding["sigma"],
                    ["finite_number", ("greater_than", {"minimum": 0})],
                    label="Threshold sigma",
                    stop_on_first_error=False,
                )
            )
            errors.extend(
                self.validation.validate_many(
                    thresholding["samples"],
                    ["integer", ("greater_or_equal", {"minimum": 1})],
                    label="Threshold samples",
                    stop_on_first_error=False,
                )
            )
            errors.extend(
                self.validation.validate_many(
                    thresholding["channels"],
                    ["integer", ("greater_or_equal", {"minimum": 1})],
                    label="Threshold channels",
                    stop_on_first_error=False,
                )
            )

            if epoch_samples and thresholding["samples"] > epoch_samples:
                errors.append(
                    "Threshold samples cannot exceed the smallest configured epoch sample count."
                )
            if n_channels and thresholding["channels"] > n_channels:
                errors.append(
                    "Threshold channels cannot exceed the loaded channel count."
                )

        resampling = segmentation["resampling"]
        if resampling["enabled"]:
            target = resampling["target_sampling_frequency"]
            errors.extend(
                self.validation.validate_many(
                    target,
                    [
                        "integer",
                        ("greater_or_equal", {"minimum": 250, "suffix": " Hz"}),
                    ],
                    label="Target sample frequency",
                    stop_on_first_error=False,
                )
            )

            if self.source_sampling_frequency is not None:
                errors.extend(
                    self.validation.validate_many(
                        target,
                        [
                            (
                                "less_or_equal",
                                {
                                    "maximum": self.source_sampling_frequency,
                                    "suffix": " Hz",
                                },
                            )
                        ],
                        label="Target sample frequency",
                    )
                )

        return errors

    def on_step_activated(self) -> None:
        metadata = self.state.get("metadata") or {}
        self.source_sampling_frequency = metadata.get("sampling_frequency")

        if self.source_sampling_frequency is not None:
            self.target_sampling_frequency.setMaximum(
                max(250, int(self.source_sampling_frequency))
            )

        self._refresh_events()
        self._sync()

    def can_continue(self) -> bool:
        return not self.validation_errors


__all__ = ["EEGSegmentationWidget"]
