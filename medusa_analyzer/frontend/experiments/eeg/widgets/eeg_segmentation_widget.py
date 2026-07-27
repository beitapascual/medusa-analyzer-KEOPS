from __future__ import annotations
from copy import deepcopy
from math import pi, sin
from typing import Any
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QScrollArea, QSizePolicy,
    QSlider, QSpinBox, QVBoxLayout, QWidget)
from medusa_analyzer.frontend.validation import Validation


class WindowSegmentationDiagram(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.epoch_length_ms = 1000
        self.overlap_percent = 0
        self.setMinimumHeight(270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, epoch_length_ms: int, overlap_percent: int) -> None:
        self.epoch_length_ms = int(epoch_length_ms)
        self.overlap_percent = int(overlap_percent)
        self.update()

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        painter.fillRect(rect, QColor("#1F171B"))

        text_color = QColor("#F8EEF2")
        muted_color = QColor("#B8A7AF")
        border_color = QColor("#3A2931")
        accent_color = QColor("#E35A82")
        signal_color = QColor("#9BE7E8")

        painter.setPen(QPen(border_color, 1.2))
        painter.drawRoundedRect(rect, 10, 10)

        signal_start_x = rect.left() + 28
        signal_end_x = rect.right() - 92
        signal_width = max(1.0, signal_end_x - signal_start_x)
        signal_y = rect.top() + 72
        windows_top = rect.top() + 128
        windows_height = 58

        painter.setPen(QPen(border_color, 1.3))
        painter.drawLine(QPointF(signal_start_x, signal_y), QPointF(signal_end_x, signal_y))

        signal_path = QPainterPath(QPointF(signal_start_x, signal_y))
        samples = 220
        for index in range(samples + 1):
            ratio = index / samples
            x = signal_start_x + ratio * signal_width
            y = signal_y - 28 * sin(ratio * pi * 10)
            if index == 0:
                signal_path.moveTo(x, y)
            else:
                signal_path.lineTo(x, y)
        painter.setPen(QPen(signal_color, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(signal_path)

        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        painter.setPen(text_color)
        painter.drawText(QRectF(signal_end_x + 14, signal_y - 16, 76, 32), Qt.AlignmentFlag.AlignVCenter, "Signal")

        min_epoch_width = 86
        max_epoch_width = 148
        epoch_width = min_epoch_width + (
            (self.epoch_length_ms - 400) / (2000 - 400)
        ) * (max_epoch_width - min_epoch_width)
        overlap_ratio = max(0, min(100, self.overlap_percent)) / 100
        start_step = epoch_width * (1 - overlap_ratio)
        window_fill = QColor(accent_color)
        window_fill.setAlpha(34)
        guide_pen = QPen(accent_color, 1.2, Qt.PenStyle.DashLine)

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        for index in range(5):
            start_x = signal_start_x + index * start_step
            if start_x + epoch_width > signal_end_x + 12:
                break
            window_rect = QRectF(start_x, windows_top, epoch_width, windows_height)
            painter.setBrush(window_fill)
            painter.setPen(QPen(accent_color, 1.6))
            painter.drawRoundedRect(window_rect, 7, 7)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(guide_pen)
            painter.drawLine(QPointF(start_x, signal_y + 38), QPointF(start_x, windows_top + windows_height))
            painter.setPen(text_color)
            painter.drawText(window_rect, Qt.AlignmentFlag.AlignCenter, f"Epoch {index + 1}")

        self._draw_measurement(
            painter,
            signal_start_x,
            signal_start_x + epoch_width,
            rect.top() + 216,
            f"epoch length ({self.epoch_length_ms} ms)",
            windows_top + windows_height,
            muted_color,
            text_color,
        )

        if self.overlap_percent > 0:
            second_start_x = signal_start_x + start_step
            overlap_end_x = signal_start_x + epoch_width
            if overlap_end_x > second_start_x:
                self._draw_measurement(
                    painter,
                    second_start_x,
                    overlap_end_x,
                    rect.top() + 250,
                    f"overlap ({self.overlap_percent}%)",
                    windows_top,
                    muted_color,
                    text_color,
                )

    def _draw_measurement(self, painter: QPainter, x1: float, x2: float, y: float, label: str,
        guide_top: float, muted_color: QColor, text_color: QColor) -> None:
        painter.setPen(QPen(muted_color, 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x1, guide_top), QPointF(x1, y - 7))
        painter.drawLine(QPointF(x2, guide_top), QPointF(x2, y - 7))

        painter.setPen(QPen(muted_color, 1.5))
        painter.drawLine(QPointF(x1 + 7, y), QPointF(x2 - 7, y))
        self._draw_arrow_head(painter, QPointF(x1 + 7, y), -1, muted_color)
        self._draw_arrow_head(painter, QPointF(x2 - 7, y), 1, muted_color)

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(text_color)
        painter.drawText(QRectF(x1 - 80, y + 7, (x2 - x1) + 160, 22), Qt.AlignmentFlag.AlignHCenter, label)

    @staticmethod
    def _draw_arrow_head(painter: QPainter, point: QPointF, direction: int, color: QColor) -> None:
        size = 6
        polygon = QPolygonF([
            QPointF(point.x(), point.y()),
            QPointF(point.x() + direction * size, point.y() - size / 2),
            QPointF(point.x() + direction * size, point.y() + size / 2),
        ])
        painter.setBrush(color)
        painter.setPen(QPen(color, 1))
        painter.drawPolygon(polygon)
        painter.setBrush(Qt.BrushStyle.NoBrush)


class WindowSegmentationWidget(QFrame):
    epoch_length_changed = Signal(int)
    overlap_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._syncing = False
        self.setProperty("role", "segmentation-visual-widget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        controls = QGridLayout()
        controls.setHorizontalSpacing(12)
        controls.setVerticalSpacing(12)
        layout.addLayout(controls)

        epoch_card, self.epoch_slider, self.epoch_value = self._control(
            "Epoch length", 400, 2000, 100, 1000, "ms",
            "If epoch length increases, the windows become wider.")
        overlap_card, self.overlap_slider, self.overlap_value = self._control(
            "Overlap", 0, 80, 5, 0, "%",
            "Increasing overlap makes consecutive epochs overlap more.")

        controls.addWidget(epoch_card, 0, 0)
        controls.addWidget(overlap_card, 0, 1)

        self.diagram = WindowSegmentationDiagram()
        layout.addWidget(self.diagram)

        self.epoch_slider.valueChanged.connect(self._epoch_slider_changed)
        self.overlap_slider.valueChanged.connect(self._overlap_slider_changed)
        self.set_values(1000, 0)

    def _control(self, title: str, minimum: int, maximum: int, step: int, value: int,
        suffix: str, hint: str) -> tuple[QFrame, QSlider, QLabel]:
        card = QFrame()
        card.setProperty("role", "segmentation-visual-control")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("subgroupTitle")
        value_label = QLabel(f"{value} {suffix}" if suffix == "ms" else f"{value}{suffix}")
        value_label.setObjectName("segmentationVisualBadge")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(label)
        header.addStretch()
        header.addWidget(value_label)
        layout.addLayout(header)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(step)
        slider.setPageStep(step)
        slider.setValue(value)
        layout.addWidget(slider)

        hint_label = QLabel(hint)
        hint_label.setObjectName("muted")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        return card, slider, value_label

    def set_values(self, epoch_length_ms: int, overlap_percent: int) -> None:
        previous = self._syncing
        self._syncing = True
        try:
            self.epoch_slider.setValue(int(epoch_length_ms))
            self.overlap_slider.setValue(int(overlap_percent))
            self._update_labels()
            self.diagram.set_values(int(epoch_length_ms), int(overlap_percent))
        finally:
            self._syncing = previous

    def _update_labels(self) -> None:
        self.epoch_value.setText(f"{self.epoch_slider.value()} ms")
        self.overlap_value.setText(f"{self.overlap_slider.value()}%")

    def _epoch_slider_changed(self, value: int) -> None:
        self._update_labels()
        self.diagram.set_values(value, self.overlap_slider.value())
        if not self._syncing:
            self.epoch_length_changed.emit(value)

    def _overlap_slider_changed(self, value: int) -> None:
        self._update_labels()
        self.diagram.set_values(self.epoch_slider.value(), value)
        if not self._syncing:
            self.overlap_changed.emit(value)


class OnsetSegmentationDiagram(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.window_start_ms = 0
        self.window_end_ms = 400
        self.baseline_start_ms = -100
        self.baseline_end_ms = 0
        self.setMinimumHeight(330)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, window_start_ms: int, window_end_ms: int,
        baseline_start_ms: int, baseline_end_ms: int) -> None:
        self.window_start_ms = int(window_start_ms)
        self.window_end_ms = int(window_end_ms)
        self.baseline_start_ms = int(baseline_start_ms)
        self.baseline_end_ms = int(baseline_end_ms)
        self.update()

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        painter.fillRect(rect, QColor("#1F171B"))

        text_color = QColor("#F8EEF2")
        muted_color = QColor("#B8A7AF")
        border_color = QColor("#3A2931")
        signal_color = QColor("#9BE7E8")
        onset_color = QColor("#FF6B7A")
        window_color = QColor("#E35A82")
        baseline_color = QColor("#F6C177")

        painter.setPen(QPen(border_color, 1.2))
        painter.drawRoundedRect(rect, 10, 10)

        signal_start_x = rect.left() + 34
        signal_end_x = rect.right() - 100
        signal_width = max(1.0, signal_end_x - signal_start_x)
        signal_y = rect.top() + 72
        onset_positions = [
            signal_start_x + signal_width * 0.25,
            signal_start_x + signal_width * 0.74,
        ]
        pixels_per_ms = signal_width / 2600
        window_row_y = rect.top() + 168
        baseline_row_y = rect.top() + 248

        painter.setPen(QPen(border_color, 1.3))
        painter.drawLine(QPointF(signal_start_x, signal_y), QPointF(signal_end_x, signal_y))

        signal_path = QPainterPath(QPointF(signal_start_x, self._signal_y(signal_start_x, signal_start_x, signal_width, signal_y)))
        samples = 320
        for index in range(samples + 1):
            ratio = index / samples
            x = signal_start_x + ratio * signal_width
            y = self._signal_y(x, signal_start_x, signal_width, signal_y)
            if index == 0:
                signal_path.moveTo(x, y)
            else:
                signal_path.lineTo(x, y)
        painter.setPen(QPen(signal_color, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(signal_path)

        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        painter.setPen(text_color)
        painter.drawText(QRectF(signal_end_x + 14, signal_y - 16, 78, 32), Qt.AlignmentFlag.AlignVCenter, "Signal")

        for onset_x in onset_positions:
            onset_y = self._signal_y(onset_x, signal_start_x, signal_width, signal_y)
            painter.setPen(QPen(onset_color, 1.3, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(onset_x, onset_y), QPointF(onset_x, baseline_row_y + 45))
            painter.setBrush(onset_color)
            painter.setPen(QPen(QColor("#1F171B"), 1.6))
            painter.drawEllipse(QPointF(onset_x, onset_y), 5.8, 5.8)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(onset_color)
            painter.drawText(QRectF(onset_x - 36, onset_y - 30, 72, 18), Qt.AlignmentFlag.AlignCenter, "onset")

            window_start_x = self._clamp_x(onset_x + self.window_start_ms * pixels_per_ms, signal_start_x, signal_end_x)
            window_end_x = self._clamp_x(onset_x + self.window_end_ms * pixels_per_ms, signal_start_x, signal_end_x)
            baseline_start_x = self._clamp_x(onset_x + self.baseline_start_ms * pixels_per_ms, signal_start_x, signal_end_x)
            baseline_end_x = self._clamp_x(onset_x + self.baseline_end_ms * pixels_per_ms, signal_start_x, signal_end_x)

            self._draw_interval(
                painter,
                window_start_x,
                window_end_x,
                window_row_y,
                window_color,
                "segmentation window",
                f"start {self.window_start_ms} ms",
                f"end {self.window_end_ms} ms",
            )
            self._draw_interval(
                painter,
                baseline_start_x,
                baseline_end_x,
                baseline_row_y,
                baseline_color,
                "baseline",
                f"baseline start {self.baseline_start_ms} ms",
                f"baseline end {self.baseline_end_ms} ms",
            )

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.setPen(muted_color)
        painter.drawText(
            QRectF(rect.left() + 18, rect.bottom() - 26, rect.width() - 36, 20),
            Qt.AlignmentFlag.AlignCenter,
            "Onsets are separated so segmentation windows and baseline intervals remain readable.",
        )

    @staticmethod
    def _signal_y(x: float, start_x: float, width: float, middle_y: float) -> float:
        ratio = (x - start_x) / width
        return middle_y - 28 * sin(ratio * pi * 8.5) - 8 * sin(ratio * pi * 21)

    @staticmethod
    def _clamp_x(x: float, minimum: float, maximum: float) -> float:
        return max(minimum + 5, min(maximum - 5, x))

    def _draw_interval(self, painter: QPainter, x1: float, x2: float, y: float, color: QColor,
        title: str, start_label: str, end_label: str) -> None:
        left_x = min(x1, x2)
        right_x = max(x1, x2)
        interval_width = max(2.0, right_x - left_x)

        fill = QColor(color)
        fill.setAlpha(38)
        painter.setBrush(fill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(left_x, y - 13, interval_width, 16), 4, 4)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setPen(QPen(color, 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(left_x, y - 18), QPointF(left_x, y + 34))
        painter.drawLine(QPointF(right_x, y - 18), QPointF(right_x, y + 34))

        painter.setPen(QPen(color, 2.0))
        painter.drawPath(self._brace_path(left_x, right_x, y, 22))

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(color)
        painter.drawText(QRectF(left_x - 50, y + 27, interval_width + 100, 18), Qt.AlignmentFlag.AlignCenter, title)
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        painter.drawText(QRectF(left_x - 118, y - 32, 110, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, start_label)
        painter.drawText(QRectF(right_x + 8, y - 32, 118, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, end_label)

    @staticmethod
    def _brace_path(x1: float, x2: float, y: float, height: float) -> QPainterPath:
        left_x = min(x1, x2)
        right_x = max(x1, x2)
        width = max(1.0, right_x - left_x)
        middle_x = (left_x + right_x) / 2
        curve_width = min(24.0, max(8.0, width * 0.18))

        path = QPainterPath(QPointF(left_x, y))
        path.cubicTo(left_x, y, left_x, y + height * 0.55, left_x + curve_width, y + height * 0.55)
        path.cubicTo(left_x + curve_width * 1.5, y + height * 0.55,
            middle_x - curve_width * 0.8, y + height, middle_x, y + height)
        path.cubicTo(middle_x + curve_width * 0.8, y + height,
            right_x - curve_width * 1.5, y + height * 0.55, right_x - curve_width, y + height * 0.55)
        path.cubicTo(right_x, y + height * 0.55, right_x, y, right_x, y)
        return path


class OnsetSegmentationWidget(QFrame):
    values_changed = Signal(int, int, int, int)

    def __init__(self) -> None:
        super().__init__()
        self._syncing = False
        self.setProperty("role", "segmentation-visual-widget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        controls = QGridLayout()
        controls.setHorizontalSpacing(12)
        controls.setVerticalSpacing(12)
        layout.addLayout(controls)

        start_card, self.window_start_slider, self.window_start_value = self._control(
            "Start", -300, 200, 25, 0,
            "Beginning of the segmentation window relative to the onset.")
        end_card, self.window_end_slider, self.window_end_value = self._control(
            "End", 50, 700, 25, 400,
            "End of the segmentation window relative to the onset.")
        baseline_start_card, self.baseline_start_slider, self.baseline_start_value = self._control(
            "Baseline start", -400, -25, 25, -100,
            "Beginning of the baseline interval relative to the onset.")
        baseline_end_card, self.baseline_end_slider, self.baseline_end_value = self._control(
            "Baseline end", -300, 0, 25, 0,
            "By default, the baseline ends at the onset.")

        controls.addWidget(start_card, 0, 0)
        controls.addWidget(end_card, 0, 1)
        controls.addWidget(baseline_start_card, 1, 0)
        controls.addWidget(baseline_end_card, 1, 1)

        self.diagram = OnsetSegmentationDiagram()
        layout.addWidget(self.diagram)

        for slider in (
            self.window_start_slider,
            self.window_end_slider,
            self.baseline_start_slider,
            self.baseline_end_slider,
        ):
            slider.valueChanged.connect(self._slider_changed)

        self.set_values(0, 400, -100, 0)

    def _control(self, title: str, minimum: int, maximum: int, step: int, value: int,
        hint: str) -> tuple[QFrame, QSlider, QLabel]:
        card = QFrame()
        card.setProperty("role", "segmentation-visual-control")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("subgroupTitle")
        value_label = QLabel(f"{value} ms")
        value_label.setObjectName("segmentationVisualBadge")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(label)
        header.addStretch()
        header.addWidget(value_label)
        layout.addLayout(header)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(step)
        slider.setPageStep(step)
        slider.setValue(value)
        layout.addWidget(slider)

        hint_label = QLabel(hint)
        hint_label.setObjectName("muted")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        return card, slider, value_label

    def set_values(self, window_start_ms: int, window_end_ms: int,
        baseline_start_ms: int, baseline_end_ms: int) -> None:
        values = self._normalized_values(window_start_ms, window_end_ms, baseline_start_ms, baseline_end_ms)
        previous = self._syncing
        self._syncing = True
        try:
            self.window_start_slider.setValue(values[0])
            self.window_end_slider.setValue(values[1])
            self.baseline_start_slider.setValue(values[2])
            self.baseline_end_slider.setValue(values[3])
            self._update_labels(values)
            self.diagram.set_values(*values)
        finally:
            self._syncing = previous

    def _slider_changed(self, *_: Any) -> None:
        values = self._normalized_values(
            self.window_start_slider.value(),
            self.window_end_slider.value(),
            self.baseline_start_slider.value(),
            self.baseline_end_slider.value(),
        )
        previous = self._syncing
        self._syncing = True
        try:
            self.window_start_slider.setValue(values[0])
            self.window_end_slider.setValue(values[1])
            self.baseline_start_slider.setValue(values[2])
            self.baseline_end_slider.setValue(values[3])
            self._update_labels(values)
            self.diagram.set_values(*values)
        finally:
            self._syncing = previous

        if not previous:
            self.values_changed.emit(*values)

    def _update_labels(self, values: tuple[int, int, int, int]) -> None:
        self.window_start_value.setText(f"{values[0]} ms")
        self.window_end_value.setText(f"{values[1]} ms")
        self.baseline_start_value.setText(f"{values[2]} ms")
        self.baseline_end_value.setText(f"{values[3]} ms")

    def _normalized_values(self, window_start_ms: int, window_end_ms: int,
        baseline_start_ms: int, baseline_end_ms: int) -> tuple[int, int, int, int]:
        window_start_ms = self._clamp_to_slider(self.window_start_slider, window_start_ms)
        window_end_ms = self._clamp_to_slider(self.window_end_slider, window_end_ms)
        baseline_start_ms = self._clamp_to_slider(self.baseline_start_slider, baseline_start_ms)
        baseline_end_ms = self._clamp_to_slider(self.baseline_end_slider, baseline_end_ms)

        if window_end_ms <= window_start_ms:
            window_end_ms = min(self.window_end_slider.maximum(), window_start_ms + 25)
            if window_end_ms <= window_start_ms:
                window_start_ms = max(self.window_start_slider.minimum(), window_end_ms - 25)

        if baseline_end_ms <= baseline_start_ms:
            baseline_end_ms = min(self.baseline_end_slider.maximum(), baseline_start_ms + 25)
            if baseline_end_ms <= baseline_start_ms:
                baseline_start_ms = max(self.baseline_start_slider.minimum(), baseline_end_ms - 25)

        return window_start_ms, window_end_ms, baseline_start_ms, baseline_end_ms

    @staticmethod
    def _clamp_to_slider(slider: QSlider, value: int) -> int:
        return max(slider.minimum(), min(slider.maximum(), int(value)))


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
        self._updating_strategy = False
        self._syncing_parameter_controls = False
        self._epoch_target = "instant"
        self._normalization_target = "instant"
        self._last_event_signature: tuple[tuple[str, ...], tuple[str, ...]] | None = None

        self.state["segmentation"] = self._initial_segmentation_state(self.state.get("segmentation") or {})
        self._ensure_parameter_state()

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
            button.setCheckable(True)
            button.setProperty("role", "segmentation-mode-button")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

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
        self.duration_events_list.setObjectName("durationEventsList")
        self.instant_events_list.setObjectName("instantEventsList")
        for list_widget in (self.duration_events_list, self.instant_events_list):
            list_widget.setProperty("role", "file-list")
            list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            list_widget.setMinimumHeight(128)

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

        nested_note = QLabel(
            "Add duration events as bases, then choose either duration or instant nested events for all bases."
        )
        nested_note.setObjectName("muted")
        nested_note.setWordWrap(True)
        nested_layout.addWidget(nested_note)

        self.add_base_event_button = QPushButton("+ Add base duration event")
        self.add_base_event_button.setProperty("variant", "secondary")
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

        self.summary_panel = self._panel("Segmentation summary")
        self.summary_layout = QVBoxLayout()
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_panel.layout().addLayout(self.summary_layout)
        root.addWidget(self.summary_panel)

        # ------------------------------------------------------------------
        # Segmentation strategy
        # ------------------------------------------------------------------
        self.strategy_panel = self._panel("Segmentation strategy")
        strategy_row = QHBoxLayout()
        self.window_strategy_button = QPushButton("Window-based segmentation")
        self.onset_strategy_button = QPushButton("Onset-based segmentation")
        for button in (self.window_strategy_button, self.onset_strategy_button):
            button.setCheckable(True)
            button.setProperty("role", "segmentation-strategy-button")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.strategy_group = QButtonGroup(self)
        self.strategy_group.setExclusive(True)
        self.strategy_group.addButton(self.window_strategy_button)
        self.strategy_group.addButton(self.onset_strategy_button)
        strategy_row.addWidget(self.window_strategy_button)
        strategy_row.addWidget(self.onset_strategy_button)
        self.strategy_panel.layout().addLayout(strategy_row)

        self.window_segmentation_widget = WindowSegmentationWidget()
        self.strategy_panel.layout().addWidget(self.window_segmentation_widget)

        self.onset_segmentation_widget = OnsetSegmentationWidget()
        self.strategy_panel.layout().addWidget(self.onset_segmentation_widget)
        root.addWidget(self.strategy_panel)

        # ------------------------------------------------------------------
        # Epoch parameters
        # ------------------------------------------------------------------
        epoch_panel = self._panel("Epoch parameters")
        (self.epoch_target_panel, self.epoch_duration_target_button, self.epoch_instant_target_button) = self._target_selector("Edit epoch parameters for")
        epoch_panel.layout().addWidget(self.epoch_target_panel)
        epoch_grid = QGridLayout()
        epoch_panel.layout().addLayout(epoch_grid)

        instant_epoch_config = self._default_epoch_state("instant")
        duration_epoch_config = self._default_epoch_state("duration")
        self.epoch_start_label = QLabel("Epoch start")
        self.epoch_end_label = QLabel("Epoch end")
        self.duration_epoch_length_label = QLabel("Epoch length")
        self.stride_label = QLabel("Stride")

        self.epoch_start = self._spin(-60000, 60000, int(instant_epoch_config["epoch_window_ms"]["start"]))
        self.epoch_end = self._spin(-60000, 60000, int(instant_epoch_config["epoch_window_ms"]["end"]))
        self.duration_epoch_length = self._spin(1, 60000, int(duration_epoch_config["duration_epoch_length_ms"]))
        self.stride = self._spin(0, 100, int(instant_epoch_config["stride_percent"]), suffix=" %")
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
        (self.normalization_target_panel, self.normalization_duration_target_button,
            self.normalization_instant_target_button) = self._target_selector("Edit normalization for")
        normalization_panel.layout().addWidget(self.normalization_target_panel)
        normalization_grid = QGridLayout()
        normalization_panel.layout().addLayout(normalization_grid)

        normalization_config = self.config.get("normalization", {})
        baseline_config = normalization_config.get("baseline_window_ms", {})

        self.normalization_enabled = QCheckBox("Normalize epochs")
        self.normalization_mode = QComboBox()
        self.normalization_mode.addItem("Mean", "mean")
        self.normalization_mode.addItem("Z-score", "mean_std")

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

        # ------------------------------------------------------------------
        # Resampling
        # ------------------------------------------------------------------
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

        for widget in [self.epoch_start, self.epoch_end, self.duration_epoch_length, self.stride, self.average_epochs,
            self.normalization_enabled, self.normalization_mode, self.baseline_start, self.baseline_end,
            self.threshold_enabled, self.threshold_sigma, self.threshold_samples, self.threshold_channels,
            self.resampling_enabled, self.target_sampling_frequency]:
            signal = (widget.currentIndexChanged if isinstance(widget, QComboBox) else widget.toggled
                if isinstance(widget, QCheckBox) else widget.valueChanged)
            signal.connect(self._sync)

        self.independent_mode_button.toggled.connect(self._segmentation_mode_changed)
        self.nested_mode_button.toggled.connect(self._segmentation_mode_changed)
        self.window_strategy_button.toggled.connect(lambda checked: self._segmentation_strategy_changed("window") if checked else None)
        self.onset_strategy_button.toggled.connect(lambda checked: self._segmentation_strategy_changed("onset") if checked else None)
        self.window_segmentation_widget.epoch_length_changed.connect(self._window_preview_epoch_length_changed)
        self.window_segmentation_widget.overlap_changed.connect(self._window_preview_overlap_changed)
        self.onset_segmentation_widget.values_changed.connect(self._onset_preview_values_changed)
        self.epoch_duration_target_button.toggled.connect(lambda checked: self._epoch_target_changed("duration") if checked else None)
        self.epoch_instant_target_button.toggled.connect(lambda checked: self._epoch_target_changed("instant") if checked else None)
        self.normalization_duration_target_button.toggled.connect(lambda checked: self._normalization_target_changed("duration") if checked else None)
        self.normalization_instant_target_button.toggled.connect(lambda checked: self._normalization_target_changed("instant") if checked else None)
        self.duration_events_list.itemSelectionChanged.connect(lambda group="duration": self._independent_event_changed(group))
        self.instant_events_list.itemSelectionChanged.connect(lambda group="instant": self._independent_event_changed(group))
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
    def _spin(minimum: int, maximum: int, value: int, suffix: str = " ms") -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin

    @staticmethod
    def _target_or_default(value: Any, default: str = "instant") -> str:
        return str(value) if value in {"duration", "instant"} else default

    @staticmethod
    def _strategy_or_default(value: Any, default: str = "window") -> str:
        return str(value) if value in {"window", "onset"} else default

    @staticmethod
    def _set_button_checked(button: QPushButton, checked: bool) -> None:
        previous = button.blockSignals(True)
        button.setChecked(checked)
        button.blockSignals(previous)

    def _target_selector(self, label_text: str) -> tuple[QFrame, QPushButton, QPushButton]:
        panel = QFrame()
        panel.setProperty("role", "segmentation-target-panel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        label = QLabel(label_text)
        label.setObjectName("segmentationTargetLabel")
        duration_button = QPushButton("Duration events")
        instant_button = QPushButton("Instant events")
        for button in (duration_button, instant_button):
            button.setCheckable(True)
            button.setProperty("role", "segmentation-target-button")

        button_group = QButtonGroup(panel)
        button_group.setExclusive(True)
        button_group.addButton(duration_button)
        button_group.addButton(instant_button)
        panel.button_group = button_group

        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(duration_button)
        layout.addWidget(instant_button)
        return panel, duration_button, instant_button

    def _initial_segmentation_state(self, current: dict[str, Any]) -> dict[str, Any]:
        mode = current.get("segmentation_mode", self.config.get("segmentation_mode", "independent"))
        if mode not in {"independent", "nested"}:
            mode = "independent"

        epoch_parameters = current.get("epoch_parameters")
        if not isinstance(epoch_parameters, dict):
            epoch_parameters = {}
        normalization = current.get("normalization")
        if not isinstance(normalization, dict) or not (
            "duration" in normalization or "instant" in normalization
        ):
            normalization = {}

        return {
            "segmentation_mode": mode,
            "segmentation_strategy": self._strategy_or_default(
                current.get("segmentation_strategy", self.config.get("segmentation_strategy", "window"))
            ),
            "event_groups": self._initial_event_groups(current, mode),
            "epoch_parameters": {
                "duration": deepcopy(epoch_parameters.get("duration") or {}),
                "instant": deepcopy(epoch_parameters.get("instant") or {}),
            },
            "normalization": {
                "duration": deepcopy(normalization.get("duration") or {}),
                "instant": deepcopy(normalization.get("instant") or {}),
            },
            "thresholding": {
                **deepcopy(self.config.get("thresholding", {})),
                **deepcopy(current.get("thresholding") or {}),
            },
            "resampling": {
                **deepcopy(self.config.get("resampling", {})),
                **deepcopy(current.get("resampling") or {}),
            },
        }

    @staticmethod
    def _event_group(base_event: Any | None, duration_events: list[Any] | None,
        instant_events: list[Any] | None) -> dict[str, Any]:
        return {
            "base_event": str(base_event) if base_event else None,
            "duration_events": [str(event) for event in (duration_events or [])],
            "instant_events": [str(event) for event in (instant_events or [])],
        }

    def _initial_event_groups(self, current: dict[str, Any], mode: str) -> list[dict[str, Any]]:
        del mode
        event_groups = current.get("event_groups")
        if isinstance(event_groups, list):
            return [self._event_group(group.get("base_event"), group.get("duration_events"),
                group.get("instant_events")) for group in event_groups if isinstance(group, dict)]
        return []

    def _default_epoch_window(self) -> dict[str, int]:
        epoch = ((self.config.get("epoch_parameters") or {}).get("instant") or {}).get("epoch_window_ms", {})
        return {"start": int(epoch.get("start", -300)), "end": int(epoch.get("end", 700))}

    def _normalized_epoch_window(self, value: Any | None = None) -> dict[str, int]:
        default = self._default_epoch_window()
        if isinstance(value, dict):
            default.update({"start": int(value.get("start", default["start"])),
                "end": int(value.get("end", default["end"]))})
        return default

    def _normalized_baseline_window(self, value: Any | None = None) -> dict[str, int]:
        default = self._default_normalization_state("instant")["baseline_window_ms"]
        if isinstance(value, dict):
            default.update({"start": int(value.get("start", default["start"])),
                "end": int(value.get("end", default["end"]))})
        return default

    def _current_state_strategy(self) -> str:
        segmentation = self.state.get("segmentation") or {}
        return self._strategy_or_default(segmentation.get("segmentation_strategy"), "window")

    def _target_uses_window(self, target: str) -> bool:
        return self._target_or_default(target) == "duration" and self._current_state_strategy() == "window"

    def _target_uses_onset(self, target: str) -> bool:
        target = self._target_or_default(target)
        return target == "instant" or (target == "duration" and self._current_state_strategy() == "onset")

    def _default_epoch_state(self, target: str) -> dict[str, Any]:
        target = self._target_or_default(target)
        defaults = ((self.config.get("epoch_parameters") or {}).get(target) or {})
        if self._target_uses_window(target):
            return {
                "duration_epoch_length_ms": int(defaults.get("duration_epoch_length_ms", 1000)),
                "stride_percent": int(defaults.get("stride_percent", 0)),
                "average_epochs": bool(defaults.get("average_epochs", False)),
            }
        if target == "duration":
            defaults = ((self.config.get("epoch_parameters") or {}).get("instant") or {})
        return {
            "epoch_window_ms": self._normalized_epoch_window(defaults.get("epoch_window_ms")),
            "stride_percent": int(defaults.get("stride_percent", 0)),
            "average_epochs": bool(defaults.get("average_epochs", False)),
        }

    def _normalized_epoch_state(self, target: str, value: Any | None = None) -> dict[str, Any]:
        target = self._target_or_default(target)
        state = self._default_epoch_state(target)
        if not isinstance(value, dict):
            return state
        if self._target_uses_window(target):
            state["duration_epoch_length_ms"] = int(value.get("duration_epoch_length_ms", state["duration_epoch_length_ms"]))
        else:
            state["epoch_window_ms"] = self._normalized_epoch_window(value.get("epoch_window_ms"))
        state["stride_percent"] = int(value.get("stride_percent", state["stride_percent"]))
        state["average_epochs"] = bool(value.get("average_epochs", state["average_epochs"]))
        return state

    def _default_normalization_state(self, target: str) -> dict[str, Any]:
        target = self._target_or_default(target)
        defaults = ((self.config.get("normalization") or {}).get(target) or {})
        state = {
            "enabled": bool(defaults.get("enabled", False)),
            "mode": str(defaults.get("mode", "mean_std")),
        }
        if self._target_uses_onset(target):
            if target == "duration":
                defaults = ((self.config.get("normalization") or {}).get("instant") or defaults)
            baseline = defaults.get("baseline_window_ms", {})
            state["baseline_window_ms"] = {
                "start": int(baseline.get("start", -100)),
                "end": int(baseline.get("end", 0)),
            }
        return state

    def _normalized_normalization_state(self, target: str, value: Any | None = None) -> dict[str, Any]:
        target = self._target_or_default(target)
        state = self._default_normalization_state(target)
        if not isinstance(value, dict):
            return state
        state["enabled"] = bool(value.get("enabled", state["enabled"]))
        state["mode"] = str(value.get("mode", state["mode"]))
        if self._target_uses_onset(target):
            state["baseline_window_ms"] = self._normalized_baseline_window(value.get("baseline_window_ms"))
        return state

    def _active_event_types_from_state(self) -> tuple[bool, bool]:
        segmentation = self.state["segmentation"]
        if segmentation.get("segmentation_mode") == "nested":
            return self._nested_event_types()
        duration_events, instant_events = self._independent_events_from_state()
        return bool(duration_events), bool(instant_events)

    def _ensure_parameter_state(self, has_duration: bool | None = None, has_instant: bool | None = None) -> None:
        if has_duration is None or has_instant is None:
            has_duration, has_instant = self._active_event_types_from_state()

        segmentation = self.state["segmentation"]
        epoch_parameters = segmentation.get("epoch_parameters") if isinstance(segmentation.get("epoch_parameters"), dict) else {}
        normalization = segmentation.get("normalization") if isinstance(segmentation.get("normalization"), dict) else {}
        segmentation["epoch_parameters"] = {
            "duration": self._normalized_epoch_state("duration", epoch_parameters.get("duration")) if has_duration else {},
            "instant": self._normalized_epoch_state("instant", epoch_parameters.get("instant")) if has_instant else {},
        }
        segmentation["normalization"] = {
            "duration": self._normalized_normalization_state("duration", normalization.get("duration")) if has_duration else {},
            "instant": self._normalized_normalization_state("instant", normalization.get("instant")) if has_instant else {},
        }

    def _epoch_state(self, target: str, create: bool = True) -> dict[str, Any]:
        target = self._target_or_default(target)
        epoch_parameters = self.state["segmentation"].setdefault("epoch_parameters", {"duration": {}, "instant": {}})
        current = epoch_parameters.get(target)
        if create:
            current = self._normalized_epoch_state(target, current)
            epoch_parameters[target] = current
        return current if isinstance(current, dict) and current else self._default_epoch_state(target)

    def _normalization_state(self, target: str, create: bool = True) -> dict[str, Any]:
        target = self._target_or_default(target)
        normalization = self.state["segmentation"].setdefault("normalization", {"duration": {}, "instant": {}})
        current = normalization.get(target)
        if create:
            current = self._normalized_normalization_state(target, current)
            normalization[target] = current
        return current if isinstance(current, dict) and current else self._default_normalization_state(target)

    def _set_epoch_target_buttons(self) -> None:
        self._set_button_checked(self.epoch_duration_target_button, self._epoch_target == "duration")
        self._set_button_checked(self.epoch_instant_target_button, self._epoch_target == "instant")

    def _set_normalization_target_buttons(self) -> None:
        self._set_button_checked(self.normalization_duration_target_button, self._normalization_target == "duration")
        self._set_button_checked(self.normalization_instant_target_button, self._normalization_target == "instant")

    def _set_epoch_controls_from_state(self, target: str) -> None:
        state = self._epoch_state(target, create=False)
        previous = self._syncing_parameter_controls
        self._syncing_parameter_controls = True
        try:
            if self._target_uses_window(target):
                self.duration_epoch_length.setValue(
                    int(state.get("duration_epoch_length_ms", self._default_epoch_state("duration")["duration_epoch_length_ms"])))
            else:
                epoch = self._normalized_epoch_window(state.get("epoch_window_ms"))
                self.epoch_start.setValue(epoch["start"])
                self.epoch_end.setValue(epoch["end"])
            self.stride.setValue(int(state.get("stride_percent", self._default_epoch_state(target)["stride_percent"])))
            self.average_epochs.setChecked(
                bool(state.get("average_epochs", self._default_epoch_state(target)["average_epochs"])))
        finally:
            self._syncing_parameter_controls = previous

    def _store_epoch_controls(self, target: str) -> None:
        if self._syncing_parameter_controls:
            return
        state = self._epoch_state(target)
        if self._target_uses_window(target):
            state["duration_epoch_length_ms"] = self.duration_epoch_length.value()
        else:
            state["epoch_window_ms"] = {"start": self.epoch_start.value(), "end": self.epoch_end.value()}
        state["stride_percent"] = self.stride.value()
        state["average_epochs"] = self.average_epochs.isChecked()

    def _set_normalization_controls_from_state(self, target: str) -> None:
        state = self._normalization_state(target, create=False)
        default = self._default_normalization_state(target)
        previous = self._syncing_parameter_controls
        self._syncing_parameter_controls = True
        try:
            self.normalization_enabled.setChecked(bool(state.get("enabled", default["enabled"])))
            index = self.normalization_mode.findData(state.get("mode", default["mode"]))
            self.normalization_mode.setCurrentIndex(max(0, index))
            if target == "instant":
                baseline = self._normalized_baseline_window(state.get("baseline_window_ms"))
                self.baseline_start.setValue(baseline["start"])
                self.baseline_end.setValue(baseline["end"])
        finally:
            self._syncing_parameter_controls = previous

    def _store_normalization_controls(self, target: str) -> None:
        if self._syncing_parameter_controls:
            return
        state = self._normalization_state(target)
        state["enabled"] = self.normalization_enabled.isChecked()
        state["mode"] = self.normalization_mode.currentData()
        if self._target_uses_onset(target):
            state["baseline_window_ms"] = {"start": self.baseline_start.value(), "end": self.baseline_end.value()}

    def _selection_mode_for_state(self, mode: str, selected_duration_events: list[str], selected_instant_events: list[str]) -> str:
        if mode == "nested":
            return "nested"
        if selected_duration_events:
            return "duration"
        if selected_instant_events:
            return "instant"
        return "none"

    def _target_for_mode(self, mode: str, selection_mode: str, current_target: str) -> str:
        if mode == "nested":
            has_duration, has_instant = self._nested_event_types()
            if has_duration and not has_instant:
                return "duration"
            if has_instant and not has_duration:
                return "instant"
            return self._target_or_default(current_target)
        if selection_mode == "duration":
            return "duration"
        return "instant"

    def _current_segmentation_strategy(self) -> str:
        return "window" if self.window_strategy_button.isChecked() else "onset"

    def _strategy_for_active_types(self, has_duration: bool, has_instant: bool, current_strategy: str) -> str:
        if has_instant and not has_duration:
            return "onset"
        if has_duration and not has_instant:
            return self._strategy_or_default(current_strategy, "window")
        return self._strategy_or_default(current_strategy, "window")

    def _set_strategy_buttons(self, strategy: str) -> None:
        previous = self._updating_strategy
        self._updating_strategy = True
        try:
            self._set_button_checked(self.window_strategy_button, strategy == "window")
            self._set_button_checked(self.onset_strategy_button, strategy == "onset")
        finally:
            self._updating_strategy = previous

    def _align_segmentation_strategy(self, has_duration: bool, has_instant: bool) -> str:
        current_strategy = self.state["segmentation"].get("segmentation_strategy", self._current_segmentation_strategy())
        strategy = self._strategy_for_active_types(has_duration, has_instant, current_strategy)
        self.state["segmentation"]["segmentation_strategy"] = strategy
        self._set_strategy_buttons(strategy)
        return strategy

    def _align_parameter_targets(self, mode: str, selection_mode: str) -> None:
        epoch_target = self._target_for_mode(mode, selection_mode, self._epoch_target)
        normalization_target = self._target_for_mode(mode, selection_mode, self._normalization_target)

        if epoch_target != self._epoch_target:
            self._epoch_target = epoch_target
            self._set_epoch_target_buttons()
            self._set_epoch_controls_from_state(epoch_target)

        if normalization_target != self._normalization_target:
            self._normalization_target = normalization_target
            self._set_normalization_target_buttons()
            self._set_normalization_controls_from_state(normalization_target)

    def _segmentation_strategy_changed(self, strategy: str) -> None:
        if self._updating_strategy:
            return
        strategy = self._strategy_or_default(strategy)
        if strategy == self.state["segmentation"].get("segmentation_strategy"):
            return
        self._store_epoch_controls(self._epoch_target)
        self._store_normalization_controls(self._normalization_target)
        self.state["segmentation"]["segmentation_strategy"] = strategy
        self._set_epoch_controls_from_state(self._epoch_target)
        self._set_normalization_controls_from_state(self._normalization_target)
        self._sync_strategy_preview()
        self._sync()

    def _window_preview_epoch_length_changed(self, value: int) -> None:
        if self._syncing_parameter_controls or self._current_state_strategy() != "window":
            return
        if self._epoch_target == "duration":
            self.duration_epoch_length.setValue(value)

    def _window_preview_overlap_changed(self, value: int) -> None:
        if self._syncing_parameter_controls or self._current_state_strategy() != "window":
            return
        if self._epoch_target == "duration":
            self.stride.setValue(value)

    def _onset_preview_values_changed(self, window_start: int, window_end: int,
        baseline_start: int, baseline_end: int) -> None:
        if self._syncing_parameter_controls or not self._target_uses_onset(self._epoch_target):
            return

        previous = self._syncing_parameter_controls
        self._syncing_parameter_controls = True
        try:
            self.epoch_start.setValue(window_start)
            self.epoch_end.setValue(window_end)
            self.baseline_start.setValue(baseline_start)
            self.baseline_end.setValue(baseline_end)
        finally:
            self._syncing_parameter_controls = previous
        self._sync()

    def _sync_strategy_preview(self) -> None:
        if self._target_uses_window(self._epoch_target):
            self.window_segmentation_widget.set_values(self.duration_epoch_length.value(), self.stride.value())
        if self._target_uses_onset(self._epoch_target):
            self.onset_segmentation_widget.set_values(
                self.epoch_start.value(),
                self.epoch_end.value(),
                self.baseline_start.value(),
                self.baseline_end.value(),
            )

    def _epoch_target_changed(self, target: str) -> None:
        target = self._target_or_default(target)
        if self._syncing_parameter_controls or target == self._epoch_target:
            return
        self._store_epoch_controls(self._epoch_target)
        self._epoch_target = target
        self._set_epoch_controls_from_state(target)
        self._sync()

    def _normalization_target_changed(self, target: str) -> None:
        target = self._target_or_default(target)
        if self._syncing_parameter_controls or target == self._normalization_target:
            return
        self._store_normalization_controls(self._normalization_target)
        self._normalization_target = target
        self._set_normalization_controls_from_state(target)
        self._sync()

    def _load_state(self) -> None:
        segmentation = self.state["segmentation"]
        thresholding = segmentation.get("thresholding", {})
        resampling = segmentation.get("resampling", {})

        self.threshold_enabled.setChecked(bool(thresholding.get("enabled", self.config["thresholding"]["enabled"])))
        self.threshold_sigma.setValue(float(thresholding.get("sigma", self.config["thresholding"]["sigma"])))
        self.threshold_samples.setValue(int(thresholding.get("samples", self.config["thresholding"]["samples"])))
        self.threshold_channels.setValue(int(thresholding.get("channels", self.config["thresholding"]["channels"])))
        self.resampling_enabled.setChecked(bool(resampling.get("enabled", self.config["resampling"]["enabled"])))
        self.target_sampling_frequency.setValue(int(resampling.get("target_sampling_frequency",
                    self.config["resampling"]["target_sampling_frequency"])))

        requested_mode = segmentation.get("segmentation_mode")
        if requested_mode not in {"independent", "nested"}:
            requested_mode = "nested" if any(group.get("base_event") for group in segmentation.get("event_groups", [])) else "independent"

        self._updating_mode = True
        self.independent_mode_button.setChecked(requested_mode == "independent")
        self.nested_mode_button.setChecked(requested_mode == "nested")
        self._updating_mode = False

        has_duration, has_instant = self._active_event_types_from_state()
        default_target = "duration" if has_duration and not has_instant else "instant"
        strategy = self._strategy_for_active_types(
            has_duration,
            has_instant,
            segmentation.get("segmentation_strategy", self.config.get("segmentation_strategy", "window")),
        )
        segmentation["segmentation_strategy"] = strategy
        self._epoch_target = default_target
        self._normalization_target = default_target
        self._set_strategy_buttons(strategy)
        self._ensure_parameter_state(has_duration, has_instant)
        self._set_epoch_target_buttons()
        self._set_normalization_target_buttons()
        self._set_epoch_controls_from_state(self._epoch_target)
        self._set_normalization_controls_from_state(self._normalization_target)
        self._sync_strategy_preview()

    def _event_names(self) -> tuple[list[str], list[str]]:
        duration_events = list(self.state.get("duration_events") or [])
        instant_events = list(self.state.get("instant_events") or [])
        if not duration_events and not instant_events:
            instant_events = list(self.state.get("event_types") or [])
        return duration_events, instant_events

    def _current_segmentation_mode(self) -> str:
        return "nested" if self.nested_mode_button.isChecked() else "independent"

    def _nested_mode_available(self) -> bool:
        duration_events, instant_events = self._event_names()
        if not duration_events and not instant_events:
            return False
        # Nested mode only has no meaningful relationship when there is a
        # single duration event and no instant event to place inside it.
        return not (len(duration_events) == 1 and not instant_events)

    def _clear_layout(self, layout: QVBoxLayout | QHBoxLayout | QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            if item.layout():
                self._clear_layout(item.layout())

    def _clear_event_group(self, group: str) -> None:
        list_widget = (self.instant_events_list if group == "instant" else self.duration_events_list)
        list_widget.blockSignals(True)
        list_widget.clearSelection()
        list_widget.blockSignals(False)

    def _independent_events_from_state(self) -> tuple[list[str], list[str]]:
        duration_events: list[str] = []
        instant_events: list[str] = []
        for group in self.state["segmentation"].get("event_groups") or []:
            if group.get("base_event"):
                continue
            duration_events.extend(str(event) for event in group.get("duration_events") or [])
            instant_events.extend(str(event) for event in group.get("instant_events") or [])
        return list(dict.fromkeys(duration_events)), list(dict.fromkeys(instant_events))

    def _refresh_events(self) -> None:
        duration_events, instant_events = self._event_names()
        signature = (tuple(duration_events), tuple(instant_events))
        segmentation = self.state["segmentation"]

        saved_duration, saved_instant = self._independent_events_from_state()
        saved_duration = set(saved_duration)
        saved_instant = set(saved_instant)

        if signature != self._last_event_signature:
            saved_duration &= set(duration_events)
            saved_instant &= set(instant_events)

            if saved_duration and saved_instant:
                saved_instant.clear()

            valid_event_groups = []
            for group in segmentation.get("event_groups") or []:
                base_event = group.get("base_event")
                if not base_event:
                    if saved_duration or saved_instant:
                        valid_event_groups.append(self._event_group(None, list(saved_duration), list(saved_instant)))
                    continue
                if base_event not in duration_events:
                    continue

                nested_duration = [event for event in group.get("duration_events") or []
                    if event in duration_events and event != base_event]
                nested_instant = [event for event in group.get("instant_events") or []
                    if event in instant_events]
                valid_event_groups.append(self._event_group(base_event, list(dict.fromkeys(nested_duration)),
                    list(dict.fromkeys(nested_instant))))
            segmentation["event_groups"] = valid_event_groups

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

        self._update_nested_mode_availability()
        self._refresh_nested_groups_editor()

    def _update_nested_mode_availability(self) -> None:
        available = self._nested_mode_available()
        self.nested_mode_button.setEnabled(available)

        if available:
            self.nested_mode_button.setToolTip("Create relationships between a base duration event and nested duration or instant events.")
        else:
            self.nested_mode_button.setToolTip("Nested mode requires either an instant event or at least two duration events.")

        if not available and self.nested_mode_button.isChecked():
            self._updating_mode = True
            self.independent_mode_button.setChecked(True)
            self._updating_mode = False
            self.state["segmentation"]["event_groups"] = []

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

    def _event_groups(self) -> list[dict[str, Any]]:
        return self.state["segmentation"].setdefault("event_groups", [])

    def _nested_groups(self) -> list[dict[str, Any]]:
        event_groups = self._event_groups()
        event_groups[:] = [group for group in event_groups if group.get("base_event")]
        return event_groups

    def _available_base_events(self) -> list[str]:
        duration_events, _ = self._event_names()
        existing_bases = {group.get("base_event") for group in self._nested_groups()}
        return [event for event in duration_events if event not in existing_bases]

    def _nested_group_for(self, base_event: str) -> dict[str, Any] | None:
        return next((nested_group for nested_group in self._nested_groups() if nested_group.get("base_event") == base_event), None)

    def _available_nested_events(self, group: dict[str, Any], kind: str) -> list[str]:
        nested_child_type = self._nested_child_type()
        if nested_child_type == "mixed" or (
            nested_child_type in {"duration", "instant"} and nested_child_type != kind
        ):
            return []

        duration_events, instant_events = self._event_names()
        base_event = str(group.get("base_event", ""))
        state_key = ("duration_events" if kind == "duration" else "instant_events")
        already_selected = set(group.get(state_key) or [])

        if kind == "duration":
            return [event for event in duration_events if event != base_event and event not in already_selected]

        return [event for event in instant_events if event not in already_selected]

    @staticmethod
    def _set_add_button_state(button: QPushButton, available_events: list[str], available_tooltip: str,
        unavailable_tooltip: str) -> None:
        has_available_events = bool(available_events)
        button.setEnabled(has_available_events)
        button.setToolTip(available_tooltip if has_available_events else unavailable_tooltip)

    def _add_base_events(self) -> None:
        available_events = self._available_base_events()
        if not available_events:
            return

        selected_events = self._select_multiple_events(title="Add base duration events",
            description="Select one or more duration events to use as bases.", events=available_events, kind="duration")
        if not selected_events:
            return

        for event_name in selected_events:
            self._nested_groups().append(self._event_group(event_name, [], []))
        self._sync()

    def _add_nested_events(self, base_event: str, kind: str) -> None:
        kind = self._target_or_default(kind)
        nested_child_type = self._nested_child_type()
        if nested_child_type == "mixed" or (
            nested_child_type in {"duration", "instant"} and nested_child_type != kind
        ):
            return

        group = self._nested_group_for(base_event)
        if group is None:
            return

        state_key = ("duration_events" if kind == "duration" else "instant_events")
        available_events = self._available_nested_events(group, kind)
        if not available_events:
            return

        if kind == "duration":
            description = f"Select duration events contained within {base_event}."
            title = "Add nested duration events"
        else:
            description = f"Select instant events contained within {base_event}."
            title = "Add nested instant events"

        selected_events = self._select_multiple_events(title=title, description=description, events=available_events,
            kind=kind)
        if not selected_events:
            return
        group[state_key] = list(dict.fromkeys([*(group.get(state_key) or []), *selected_events]))
        self._sync()

    def _remove_base_event(self, base_event: str) -> None:
        self.state["segmentation"]["event_groups"] = [group for group in self._nested_groups() if group.get("base_event") != base_event]
        self._sync()

    def _remove_nested_event(self, base_event: str, event_name: str, kind: str) -> None:
        state_key = ("duration_events" if kind == "duration" else "instant_events")
        for group in self._nested_groups():
            if group.get("base_event") == base_event:
                group[state_key] = [event for event in group.get(state_key) or [] if event != event_name]
                break
        self._sync()

    def _select_multiple_events(self, title: str, description: str, events: list[str], kind: str) -> list[str]:
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
        event_list.setProperty("role", "file-list")
        event_list.setObjectName("durationEventsList" if kind == "duration" else "instantEventsList")
        event_list.addItems(events)
        layout.addWidget(event_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []

        return [item.text() for item in event_list.selectedItems()]

    def _refresh_nested_groups_editor(self) -> None:
        self._clear_layout(self.nested_groups_layout)
        if self._current_segmentation_mode() != "nested":
            return
        available_base_events = self._available_base_events()
        self._set_add_button_state(self.add_base_event_button, available_base_events,"Add duration events as base events.",
            "All available duration events are already configured as base events.")
        nested_groups = self._nested_groups()
        nested_child_type = self._nested_child_type()

        if not nested_groups:
            empty = QLabel("No base events added.")
            empty.setObjectName("muted")
            self.nested_groups_layout.addWidget(empty)
            return

        for group in nested_groups:
            base_event = str(group.get("base_event", ""))
            group_container = QFrame()
            group_container.setProperty("role", "nested-group-editor")
            group_layout = QVBoxLayout(group_container)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(8)

            card = QFrame()
            card.setProperty("role", "nested-base-event")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(8)

            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(8)
            base_title = QLabel(base_event)
            base_title.setObjectName("nestedBaseEventTitle")
            base_title.setWordWrap(True)
            header.addWidget(base_title)
            header.addStretch()

            remove_base_button = QPushButton("Remove")
            remove_base_button.setProperty("variant", "ghost")
            remove_base_button.clicked.connect(lambda _=False, event=base_event: self._remove_base_event(event))
            header.addWidget(remove_base_button)
            card_layout.addLayout(header)

            children_container = QFrame()
            children_container.setProperty("role", "nested-contained-events")
            children_row = QHBoxLayout(children_container)
            children_row.setContentsMargins(10, 8, 10, 8)
            children_row.setSpacing(6)
            nested_duration = list(group.get("duration_events") or [])
            nested_instant = list(group.get("instant_events") or [])

            for event_name in nested_duration:
                children_row.addWidget(self._summary_chip(event_name, "duration", removable=True,
                    on_remove=lambda _=False, event=event_name, base=base_event: self._remove_nested_event(base, event, "duration"), compact=True))

            for event_name in nested_instant:
                children_row.addWidget(self._summary_chip(event_name, "instant", removable=True,
                    on_remove=lambda _=False, event=event_name, base=base_event: self._remove_nested_event(base, event,"instant"), compact=True))

            if not nested_duration and not nested_instant:
                empty = QLabel("No nested events selected.")
                empty.setObjectName("muted")
                children_row.addWidget(empty)

            children_row.addStretch()
            card_layout.addWidget(children_container)
            group_layout.addWidget(card)

            actions = QHBoxLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            actions.setSpacing(8)
            add_duration_button = QPushButton("+ Add duration event")
            add_instant_button = QPushButton("+ Add instant event")
            add_duration_button.setProperty("variant", "secondary")
            add_duration_button.setProperty("role", "segmentation-duration-action")
            add_instant_button.setProperty("variant", "secondary")
            add_instant_button.setProperty("role", "segmentation-instant-action")
            available_nested_duration = self._available_nested_events(group, "duration")
            available_nested_instant = self._available_nested_events(group, "instant")
            mixed_tooltip = (
                "Nested mode already contains both duration and instant events. Remove one type before adding more."
            )
            duration_unavailable_tooltip = (
                mixed_tooltip if nested_child_type == "mixed"
                else "Nested mode is already using instant nested events."
                if nested_child_type == "instant"
                else "No additional duration events are available for this base event."
            )
            instant_unavailable_tooltip = (
                mixed_tooltip if nested_child_type == "mixed"
                else "Nested mode is already using duration nested events."
                if nested_child_type == "duration"
                else "No additional instant events are available for this base event."
            )
            self._set_add_button_state(add_duration_button, available_nested_duration,
                f"Add duration events contained within {base_event}.",
                duration_unavailable_tooltip)
            self._set_add_button_state(add_instant_button, available_nested_instant,
                f"Add instant events contained within {base_event}.",
                instant_unavailable_tooltip)

            add_duration_button.clicked.connect(lambda _=False, base=base_event: self._add_nested_events(base, "duration"))
            add_instant_button.clicked.connect(lambda _=False, base=base_event: self._add_nested_events(base, "instant"))

            actions.addWidget(add_duration_button)
            actions.addWidget(add_instant_button)
            actions.addStretch()
            group_layout.addLayout(actions)

            self.nested_groups_layout.addWidget(group_container)

    def _nested_event_types(self) -> tuple[bool, bool]:
        nested_groups = self._nested_groups()
        has_duration = any(group.get("duration_events") for group in nested_groups)
        has_instant = any(group.get("instant_events") for group in nested_groups)
        return has_duration, has_instant

    def _nested_child_type(self) -> str | None:
        has_duration, has_instant = self._nested_event_types()
        if has_duration and has_instant:
            return "mixed"
        if has_duration:
            return "duration"
        if has_instant:
            return "instant"
        return None

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
            duration_events, instant_events = self._current_event_selection()
            has_duration_epochs = bool(duration_events)
            has_instant_epochs = bool(instant_events)
        else:
            has_duration_epochs, has_instant_epochs = self._nested_event_types()

        strategy = self._strategy_for_active_types(has_duration_epochs, has_instant_epochs, self._current_state_strategy())
        has_active_events = has_duration_epochs or has_instant_epochs
        duration_strategy_available = has_duration_epochs and not has_instant_epochs
        self.strategy_panel.setVisible(has_active_events)
        self.window_strategy_button.setVisible(duration_strategy_available)
        self.window_strategy_button.setEnabled(duration_strategy_available)
        self.onset_strategy_button.setEnabled(has_active_events)
        self.window_segmentation_widget.setVisible(duration_strategy_available and strategy == "window")
        self.onset_segmentation_widget.setVisible(has_active_events and strategy == "onset")

        self.epoch_target_panel.setVisible(False)
        self.normalization_target_panel.setVisible(False)

        normalization = self.normalization_enabled.isChecked()
        thresholding = self.threshold_enabled.isChecked()
        resampling = self.resampling_enabled.isChecked()
        epoch_target = self._target_or_default(self._epoch_target)
        normalization_target = self._target_or_default(self._normalization_target)
        show_epoch_instant = (
            has_instant_epochs and epoch_target == "instant"
        ) or (
            has_duration_epochs and epoch_target == "duration" and strategy == "onset"
        )
        show_epoch_duration = has_duration_epochs and epoch_target == "duration" and strategy == "window"
        show_any_epoch_controls = show_epoch_instant or show_epoch_duration

        self._set_visible([self.epoch_start_label, self.epoch_start, self.epoch_end_label, self.epoch_end],
            show_epoch_instant)
        self._set_visible([self.duration_epoch_length_label, self.duration_epoch_length, self.stride_label,
                self.stride], show_epoch_duration)
        self.stride_label.setText("Overlap" if show_epoch_duration else "Stride")
        self.average_epochs.setVisible(show_any_epoch_controls)

        baseline_visible = normalization and (
            has_instant_epochs and normalization_target == "instant"
            or has_duration_epochs and normalization_target == "duration" and strategy == "onset"
        )
        self._set_visible([self.baseline_start_label, self.baseline_start, self.baseline_end_label,
                self.baseline_end], baseline_visible)

        self.normalization_mode.setEnabled(normalization)
        self.baseline_start.setEnabled(baseline_visible)
        self.baseline_end.setEnabled(baseline_visible)

        for widget in (self.threshold_sigma, self.threshold_samples, self.threshold_channels):
            widget.setEnabled(thresholding)

        self.target_sampling_frequency.setEnabled(resampling)

        if independent:
            self.mode_help.setText("Select either duration events or instant events. The two lists are mutually exclusive.")
        else:
            self.mode_help.setText("Create parent-child relationships using one nested event type across all base events.")

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
        elif mode == "nested":
            nested_groups = self._nested_groups()
            relation_count = sum(len(group.get("duration_events") or []) + len(group.get("instant_events") or [])
                for group in nested_groups)
            text = (f"{len(nested_groups)} nested group(s) with " f"{relation_count} relationship(s) configured.")
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

    def _summary_chip(self, text: str, kind: str, removable: bool = False, on_remove: Any | None = None,
        base: bool = False, compact: bool = False) -> QFrame:
        chip = QFrame()
        if compact:
            chip.setProperty("compact", "true")
        chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        if base and kind == "duration":
            chip.setObjectName("summaryBaseDurationChip")
        elif kind == "duration":
            chip.setObjectName("summaryDurationChip")
        else:
            chip.setObjectName("summaryInstantChip")

        use_corner_remove = compact and removable and on_remove is not None
        if use_corner_remove:
            layout = QGridLayout(chip)
            layout.setContentsMargins(8, 5, 3, 4)
            layout.setHorizontalSpacing(4)
            layout.setVerticalSpacing(0)
        else:
            layout = QHBoxLayout(chip)
            if compact:
                layout.setContentsMargins(8, 3, 8, 3)
                layout.setSpacing(3)
            else:
                layout.setContentsMargins(10, 6, 10, 6)
                layout.setSpacing(5)

        label = QLabel(text)
        label.setWordWrap(True)
        if use_corner_remove:
            layout.addWidget(label, 0, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            layout.addWidget(label)

        if removable and on_remove is not None:
            remove_button = QPushButton("x")
            remove_button.setObjectName("chipRemoveButton")
            remove_button.setProperty("role", "chip-remove-button")
            remove_button.setFixedSize(16 if compact else 20, 16 if compact else 20)
            remove_button.setToolTip(f"Remove {text}")
            remove_button.clicked.connect(on_remove)
            if use_corner_remove:
                layout.addWidget(
                    remove_button,
                    0,
                    1,
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                )
            else:
                layout.addWidget(remove_button)

        return chip

    def _refresh_summary(self, mode: str, duration_events: list[str], instant_events: list[str]) -> None:
        self.summary_panel.setVisible(mode != "nested")
        self._clear_layout(self.summary_layout)

        if mode == "nested":
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

    def _active_event_types(self, mode: str, selection_mode: str) -> tuple[bool, bool]:
        if mode == "nested":
            return self._nested_event_types()
        return selection_mode == "duration", selection_mode == "instant"

    def _sync(self, *_: Any) -> None:
        if self._syncing_parameter_controls:
            return

        mode = self._current_segmentation_mode()
        duration_events, instant_events = self._current_event_selection()

        if mode == "nested":
            selected_duration_events: list[str] = []
            selected_instant_events: list[str] = []
            event_groups = deepcopy(self._nested_groups())
        else:
            selected_duration_events = duration_events
            selected_instant_events = instant_events
            event_groups = ([self._event_group(None, selected_duration_events, selected_instant_events)]
                if selected_duration_events or selected_instant_events else [])

        selection_mode = self._selection_mode_for_state(mode, selected_duration_events, selected_instant_events)
        has_duration_epochs, has_instant_epochs = self._active_event_types(mode, selection_mode)
        segmentation_strategy = self._strategy_for_active_types(
            has_duration_epochs,
            has_instant_epochs,
            self._current_segmentation_strategy(),
        )
        previous_segmentation = self.state["segmentation"]
        previous_epoch_parameters = deepcopy(previous_segmentation.get("epoch_parameters") or {})
        previous_normalization = deepcopy(previous_segmentation.get("normalization") or {})

        self.state["segmentation"] = {
            "segmentation_mode": mode,
            "segmentation_strategy": segmentation_strategy,
            "event_groups": event_groups,
            "epoch_parameters": {
                "duration": deepcopy(previous_epoch_parameters.get("duration") or {}),
                "instant": deepcopy(previous_epoch_parameters.get("instant") or {}),
            },
            "normalization": {
                "duration": deepcopy(previous_normalization.get("duration") or {}),
                "instant": deepcopy(previous_normalization.get("instant") or {}),
            },
            "thresholding": {"enabled": self.threshold_enabled.isChecked(),
                "sigma": self.threshold_sigma.value(),
                "samples": self.threshold_samples.value(),
                "channels": self.threshold_channels.value()},
            "resampling": {
                "enabled": self.resampling_enabled.isChecked(),
                "target_sampling_frequency": self.target_sampling_frequency.value()}}

        self._align_segmentation_strategy(has_duration_epochs, has_instant_epochs)

        if self._epoch_target == "duration" and has_duration_epochs:
            self._store_epoch_controls("duration")
        elif self._epoch_target == "instant" and has_instant_epochs:
            self._store_epoch_controls("instant")

        if self._normalization_target == "duration" and has_duration_epochs:
            self._store_normalization_controls("duration")
        elif self._normalization_target == "instant" and has_instant_epochs:
            self._store_normalization_controls("instant")

        self._ensure_parameter_state(has_duration_epochs, has_instant_epochs)
        self._align_parameter_targets(mode, selection_mode)
        self._ensure_parameter_state(has_duration_epochs, has_instant_epochs)

        self._set_dependent_enabled(mode)
        self._sync_strategy_preview()
        self._refresh_nested_groups_editor()
        self._refresh_summary(mode, selected_duration_events, selected_instant_events)
        self.validation_errors = self._validate()
        self._update_status_label(mode, selected_duration_events, selected_instant_events)
        self.changed.emit()

    def _validate(self) -> list[str]:
        segmentation = self.state["segmentation"]
        mode = segmentation["segmentation_mode"]
        independent_duration_events, independent_instant_events = self._independent_events_from_state()
        selection_mode = self._selection_mode_for_state(mode,
            independent_duration_events,
            independent_instant_events)
        errors: list[str] = []

        if mode == "nested":
            if not self._nested_mode_available():
                errors.append("Nested mode requires either an instant event or at least two duration events.")
            else:
                nested_groups = self._nested_groups()
                errors.extend(self.validation.validate_many(nested_groups, [("minimum_length", {"minimum": 1,
                                    "item_name": "base duration event", "action": "add"})], label="Event groups"))
                has_nested_duration = any(group.get("duration_events") for group in nested_groups)
                has_nested_instant = any(group.get("instant_events") for group in nested_groups)
                if has_nested_duration and has_nested_instant:
                    errors.append("Nested mode supports either duration or instant nested events, not both.")

                seen_bases: set[str] = set()
                for group in nested_groups:
                    base_event = group.get("base_event")
                    if not base_event:
                        errors.append("Nested group: base duration event is missing.")
                        continue
                    if base_event in seen_bases:
                        errors.append(f"Nested groups: base event '{base_event}' is duplicated.")
                    seen_bases.add(base_event)
                    nested_duration = list(group.get("duration_events") or [])
                    nested_instant = list(group.get("instant_events") or [])

                    if base_event in nested_duration:
                        errors.append(f"{base_event}: a base event cannot contain itself.")
                    if not nested_duration and not nested_instant:
                        errors.append(f"{base_event}: select at least one nested event.")

        elif selection_mode == "duration":
            errors.extend(
                self.validation.validate_many(independent_duration_events,[("minimum_length",
                            {"minimum": 1, "item_name": "duration event", "action": "select"})], label="Duration events"))
        elif selection_mode == "instant":
            errors.extend(self.validation.validate_many(independent_instant_events,
                    [("minimum_length", {"minimum": 1, "item_name": "instant event", "action": "select"})], label="Instant events"))
        else:
            errors.append("Signal events: select at least one event.")

        self._ensure_parameter_state()
        duration_epoch = self._epoch_state("duration", create=False)
        instant_epoch = self._epoch_state("instant", create=False)
        duration_normalization = self._normalization_state("duration", create=False)
        instant_normalization = self._normalization_state("instant", create=False)

        has_duration_epochs, has_instant_epochs = self._active_event_types(mode, selection_mode)
        strategy = self._current_state_strategy()

        def validate_stride(value: Any, label: str) -> None:
            errors.extend(self.validation.validate_many(value,["integer", ("greater_or_equal", {"minimum": 0, "suffix": " %"}),
                    ("less_or_equal", {"maximum": 100, "suffix": " %"})], label=label, stop_on_first_error=False))

        def validate_duration_epoch() -> int:
            errors.extend(self.validation.validate_many(duration_epoch["duration_epoch_length_ms"],
                    ["integer", ("greater_than", {"minimum": 0, "suffix": " ms"})],
                    label="Duration epoch length" if mode == "nested" else "Epoch length",
                    stop_on_first_error=False))
            validate_stride(duration_epoch["stride_percent"], "Duration overlap" if mode == "nested" else "Overlap")
            return int(duration_epoch["duration_epoch_length_ms"])

        def validate_onset_epoch(epoch_config: dict[str, Any], target: str) -> int:
            epoch = epoch_config["epoch_window_ms"]
            start = epoch["start"]
            end = epoch["end"]
            start_label = "Epoch start"
            end_label = "Epoch end"
            if mode == "nested" or target == "duration":
                start_label = f"{target.title()} epoch start"
                end_label = f"{target.title()} epoch end"
            errors.extend(self.validation.validate_many(start, ["integer"],
                            label=start_label))
            errors.extend(self.validation.validate_many(end, ["integer"],
                                    label=end_label))
            if end <= start:
                prefix = f"{target.title()} epoch window" if mode == "nested" or target == "duration" else "Epoch window"
                errors.append(f"{prefix}: end must be greater than start.")
                return 0
            if "stride_percent" in epoch_config:
                validate_stride(epoch_config["stride_percent"], f"{target.title()} stride" if mode == "nested" else "Stride")
            return int(end - start)

        def validate_normalization(normalization: dict[str, Any], target: str, epoch_window: dict[str, int] | None) -> None:
            if not normalization.get("enabled", False):
                return
            prefix = f"{target.title()} normalization" if mode == "nested" else "Normalization"
            errors.extend(self.validation.validate_many(normalization.get("mode"),
                    [("one_of", {"options": ["mean", "mean_std"]})], label=f"{prefix} mode"))
            if epoch_window is None:
                return
            baseline = normalization.get("baseline_window_ms", {})
            base_start = baseline.get("start")
            base_end = baseline.get("end")
            if base_end <= base_start:
                errors.append(f"{prefix} baseline window: end must be greater than start.")
            if base_start < epoch_window["start"] or base_end > epoch_window["end"]:
                errors.append(f"{prefix} baseline window must be inside the onset epoch window.")

        epoch_lengths_ms: list[int] = []
        if has_duration_epochs:
            epoch_length = validate_duration_epoch() if strategy == "window" else validate_onset_epoch(duration_epoch, "duration")
            if epoch_length > 0:
                epoch_lengths_ms.append(epoch_length)

        if has_instant_epochs:
            epoch_length = validate_onset_epoch(instant_epoch, "instant")
            if epoch_length > 0:
                epoch_lengths_ms.append(epoch_length)

        if mode == "nested":
            if has_duration_epochs:
                validate_normalization(duration_normalization, "duration",
                    duration_epoch["epoch_window_ms"] if strategy == "onset" else None)
            if has_instant_epochs:
                validate_normalization(instant_normalization, "instant", instant_epoch["epoch_window_ms"])
        else:
            if selection_mode == "duration":
                validate_normalization(duration_normalization, "duration",
                    duration_epoch["epoch_window_ms"] if strategy == "onset" else None)
            elif selection_mode == "instant":
                validate_normalization(instant_normalization, "instant", instant_epoch["epoch_window_ms"])

        smallest_epoch_ms = min(epoch_lengths_ms) if epoch_lengths_ms else 0
        epoch_samples = (int(smallest_epoch_ms * float(self.source_sampling_frequency or 0)/ 1000) if smallest_epoch_ms > 0
            else 0)
        n_channels = int((self.state.get("metadata") or {}).get("n_channels") or 0)
        thresholding = segmentation["thresholding"]

        if thresholding["enabled"]:
            errors.extend(self.validation.validate_many(thresholding["sigma"], ["finite_number", ("greater_than", {"minimum": 0})],
                    label="Threshold sigma", stop_on_first_error=False))
            errors.extend(self.validation.validate_many(thresholding["samples"], ["integer", ("greater_or_equal", {"minimum": 1})],
                    label="Threshold samples", stop_on_first_error=False))
            errors.extend(self.validation.validate_many(thresholding["channels"], ["integer", ("greater_or_equal", {"minimum": 1})],
                    label="Threshold channels", stop_on_first_error=False))
            if epoch_samples and thresholding["samples"] > epoch_samples:
                errors.append("Threshold samples cannot exceed the smallest configured epoch sample count.")
            if n_channels and thresholding["channels"] > n_channels:
                errors.append("Threshold channels cannot exceed the loaded channel count.")

        resampling = segmentation["resampling"]
        if resampling["enabled"]:
            target = resampling["target_sampling_frequency"]
            errors.extend(self.validation.validate_many(target,["integer", ("greater_or_equal", {"minimum": 250, "suffix": " Hz"})],
                    label="Target sample frequency", stop_on_first_error=False))

            if self.source_sampling_frequency is not None:
                errors.extend(self.validation.validate_many(target,[("less_or_equal", {"maximum":
                            self.source_sampling_frequency, "suffix": " Hz",})], label="Target sample frequency",))

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
