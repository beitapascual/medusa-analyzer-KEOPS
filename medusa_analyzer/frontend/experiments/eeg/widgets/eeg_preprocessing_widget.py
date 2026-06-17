from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from medusa_analyzer.frontend.widgets.filtering import (FilterControls, FilterPreviewPlot, build_filter_defaults,
    compute_filter_response, filter_response_error)
from medusa_analyzer.frontend.experiments.eeg.widgets.frequency_bands_table import (
    EEGFrequencyBandsTable)

class EEGPreprocessingWidget(QScrollArea):
    changed = Signal()
    _minimum_band_frequency = 0.1

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        _ = experiment_info
        self.config = defaults.get("preprocessing", {})
        self.state = state

        self.default_frequency_bands = self._build_default_frequency_bands()
        existing_values = self.state.get("preprocessing") or {}
        if not existing_values:
            existing_values = self._build_default_state()
            self.state["preprocessing"] = existing_values
        self.values = existing_values

        title = "Pre-processing"
        description = "Tune the defaults that will be applied to the EEG recording."

        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(4, 4, 12, 4)
        root.setSpacing(16)

        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        subtitle = QLabel(description)
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(subtitle)
        root.addSpacing(16)

        car_panel = QFrame()
        car_panel.setProperty("role", "surface-panel")
        car_layout = QVBoxLayout(car_panel)
        self.car_checkbox = QCheckBox("Apply common average reference (CAR)")
        self.car_checkbox.setChecked(bool(self.values.get("car_checked", False)))
        car_layout.addWidget(self.car_checkbox)
        root.addWidget(car_panel)

        filters_grid = QGridLayout()
        filters_grid.setContentsMargins(0, 0, 0, 0)
        filters_grid.setHorizontalSpacing(16)
        filters_grid.setVerticalSpacing(16)
        filters_grid.setColumnStretch(0, 5)
        filters_grid.setColumnStretch(1, 7)
        filters_grid.setRowStretch(0, 1)
        filters_grid.setRowStretch(1, 1)
        filter_options = self.config.get("filter_options", {})
        families = filter_options.get("families", ["FIR", "IIR"])
        fir = filter_options.get("fir", {})
        iir = filter_options.get("iir", {})

        self.notch = FilterControls("Notch filter", self.values["notch"], families,
            fir, iir,"bandstop")
        self.bandpass = FilterControls("Bandpass filter", self.values["bandpass"], families,
            fir, iir,"bandpass")
        self.notch.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.bandpass.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.notch_plot_panel = self._build_filter_plot_panel("Notch filter response",
            "notch_plot")
        self.bandpass_plot_panel = self._build_filter_plot_panel("Bandpass filter response",
            "bandpass_plot")

        filters_grid.addWidget(self.notch, 0, 0)
        filters_grid.addWidget(self.notch_plot_panel, 0, 1)
        filters_grid.addWidget(self.bandpass, 1, 0)
        filters_grid.addWidget(self.bandpass_plot_panel, 1, 1)
        root.addLayout(filters_grid)

        bands_panel = QFrame()
        bands_panel.setProperty("role", "surface-panel")
        bands_layout = QVBoxLayout(bands_panel)
        bands_layout.setContentsMargins(24, 20, 24, 20)
        bands_title = QLabel("Frequency bands")
        bands_title.setObjectName("panelTitle")
        bands_layout.addWidget(bands_title)
        self.bands = EEGFrequencyBandsTable(self.values["frequency_bands"],
            default_rows=self.default_frequency_bands)
        bands_layout.addWidget(self.bands)
        root.addWidget(bands_panel)
        root.addStretch()

        self.setWidget(content)
        self.car_checkbox.toggled.connect(self._sync)
        self.notch.changed.connect(self._sync)
        self.bandpass.changed.connect(self._sync)
        self.bands.changed.connect(self._sync)
        self._sync()

    def _build_default_state(self) -> dict[str, Any]:
        filter_options = self.config.get("filter_options", {})
        return {
            "car_checked": bool(self.config.get("car", {}).get("checked_by_default", False)),
            "notch": build_filter_defaults(self.config.get("notch", {}),
                filter_options,
                "bandstop",
            ),
            "bandpass": build_filter_defaults(
                self.config.get("bandpass", {}),
                filter_options,
                "bandpass",
            ),
            "frequency_bands": self._build_default_frequency_bands(),
        }

    def _build_filter_plot_panel(self, title: str, plot_attribute: str) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        panel.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 20, 24, 20)
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        plot = FilterPreviewPlot()
        setattr(self, plot_attribute, plot)
        panel_layout.addWidget(title_label)
        panel_layout.addWidget(plot)
        return panel

    def _build_default_frequency_bands(self) -> list[dict[str, Any]]:
        bands: list[dict[str, Any]] = []
        for band in self.config.get("bands", {}).get("available", []):
            band_copy = deepcopy(band)
            band_copy["enabled"] = bool(band_copy.get("checked_by_default", True))
            band_copy["low_cut"] = float(
                band_copy.get(
                    "low_cut",
                    band_copy.get("low", self._minimum_band_frequency),
                )
            )
            band_copy["high_cut"] = float(
                band_copy.get(
                    "high_cut",
                    band_copy.get(
                        "high",
                        max(self._minimum_band_frequency + 0.1, 1.0),
                    ),
                )
            )
            bands.append(band_copy)
        return bands

    def _sync(self) -> None:
        self.values["car_checked"] = self.car_checkbox.isChecked()
        fs = 1000.0
        metadata_list = self.state.get("metadata_list") or []
        sampling_rates = [metadata.sampling_rate for metadata in metadata_list
            if metadata.sampling_rate is not None and metadata.sampling_rate > 0]
        if sampling_rates:
            fs = min(sampling_rates)
        else:
            metadata = self.state.get("metadata")
            if (metadata is not None and metadata.sampling_rate is not None
                and metadata.sampling_rate > 0):
                fs = metadata.sampling_rate

        notch_response = compute_filter_response(self.values["notch"], fs, "bandstop")
        bandpass_response = compute_filter_response(self.values["bandpass"], fs,"bandpass")
        maximum_band_frequency = fs / 2
        if self.values["bandpass"].get("enabled", True):
            try:
                bandpass_high_cut = float(self.values["bandpass"].get("high_cut", maximum_band_frequency))
            except (TypeError, ValueError):
                bandpass_high_cut = maximum_band_frequency
            if math.isfinite(bandpass_high_cut) and bandpass_high_cut > 0:
                maximum_band_frequency = min(maximum_band_frequency, bandpass_high_cut)
        self.bands.set_frequency_bounds(
            minimum_frequency=self._minimum_band_frequency,
            maximum_frequency=maximum_band_frequency,
            emit_changed=False,
        )
        self.notch_plot.set_response(notch_response, (filter_response_error(self.values["notch"], fs)
                if notch_response is None else None))
        self.bandpass_plot.set_response(bandpass_response, (filter_response_error(self.values["bandpass"], fs)
                if bandpass_response is None else None))
        self.changed.emit()

    def on_step_activated(self) -> None:
        self._sync()

    def can_continue(self) -> bool:
        return self.bands.is_valid()

__all__ = ["EEGPreprocessingWidget"]
