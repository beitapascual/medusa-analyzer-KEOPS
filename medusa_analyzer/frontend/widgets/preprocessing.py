from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from scipy import signal

from medusa_analyzer.frontend.widgets.filter_preview_plot import FilterPreviewPlot, FilterResponse
from medusa_analyzer.frontend.widgets.frequency_band_editor import FrequencyBandEditor


def _normalize_choice(choice: Any) -> tuple[str, str]:
    if isinstance(choice, dict):
        return str(choice["id"]), str(choice.get("title", choice["id"]))
    return str(choice), str(choice).replace("_", " ").title()


def _build_filter_defaults(config: dict[str, Any]) -> dict[str, Any]:
    fir = config.get("fir", {})
    iir = config.get("iir", {})
    return {
        "enabled": bool(config.get("checked_by_default", config.get("enabled", True))),
        "low_cut": float(config.get("default_low_cut", 0.5)),
        "high_cut": float(config.get("default_high_cut", 60.0)),
        "filter_type": str(config.get("default_family", "FIR")).lower(),
        "fir_order": int(fir.get("default_order", 101)),
        "fir_window": str(fir.get("default_window", "hamming")),
        "iir_order": int(iir.get("default_order", 4)),
        "iir_design": str(iir.get("default_design", "butter")),
        "iir_rp_db": float(iir.get("default_rp_db", 1.0)),
        "iir_rs_db": float(iir.get("default_rs_db", 40.0)),
    }


def _compute_filter_response(config: dict[str, Any], fs: float) -> FilterResponse | None:
    if not config.get("enabled", True):
        return FilterResponse([0.0, fs / 2], [0.0, 0.0])

    low_cut = float(config["low_cut"])
    high_cut = float(config["high_cut"])
    filter_type = str(config["filter_type"]).lower()
    is_notch = low_cut > 20 and high_cut - low_cut < 10

    try:
        if filter_type == "fir":
            coefficients = signal.firwin(
                int(config["fir_order"]),
                [low_cut, high_cut],
                pass_zero="bandstop" if is_notch else False,
                fs=fs,
                window=str(config["fir_window"]),
            )
            frequencies, response = signal.freqz(coefficients, worN=1024, fs=fs)
        else:
            iir_kwargs = {}
            design = str(config["iir_design"])
            if design in {"cheby1", "ellip"}:
                iir_kwargs["rp"] = float(config["iir_rp_db"])
            if design in {"cheby2", "ellip"}:
                iir_kwargs["rs"] = float(config["iir_rs_db"])
            coefficients = signal.iirfilter(
                int(config["iir_order"]),
                [low_cut, high_cut],
                btype="bandstop" if is_notch else "bandpass",
                fs=fs,
                ftype=design,
                output="sos",
                **iir_kwargs,
            )
            frequencies, response = signal.sosfreqz(coefficients, worN=1024, fs=fs)
    except (ValueError, TypeError):
        return None

    magnitude = 20 * np.log10(np.maximum(np.abs(response), 1e-8))
    return FilterResponse(frequencies.tolist(), magnitude.tolist())


class FilterControls(QFrame):
    changed = Signal()

    def __init__(self, title: str, config: dict[str, Any], families: list[str], fir: dict[str, Any], iir: dict[str, Any]):
        super().__init__()
        self.config = config
        self.families = families
        self.fir = fir
        self.iir = iir
        self.setProperty("role", "filter-controls")
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)

        self.enabled = QCheckBox(title)
        self.enabled.setObjectName("controlTitle")
        self.enabled.setChecked(bool(config.get("enabled", True)))
        root.addWidget(self.enabled)

        grid = QGridLayout()
        self.low = self._double(float(config.get("low_cut", 0.5)))
        self.high = self._double(float(config.get("high_cut", 60.0)))
        self.kind = QComboBox()
        for family in families:
            self.kind.addItem(str(family))
        self.kind.setCurrentText(str(config.get("filter_type", "fir")).upper())
        grid.addWidget(QLabel("Low cut"), 0, 0)
        grid.addWidget(self.low, 1, 0)
        grid.addWidget(QLabel("High cut"), 0, 1)
        grid.addWidget(self.high, 1, 1)
        grid.addWidget(QLabel("Type"), 0, 2)
        grid.addWidget(self.kind, 1, 2)
        root.addLayout(grid)

        self.parameters = QStackedWidget()

        fir_widget = QWidget()
        fir_layout = QGridLayout(fir_widget)
        fir_layout.setContentsMargins(0, 4, 0, 0)
        self.fir_order = QSpinBox()
        self.fir_order.setRange(3, 99999)
        self.fir_order.setSingleStep(2)
        self.fir_order.setValue(int(config.get("fir_order", fir.get("default_order", 101))))
        self.window = QComboBox()
        for window in fir.get("windows", []):
            self.window.addItem(str(window).title(), str(window))
        window_index = self.window.findData(str(config.get("fir_window", fir.get("default_window", "hamming"))))
        if window_index >= 0:
            self.window.setCurrentIndex(window_index)
        fir_layout.addWidget(QLabel("FIR order"), 0, 0)
        fir_layout.addWidget(QLabel("Window"), 0, 1)
        fir_layout.addWidget(self.fir_order, 1, 0)
        fir_layout.addWidget(self.window, 1, 1)

        iir_widget = QWidget()
        iir_layout = QGridLayout(iir_widget)
        iir_layout.setContentsMargins(0, 4, 0, 0)
        self.iir_order = QSpinBox()
        self.iir_order.setRange(1, 20)
        self.iir_order.setValue(int(config.get("iir_order", iir.get("default_order", 4))))
        self.design = QComboBox()
        for design in iir.get("designs", []):
            design_id, design_title = _normalize_choice(design)
            self.design.addItem(design_title, design_id)
        design_index = self.design.findData(str(config.get("iir_design", iir.get("default_design", "butter"))))
        if design_index >= 0:
            self.design.setCurrentIndex(design_index)
        self.iir_rp = QDoubleSpinBox()
        self.iir_rp.setRange(0.1, 20.0)
        self.iir_rp.setDecimals(2)
        self.iir_rp.setValue(float(config.get("iir_rp_db", iir.get("default_rp_db", 1.0))))
        self.iir_rp.setSuffix(" dB")
        self.iir_rs = QDoubleSpinBox()
        self.iir_rs.setRange(1.0, 200.0)
        self.iir_rs.setDecimals(1)
        self.iir_rs.setValue(float(config.get("iir_rs_db", iir.get("default_rs_db", 40.0))))
        self.iir_rs.setSuffix(" dB")
        iir_layout.addWidget(QLabel("IIR order"), 0, 0)
        iir_layout.addWidget(QLabel("Design"), 0, 1)
        iir_layout.addWidget(self.iir_order, 1, 0)
        iir_layout.addWidget(self.design, 1, 1)
        iir_layout.addWidget(QLabel("Passband ripple"), 2, 0)
        iir_layout.addWidget(QLabel("Stopband attenuation"), 2, 1)
        iir_layout.addWidget(self.iir_rp, 3, 0)
        iir_layout.addWidget(self.iir_rs, 3, 1)

        self.parameters.addWidget(fir_widget)
        self.parameters.addWidget(iir_widget)
        root.addWidget(self.parameters)

        self.controls = [
            self.low,
            self.high,
            self.kind,
            self.fir_order,
            self.window,
            self.iir_order,
            self.design,
        ]
        self.enabled.toggled.connect(self._sync)
        self.kind.currentTextChanged.connect(self._sync)
        for control in (self.low, self.high):
            control.valueChanged.connect(self._sync)
        for control in (self.fir_order, self.iir_order):
            control.valueChanged.connect(self._sync)
        self.window.currentIndexChanged.connect(self._sync)
        self.design.currentIndexChanged.connect(self._sync)
        self.iir_rp.valueChanged.connect(self._sync)
        self.iir_rs.valueChanged.connect(self._sync)
        self._sync()

    @staticmethod
    def _double(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 10000)
        spin.setDecimals(1)
        spin.setValue(value)
        spin.setSuffix(" Hz")
        return spin

    def _sync(self) -> None:
        self.config["enabled"] = self.enabled.isChecked()
        self.config["low_cut"] = self.low.value()
        self.config["high_cut"] = self.high.value()
        self.config["filter_type"] = self.kind.currentText().lower()
        self.config["fir_order"] = self.fir_order.value()
        self.config["fir_window"] = self.window.currentData()
        self.config["iir_order"] = self.iir_order.value()
        self.config["iir_design"] = self.design.currentData()
        self.config["iir_rp_db"] = self.iir_rp.value()
        self.config["iir_rs_db"] = self.iir_rs.value()

        is_fir = self.config["filter_type"] == "fir"
        self.parameters.setCurrentIndex(0 if is_fir else 1)
        design = self.config["iir_design"]
        self.iir_rp.setEnabled(self.config["enabled"] and not is_fir and design in {"cheby1", "ellip"})
        self.iir_rs.setEnabled(self.config["enabled"] and not is_fir and design in {"cheby2", "ellip"})
        for control in self.controls:
            control.setEnabled(self.config["enabled"])
        self.changed.emit()


class PreprocessingWidget(QScrollArea):
    changed = Signal()

    def __init__(self, config: dict[str, Any], state: dict[str, Any], title: str, description: str):
        super().__init__()
        self.config = config
        self.state = state
        existing_values = self.state.get("preprocessing") or {}
        if not existing_values:
            existing_values = self._build_default_state()
            self.state["preprocessing"] = existing_values
        self.values = existing_values

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

        columns = QHBoxLayout()
        controls_column = QVBoxLayout()
        filters = self.config.get("filters", {})
        families = filters.get("families", ["FIR", "IIR"])
        fir = filters.get("fir", {})
        iir = filters.get("iir", {})

        self.notch = FilterControls("Notch filter", self.values["notch"], families, fir, iir)
        self.bandpass = FilterControls("Bandpass filter", self.values["bandpass"], families, fir, iir)
        controls_column.addWidget(self.notch)
        controls_column.addWidget(self.bandpass)
        columns.addLayout(controls_column, 5)

        plots = QVBoxLayout()
        for label, attribute in (
            ("Notch filter response", "notch_plot"),
            ("Bandpass filter response", "bandpass_plot"),
        ):
            panel = QFrame()
            panel.setProperty("role", "surface-panel")
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(24, 20, 24, 20)
            title_label = QLabel(label)
            title_label.setObjectName("panelTitle")
            plot = FilterPreviewPlot()
            setattr(self, attribute, plot)
            panel_layout.addWidget(title_label)
            panel_layout.addWidget(plot)
            plots.addWidget(panel)
        columns.addLayout(plots, 7)
        root.addLayout(columns)

        bands_panel = QFrame()
        bands_panel.setProperty("role", "surface-panel")
        bands_layout = QVBoxLayout(bands_panel)
        bands_layout.setContentsMargins(24, 20, 24, 20)
        bands_title = QLabel("Frequency bands")
        bands_title.setObjectName("panelTitle")
        bands_layout.addWidget(bands_title)
        self.bands = FrequencyBandEditor(self.values["frequency_bands"])
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
        bands = []
        for band in self.config.get("bands", {}).get("available", []):
            band_copy = deepcopy(band)
            band_copy["enabled"] = bool(band_copy.get("checked_by_default", True))
            band_copy["low_cut"] = float(band_copy.get("low_cut", band_copy.get("low", 0.0)))
            band_copy["high_cut"] = float(band_copy.get("high_cut", band_copy.get("high", 0.0)))
            bands.append(band_copy)
        return {
            "car_checked": bool(self.config.get("car", {}).get("checked_by_default", False)),
            "notch": _build_filter_defaults(self.config.get("notch", {})),
            "bandpass": _build_filter_defaults(self.config.get("bandpass", {})),
            "frequency_bands": bands,
        }

    def _sync(self) -> None:
        self.values["car_checked"] = self.car_checkbox.isChecked()
        fs = 1000.0
        metadata = self.state.get("metadata")
        if metadata is not None and metadata.sampling_rate is not None:
            fs = metadata.sampling_rate
        self.notch_plot.set_response(_compute_filter_response(self.values["notch"], fs))
        self.bandpass_plot.set_response(_compute_filter_response(self.values["bandpass"], fs))
        self.changed.emit()

    def can_continue(self) -> bool:
        return True
