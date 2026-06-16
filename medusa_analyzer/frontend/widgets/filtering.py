from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from PySide6.QtCore import QPointF, Property, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from scipy import signal


FilterMode = Literal["bandpass", "bandstop"]


def normalize_choice(choice: Any) -> tuple[str, str]:
    if isinstance(choice, dict):
        return str(choice["id"]), str(choice.get("title", choice["id"]))
    return str(choice), str(choice).replace("_", " ").title()


def normalize_fir_order(value: int, require_odd: bool = False) -> int:
    order = max(3, int(value))
    if require_odd and order % 2 == 0:
        order += 1
    return order


def build_filter_defaults(config: dict[str, Any], filter_options: dict[str, Any],
    mode: FilterMode) -> dict[str, Any]:
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
        "fir_order": normalize_fir_order(specific_fir.get("default_order", common_fir.get("default_order", 101)),
            require_odd=require_odd_fir_order),
        "fir_window": str(specific_fir.get("default_window", common_fir.get("default_window", "hamming"))),
        "iir_order": int(specific_iir.get("default_order", common_iir.get("default_order", 4))),
        "iir_design": str(specific_iir.get("default_design", common_iir.get("default_design", "butter"))),
        "iir_rp_db": float(specific_iir.get("default_rp_db", common_iir.get("default_rp_db", 1.0))),
        "iir_rs_db": float(specific_iir.get("default_rs_db", common_iir.get("default_rs_db", 40.0)))}


@dataclass(frozen=True, slots=True)
class FilterResponse:
    frequencies: list[float]
    magnitude_db: list[float]


def compute_filter_response(config: dict[str, Any], fs: float, mode: FilterMode) -> FilterResponse | None:
    if not config.get("enabled", True):
        return FilterResponse([0.0, fs / 2], [0.0, 0.0])

    low_cut = float(config["low_cut"])
    high_cut = float(config["high_cut"])
    filter_type = str(config["filter_type"]).lower()
    if not 0 < low_cut < high_cut < fs / 2:
        return None

    try:
        if filter_type == "fir":
            numtaps = normalize_fir_order(config["fir_order"], require_odd=mode == "bandstop")
            window = str(config["fir_window"])
            coefficients = signal.firwin(numtaps,[low_cut, high_cut], pass_zero=mode == "bandstop",
                fs=fs, window=window)
            frequencies, response = signal.freqz(coefficients, worN=1024, fs=fs)
        else:
            iir_kwargs = {}
            design = str(config["iir_design"])
            if design in {"cheby1", "ellip"}:
                iir_kwargs["rp"] = float(config["iir_rp_db"])
            if design in {"cheby2", "ellip"}:
                iir_kwargs["rs"] = float(config["iir_rs_db"])
            coefficients = signal.iirfilter(int(config["iir_order"]), [low_cut, high_cut], btype=mode,
                fs=fs, ftype=design, output="sos", **iir_kwargs)
            frequencies, response = signal.sosfreqz(coefficients, worN=1024, fs=fs)
    except (ValueError, TypeError):
        return None

    magnitude = 20 * np.log10(np.maximum(np.abs(response), 1e-8))
    return FilterResponse(frequencies.tolist(), magnitude.tolist())


def filter_response_error(config: dict[str, Any], fs: float) -> str:
    low_cut = float(config["low_cut"])
    high_cut = float(config["high_cut"])
    nyquist = fs / 2
    if not 0 < low_cut < high_cut < nyquist:
        return ( f"Cutoffs must satisfy 0 < low < high < {nyquist:g} Hz "
            f"(Nyquist limit for {fs:g} Hz sampling).")
    return "Unable to design a response with the selected filter parameters."


class FilterPreviewPlot(QFrame):
    def __init__(self):
        super().__init__()
        self.setProperty("role", "plot")
        self.setMinimumHeight(225)
        self._plot_background_color = QColor("#FBFAF8")
        self._grid_color = QColor("#E5DFDD")
        self._axis_line_color = QColor("#B8B0B4")
        self._axis_text_color = QColor("#756F77")
        self._response_line_color = QColor("#0E7C86")
        self._empty_message_color = QColor("#756F77")
        self.response: FilterResponse | None = None
        self.empty_message = "Valid configuration required"

    def set_response(self, response: FilterResponse | None, empty_message: str | None = None) -> None:
        self.response = response
        self.empty_message = empty_message or "Valid configuration required"
        self.update()

    def _set_color(self, attribute: str, value) -> None:
        setattr(self, attribute, QColor(value))
        self.update()

    def get_plot_background_color(self) -> QColor:
        return self._plot_background_color

    def set_plot_background_color(self, value) -> None:
        self._set_color("_plot_background_color", value)

    def get_grid_color(self) -> QColor:
        return self._grid_color

    def set_grid_color(self, value) -> None:
        self._set_color("_grid_color", value)

    def get_axis_line_color(self) -> QColor:
        return self._axis_line_color

    def set_axis_line_color(self, value) -> None:
        self._set_color("_axis_line_color", value)

    def get_axis_text_color(self) -> QColor:
        return self._axis_text_color

    def set_axis_text_color(self, value) -> None:
        self._set_color("_axis_text_color", value)

    def get_response_line_color(self) -> QColor:
        return self._response_line_color

    def set_response_line_color(self, value) -> None:
        self._set_color("_response_line_color", value)

    def get_empty_message_color(self) -> QColor:
        return self._empty_message_color

    def set_empty_message_color(self, value) -> None:
        self._set_color("_empty_message_color", value)

    @staticmethod
    def _nice_step(value: float) -> float:
        if value <= 0:
            return 1.0
        exponent = math.floor(math.log10(value))
        fraction = value / 10 ** exponent
        if fraction <= 1:
            nice_fraction = 1
        elif fraction <= 2:
            nice_fraction = 2
        elif fraction <= 5:
            nice_fraction = 5
        else:
            nice_fraction = 10
        return nice_fraction * 10 ** exponent

    @classmethod
    def _frequency_ticks(cls, maximum_frequency: float, plot_width: float) -> tuple[float, list[float]]:
        target_intervals = max(2, min(6, int(plot_width // 72)))
        step = cls._nice_step(maximum_frequency / target_intervals)
        axis_maximum = max(step, math.ceil(maximum_frequency / step) * step)
        tick_count = int(round(axis_maximum / step))
        ticks = [index * step for index in range(tick_count + 1)]
        return axis_maximum, ticks

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self.rect().adjusted(48, 18, -18, -55)
        painter.fillRect(plot, self._plot_background_color)

        maximum_frequency = (max(self.response.frequencies) if self.response and self.response.frequencies else 1.0)
        axis_maximum, frequency_ticks = self._frequency_ticks(maximum_frequency, plot.width())

        painter.setPen(QPen(self._grid_color, 1))
        for index in range(5):
            y = plot.top() + plot.height() * index / 4
            painter.drawLine(plot.left(), int(y), plot.right(), int(y))

        for frequency in frequency_ticks:
            x = plot.left() + plot.width() * frequency / axis_maximum
            painter.drawLine(int(x), plot.top(), int(x), plot.bottom())

        painter.setPen(QPen(self._axis_line_color, 1))
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())

        axis_font = QFont(painter.font())
        axis_font.setPointSizeF(max(7.0, axis_font.pointSizeF() - 1.0))
        painter.setFont(axis_font)
        painter.setPen(self._axis_text_color)
        painter.drawText(QRectF(5, plot.top(), 38, 20), Qt.AlignmentFlag.AlignRight, "0 dB")
        painter.drawText(QRectF(5, plot.bottom() - 15, 38, 20), Qt.AlignmentFlag.AlignRight, "-80")

        for frequency in frequency_ticks:
            x = plot.left() + plot.width() * frequency / axis_maximum
            label_width = 58.0
            label_left = max(1.0, min(self.width() - label_width - 1.0, x - label_width / 2))
            painter.drawText(QRectF(label_left, plot.bottom() + 4, label_width, 17),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{frequency:g}")

        painter.drawText(plot.left(), plot.bottom() + 25, plot.width(), 20, Qt.AlignmentFlag.AlignCenter, "Frequency (Hz)")
        if not self.response or len(self.response.frequencies) < 2:
            painter.setPen(self._empty_message_color)
            painter.drawText(plot.adjusted(24, 24, -24, -24), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self.empty_message)
            return

        path = QPainterPath()
        for index, (frequency, magnitude) in enumerate(zip(self.response.frequencies, self.response.magnitude_db)):
            x = plot.left() + plot.width() * frequency / axis_maximum
            y = plot.bottom() - plot.height() * min(80, max(0, magnitude + 80)) / 80
            point = QPointF(x, y)
            path.moveTo(point) if index == 0 else path.lineTo(point)
        painter.setPen(QPen(self._response_line_color, 2.4))
        painter.drawPath(path)

    plotBackgroundColor = Property(QColor, get_plot_background_color, set_plot_background_color)
    gridColor = Property(QColor, get_grid_color, set_grid_color)
    axisLineColor = Property(QColor, get_axis_line_color, set_axis_line_color)
    axisTextColor = Property(QColor, get_axis_text_color, set_axis_text_color)
    responseLineColor = Property(QColor, get_response_line_color, set_response_line_color)
    emptyMessageColor = Property(QColor, get_empty_message_color, set_empty_message_color)


class FilterControls(QFrame):
    changed = Signal()

    def __init__(self, title: str, config: dict[str, Any], families: list[str], fir: dict[str, Any],
        iir: dict[str, Any], mode: FilterMode):
        super().__init__()
        self.config = config
        self.families = families
        self.fir = fir
        self.iir = iir
        self.mode = mode
        self.setProperty("role", "filter-controls")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
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
        self.parameters.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        parameters_layout = QVBoxLayout(self.parameters)
        parameters_layout.setContentsMargins(0, 0, 0, 0)
        parameters_layout.setSpacing(0)

        self.fir_widget = QWidget()
        self.fir_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
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
        self.fir_order.setValue(int(config.get("fir_order", fir.get("default_order", 1001))))
        self.fir_order.setMaximumWidth(140)
        self.window = QComboBox()
        for window in fir.get("windows", []):
            window_id, window_title = normalize_choice(window)
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
        self.iir_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
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
            design_id, design_title = normalize_choice(design)
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
        root.addStretch(1)

        self.controls = [self.low, self.high, self.kind, self.fir_order, self.window, self.iir_order, self.design]
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
        self.config["fir_order"] = normalize_fir_order(self.fir_order.value(), require_odd=require_odd_fir_order)
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


__all__ = ["FilterControls","FilterMode", "FilterPreviewPlot", "FilterResponse", "build_filter_defaults",
    "compute_filter_response", "filter_response_error", "normalize_choice", "normalize_fir_order"]
