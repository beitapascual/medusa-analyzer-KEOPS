from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from scipy import signal

from medusa_analyzer.frontend.widgets.filter_preview_plot import FilterPreviewPlot, FilterResponse
from medusa_analyzer.frontend.widgets.frequency_band_editor import FrequencyBandEditor


FilterMode = Literal["bandpass", "bandstop"]


def _normalize_choice(choice: Any) -> tuple[str, str]:
    if isinstance(choice, dict):
        return str(choice["id"]), str(choice.get("title", choice["id"]))
    return str(choice), str(choice).replace("_", " ").title()


def _normalize_fir_order(value: int, require_odd: bool = False) -> int:
    order = max(3, int(value))
    if require_odd and order % 2 == 0:
        order += 1
    return order


def _build_filter_defaults(
    config: dict[str, Any],
    filter_options: dict[str, Any],
    mode: FilterMode,
) -> dict[str, Any]:
    common_fir = filter_options.get("fir", {})
    specific_fir = config.get("fir", {})
    common_iir = filter_options.get("iir", {})
    specific_iir = config.get("iir", {})
    filter_type = str(config.get("default_family", "FIR")).lower()
    require_odd_fir_order = mode == "bandstop" and filter_type == "fir"
    return {
        "enabled": bool(config.get("checked_by_default", config.get("enabled", True))),
        "low_cut": float(config.get("default_low_cut", 0.5)),
        "high_cut": float(config.get("default_high_cut", 60.0)),
        "filter_type": filter_type,
        "fir_order": _normalize_fir_order(
            specific_fir.get(
                "default_order",
                common_fir.get("default_order", 101),
            ),
            require_odd=require_odd_fir_order,
        ),
        "fir_window": str(
            specific_fir.get(
                "default_window",
                common_fir.get("default_window", "hamming"),
            )
        ),
        "iir_order": int(
            specific_iir.get(
                "default_order",
                common_iir.get("default_order", 4),
            )
        ),
        "iir_design": str(
            specific_iir.get(
                "default_design",
                common_iir.get("default_design", "butter"),
            )
        ),
        "iir_rp_db": float(
            specific_iir.get(
                "default_rp_db",
                common_iir.get("default_rp_db", 1.0),
            )
        ),
        "iir_rs_db": float(
            specific_iir.get(
                "default_rs_db",
                common_iir.get("default_rs_db", 40.0),
            )
        ),
    }


def _compute_filter_response(
    config: dict[str, Any],
    fs: float,
    mode: FilterMode,
) -> FilterResponse | None:
    if not config.get("enabled", True):
        return FilterResponse([0.0, fs / 2], [0.0, 0.0])

    low_cut = float(config["low_cut"])
    high_cut = float(config["high_cut"])
    filter_type = str(config["filter_type"]).lower()
    if not 0 < low_cut < high_cut < fs / 2:
        return None

    try:
        if filter_type == "fir":
            numtaps = _normalize_fir_order(
                config["fir_order"],
                require_odd=mode == "bandstop",
            )
            window = str(config["fir_window"])
            coefficients = signal.firwin(
                numtaps,
                [low_cut, high_cut],
                pass_zero=mode == "bandstop",
                fs=fs,
                window=window,
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
                btype=mode,
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


def _filter_response_error(config: dict[str, Any], fs: float) -> str:
    low_cut = float(config["low_cut"])
    high_cut = float(config["high_cut"])
    nyquist = fs / 2
    if not 0 < low_cut < high_cut < nyquist:
        return (
            f"Cutoffs must satisfy 0 < low < high < {nyquist:g} Hz "
            f"(Nyquist limit for {fs:g} Hz sampling)."
        )
    return "Unable to design a response with the selected filter parameters."


class FilterControls(QFrame):
    changed = Signal()

    def __init__(
        self,
        title: str,
        config: dict[str, Any],
        families: list[str],
        fir: dict[str, Any],
        iir: dict[str, Any],
        mode: FilterMode,
    ):
        super().__init__()
        self.config = config
        self.families = families
        self.fir = fir
        self.iir = iir
        self.mode = mode
        self.setProperty("role", "filter-controls")
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
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

        self.parameters = QWidget()
        self.parameters.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed)

        parameters_layout = QVBoxLayout(self.parameters)
        parameters_layout.setContentsMargins(0, 0, 0, 0)
        parameters_layout.setSpacing(0)

        self.fir_widget = QWidget()
        self.fir_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        fir_layout = QGridLayout(self.fir_widget)
        fir_layout.setContentsMargins(0, 4, 0, 0)
        fir_layout.setHorizontalSpacing(12)
        fir_layout.setVerticalSpacing(6)
        fir_layout.setColumnStretch(0, 0)
        fir_layout.setColumnStretch(1, 0)
        fir_layout.setColumnStretch(2, 1)
        self.fir_order = QSpinBox()
        self.fir_order.setRange(0, 99999)
        self.fir_order.setSingleStep(1)
        self.fir_order.setValue(int(config.get("fir_order", fir.get("default_order", 101))))
        self.fir_order.setMaximumWidth(140)
        self.window = QComboBox()
        for window in fir.get("windows", []):
            window_id, window_title = _normalize_choice(window)
            self.window.addItem(window_title, window_id)
        window_index = self.window.findData(str(config.get("fir_window", fir.get("default_window", "hamming"))))
        if window_index >= 0:
            self.window.setCurrentIndex(window_index)
        self.window.setMaximumWidth(180)
        fir_layout.addWidget(QLabel("FIR order"), 0, 0)
        fir_layout.addWidget(QLabel("Window"), 0, 1)
        fir_layout.addWidget(self.fir_order, 1, 0)
        fir_layout.addWidget(self.window, 1, 1)

        self.iir_widget = QWidget()
        self.iir_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        iir_layout = QGridLayout(self.iir_widget)
        iir_layout.setContentsMargins(0, 4, 0, 0)
        iir_layout.setHorizontalSpacing(12)
        iir_layout.setVerticalSpacing(6)
        iir_layout.setColumnStretch(0, 0)
        iir_layout.setColumnStretch(1, 0)
        iir_layout.setColumnStretch(2, 1)
        self.iir_order = QSpinBox()
        self.iir_order.setRange(1, 20)
        self.iir_order.setValue(int(config.get("iir_order", iir.get("default_order", 4))))
        self.iir_order.setMaximumWidth(140)
        self.design = QComboBox()
        for design in iir.get("designs", []):
            design_id, design_title = _normalize_choice(design)
            self.design.addItem(design_title, design_id)
        design_index = self.design.findData(str(config.get("iir_design", iir.get("default_design", "butter"))))
        if design_index >= 0:
            self.design.setCurrentIndex(design_index)
        self.design.setMaximumWidth(180)
        self.iir_rp = QDoubleSpinBox()
        self.iir_rp.setRange(0.1, 20.0)
        self.iir_rp.setDecimals(2)
        self.iir_rp.setValue(float(config.get("iir_rp_db", iir.get("default_rp_db", 1.0))))
        self.iir_rp.setSuffix(" dB")
        self.iir_rp.setMaximumWidth(140)
        self.iir_rs = QDoubleSpinBox()
        self.iir_rs.setRange(1.0, 200.0)
        self.iir_rs.setDecimals(1)
        self.iir_rs.setValue(float(config.get("iir_rs_db", iir.get("default_rs_db", 40.0))))
        self.iir_rs.setSuffix(" dB")
        self.iir_rs.setMaximumWidth(180)
        iir_layout.addWidget(QLabel("IIR order"), 0, 0)
        iir_layout.addWidget(QLabel("Design"), 0, 1)
        iir_layout.addWidget(self.iir_order, 1, 0)
        iir_layout.addWidget(self.design, 1, 1)
        iir_layout.addWidget(QLabel("Passband ripple"), 2, 0)
        iir_layout.addWidget(QLabel("Stopband attenuation"), 2, 1)
        iir_layout.addWidget(self.iir_rp, 3, 0)
        iir_layout.addWidget(self.iir_rs, 3, 1)

        parameters_layout.addWidget(self.fir_widget)
        parameters_layout.addWidget(self.iir_widget)
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
        filter_type = self.kind.currentText().lower()
        require_odd_fir_order = self.mode == "bandstop" and filter_type == "fir"

        self.config["enabled"] = self.enabled.isChecked()
        self.config["low_cut"] = self.low.value()
        self.config["high_cut"] = self.high.value()
        self.config["filter_type"] = filter_type
        self.config["fir_order"] = _normalize_fir_order(
            self.fir_order.value(),
            require_odd=require_odd_fir_order,
        )
        self.config["fir_window"] = self.window.currentData()
        self.config["iir_order"] = self.iir_order.value()
        self.config["iir_design"] = self.design.currentData()
        self.config["iir_rp_db"] = self.iir_rp.value()
        self.config["iir_rs_db"] = self.iir_rs.value()

        is_fir = self.config["filter_type"] == "fir"

        self.fir_widget.setVisible(is_fir)
        self.iir_widget.setVisible(not is_fir)

        self.parameters.adjustSize()
        self.parameters.updateGeometry()
        self.adjustSize()
        self.updateGeometry()

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
        filter_options = self.config.get("filter_options", {})
        families = filter_options.get("families", ["FIR", "IIR"])
        fir = filter_options.get("fir", {})
        iir = filter_options.get("iir", {})

        self.notch = FilterControls(
            "Notch filter",
            self.values["notch"],
            families,
            fir,
            iir,
            "bandstop",
        )
        self.bandpass = FilterControls(
            "Bandpass filter",
            self.values["bandpass"],
            families,
            fir,
            iir,
            "bandpass",
        )
        controls_column.addWidget(self.notch)
        controls_column.addWidget(self.bandpass)
        controls_column.addStretch(1)
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
        filter_options = self.config.get("filter_options", {})
        return {
            "car_checked": bool(self.config.get("car", {}).get("checked_by_default", False)),
            "notch": _build_filter_defaults(
                self.config.get("notch", {}),
                filter_options,
                "bandstop",
            ),
            "bandpass": _build_filter_defaults(
                self.config.get("bandpass", {}),
                filter_options,
                "bandpass",
            ),
            "frequency_bands": bands,
        }

    def _sync(self) -> None:
        self.values["car_checked"] = self.car_checkbox.isChecked()
        fs = 1000.0
        metadata = self.state.get("metadata")
        if metadata is not None and metadata.sampling_rate is not None:
            fs = metadata.sampling_rate
        notch_response = _compute_filter_response(
            self.values["notch"],
            fs,
            "bandstop",
        )
        bandpass_response = _compute_filter_response(
            self.values["bandpass"],
            fs,
            "bandpass",
        )
        self.notch_plot.set_response(
            notch_response,
            _filter_response_error(self.values["notch"], fs)
            if notch_response is None
            else None,
        )
        self.bandpass_plot.set_response(
            bandpass_response,
            _filter_response_error(self.values["bandpass"], fs)
            if bandpass_response is None
            else None,
        )
        self.changed.emit()

    def on_step_activated(self) -> None:
        self._sync()

    def can_continue(self) -> bool:
        return True
