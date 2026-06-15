from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame


@dataclass(frozen=True, slots=True)
class FilterResponse:
    frequencies: list[float]
    magnitude_db: list[float]


class FilterPreviewPlot(QFrame):
    def __init__(self):
        super().__init__()
        self.setProperty("role", "plot")
        self.setMinimumHeight(225)
        self.response: FilterResponse | None = None

    def set_response(self, response: FilterResponse | None) -> None:
        self.response = response
        self.update()

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
        painter.fillRect(plot, QColor("#FBFAF8"))

        maximum_frequency = max(self.response.frequencies) if self.response and self.response.frequencies else 1.0
        axis_maximum, frequency_ticks = self._frequency_ticks(maximum_frequency, plot.width())

        painter.setPen(QPen(QColor("#E5DFDD"), 1))
        for index in range(5):
            y = plot.top() + plot.height() * index / 4
            painter.drawLine(plot.left(), int(y), plot.right(), int(y))

        for frequency in frequency_ticks:
            x = plot.left() + plot.width() * frequency / axis_maximum
            painter.drawLine(int(x), plot.top(), int(x), plot.bottom())

        painter.setPen(QPen(QColor("#B8B0B4"), 1))
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())

        axis_font = QFont(painter.font())
        axis_font.setPointSizeF(max(7.0, axis_font.pointSizeF() - 1.0))
        painter.setFont(axis_font)
        painter.setPen(QColor("#756F77"))
        painter.drawText(QRectF(5, plot.top(), 38, 20), Qt.AlignmentFlag.AlignRight, "0 dB")
        painter.drawText(QRectF(5, plot.bottom() - 15, 38, 20), Qt.AlignmentFlag.AlignRight, "-80")

        for frequency in frequency_ticks:
            x = plot.left() + plot.width() * frequency / axis_maximum
            label_width = 58.0
            label_left = max(1.0, min(self.width() - label_width - 1.0, x - label_width / 2))
            painter.drawText(
                QRectF(label_left, plot.bottom() + 4, label_width, 17),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                f"{frequency:g}",
            )

        painter.drawText(
            plot.left(),
            plot.bottom() + 25,
            plot.width(),
            20,
            Qt.AlignmentFlag.AlignCenter,
            "Frequency (Hz)",
        )
        if not self.response or len(self.response.frequencies) < 2:
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "Valid configuration required")
            return

        path = QPainterPath()
        for index, (frequency, magnitude) in enumerate(zip(self.response.frequencies, self.response.magnitude_db)):
            x = plot.left() + plot.width() * frequency / axis_maximum
            y = plot.bottom() - plot.height() * min(80, max(0, magnitude + 80)) / 80
            point = QPointF(x, y)
            path.moveTo(point) if index == 0 else path.lineTo(point)
        painter.setPen(QPen(QColor("#0E7C86"), 2.4))
        painter.drawPath(path)
