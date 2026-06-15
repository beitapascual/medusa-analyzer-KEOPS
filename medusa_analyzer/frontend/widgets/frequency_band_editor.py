from __future__ import annotations

from collections.abc import MutableSequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout


class FrequencyBandEditor(QFrame):
    changed = Signal()

    def __init__(self, bands: MutableSequence[dict]):
        super().__init__()
        self.setProperty("role", "band-editor")
        self.bands = bands
        self.rows = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for band in bands:
            row = QFrame()
            row.setProperty("role", "band-chip")
            row_layout = QHBoxLayout(row)
            enabled = QCheckBox(band.get("title", band.get("id", "Band")))
            enabled.setChecked(bool(band.get("enabled", True)))
            low = self._spin(float(band.get("low_cut", band.get("low", 0.0))))
            high = self._spin(float(band.get("high_cut", band.get("high", 0.0))))
            row_layout.addWidget(enabled, 1)
            row_layout.addWidget(QLabel("From"))
            row_layout.addWidget(low)
            row_layout.addWidget(QLabel("to"))
            row_layout.addWidget(high)
            row_layout.addWidget(QLabel("Hz"))
            layout.addWidget(row)
            self.rows.append((band, enabled, low, high))
            enabled.toggled.connect(self._sync)
            low.valueChanged.connect(self._sync)
            high.valueChanged.connect(self._sync)

    def _spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 10000)
        spin.setDecimals(1)
        spin.setValue(value)
        spin.setFixedWidth(88)
        return spin

    def _sync(self) -> None:
        for band, enabled, low, high in self.rows:
            band["enabled"] = enabled.isChecked()
            band["low_cut"] = low.value()
            band["high_cut"] = high.value()
        self.changed.emit()
