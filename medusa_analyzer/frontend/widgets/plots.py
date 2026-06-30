from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Property, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame


@dataclass(frozen=True, slots=True)
class PlotSeries:
    """Serie genérica de puntos para un line plot."""
    x_values: list[float]
    y_values: list[float]


class LinePlot(QFrame):
    """Widget genérico para pintar una curva con ejes y mensaje vacío."""
    def __init__(self, *, x_axis_label: str | None = None, top_axis_label: str | None = None,
        bottom_axis_label: str | None = None, y_minimum: float = 0.0, y_maximum: float = 1.0,
        empty_message: str = "Valid configuration required"): # inicializamos el widget de la gráfica, sus colores y su estado vacío
        super().__init__()
        self.setProperty("role", "plot")
        self.setMinimumHeight(225)
        self._plot_background_color = QColor("#FBFAF8")
        self._grid_color = QColor("#E5DFDD")
        self._axis_line_color = QColor("#B8B0B4")
        self._axis_text_color = QColor("#756F77")
        self._response_line_color = QColor("#0E7C86")
        self._empty_message_color = QColor("#756F77")
        self.series: PlotSeries | None = None # Guarda la serie genérica
        self.empty_message = empty_message # Guarda mensaje vacío si no hay gráfica
        self.x_axis_label = x_axis_label
        self.top_axis_label = top_axis_label
        self.bottom_axis_label = bottom_axis_label
        self.y_minimum = float(y_minimum)
        self.y_maximum = float(y_maximum)

    def set_series(self, series: PlotSeries | None, empty_message: str | None = None) -> None:
        """Guarda la serie o el mensaje vacío y repinta el widget."""
        self.series = series
        self.empty_message = empty_message or "Valid configuration required"
        self.update()

    def _set_color(self, attribute: str, value) -> None:
        """Cambia uno de los colores internos y repinta."""
        setattr(self, attribute, QColor(value))
        self.update()

    def get_plot_background_color(self) -> QColor:
        """Devuelve el color del fondo de la gráfica."""
        return self._plot_background_color

    def set_plot_background_color(self, value) -> None:
        self._set_color("_plot_background_color", value) # cambia el color de fondo de la gráfica

    def get_grid_color(self) -> QColor:
        return self._grid_color # devuelve el color de la rejilla

    def set_grid_color(self, value) -> None:
        self._set_color("_grid_color", value) # cambia el color de la rejilla

    def get_axis_line_color(self) -> QColor:
        return self._axis_line_color # devuelve el color de la línea del eje

    def set_axis_line_color(self, value) -> None:
        self._set_color("_axis_line_color", value) # cambia el color de la línea del eje

    def get_axis_text_color(self) -> QColor:
        return self._axis_text_color # devuelve el color del texto de los ejes

    def set_axis_text_color(self, value) -> None:
        self._set_color("_axis_text_color", value) # cambia el color del texto de los ejes

    def get_response_line_color(self) -> QColor: # devuelve el color de la curva de la respuesta
        return self._response_line_color

    def set_response_line_color(self, value) -> None: # cambia el color de la curva de la respuesta
        self._set_color("_response_line_color", value)

    def get_empty_message_color(self) -> QColor:
        return self._empty_message_color # devuelve el color del mensaje cuando no hay gráfica

    def set_empty_message_color(self, value) -> None:
        self._set_color("_empty_message_color", value) # cambia el color del mensaje vacío

    @staticmethod
    def _nice_step(value: float) -> float:
        """Función para que el eje X del gráfico quede bonito. Va de la mano de _x_ticks."""
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
    def _x_ticks(cls, maximum_x: float, plot_width: float) -> tuple[float, list[float]]:
        """Función para que el eje X del gráfico quede bonito. Va de la mano de _nice_step."""
        target_intervals = max(2, min(6, int(plot_width // 72)))
        step = cls._nice_step(maximum_x / target_intervals)
        axis_maximum = max(step, math.ceil(maximum_x / step) * step)
        tick_count = int(round(axis_maximum / step))
        ticks = [index * step for index in range(tick_count + 1)]
        return axis_maximum, ticks

    def paintEvent(self, event):
        """Función para pintar todoo del gráfico: fondo, rejilla, ejes, etiquetas, mensaje vacío si no hay respuesta,
        curva (si la hay), etc."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self.rect().adjusted(48, 18, -18, -55)
        painter.fillRect(plot, self._plot_background_color)

        maximum_x = max(self.series.x_values) if self.series and self.series.x_values else 1.0
        axis_maximum, x_ticks = self._x_ticks(maximum_x, plot.width())

        painter.setPen(QPen(self._grid_color, 1))
        for index in range(5):
            y = plot.top() + plot.height() * index / 4
            painter.drawLine(plot.left(), int(y), plot.right(), int(y))

        for x_tick in x_ticks:
            x = plot.left() + plot.width() * x_tick / axis_maximum
            painter.drawLine(int(x), plot.top(), int(x), plot.bottom())

        painter.setPen(QPen(self._axis_line_color, 1))
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())

        axis_font = QFont(painter.font())
        axis_font.setPointSizeF(max(7.0, axis_font.pointSizeF() - 1.0))
        painter.setFont(axis_font)
        painter.setPen(self._axis_text_color)
        if self.top_axis_label:
            painter.drawText(QRectF(5, plot.top(), 38, 20), Qt.AlignmentFlag.AlignRight, self.top_axis_label)
        if self.bottom_axis_label:
            painter.drawText(QRectF(5, plot.bottom() - 15, 38, 20), Qt.AlignmentFlag.AlignRight, self.bottom_axis_label)

        for x_tick in x_ticks:
            x = plot.left() + plot.width() * x_tick / axis_maximum
            label_width = 58.0
            label_left = max(1.0, min(self.width() - label_width - 1.0, x - label_width / 2))
            painter.drawText(QRectF(label_left, plot.bottom() + 4, label_width, 17),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{x_tick:g}")

        if self.x_axis_label:
            painter.drawText(plot.left(), plot.bottom() + 25, plot.width(), 20, Qt.AlignmentFlag.AlignCenter,
                self.x_axis_label)
        if not self.series or len(self.series.x_values) < 2 or len(self.series.y_values) < 2:
            painter.setPen(self._empty_message_color)
            painter.drawText(plot.adjusted(24, 24, -24, -24), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self.empty_message)
            return

        y_span = self.y_maximum - self.y_minimum
        if y_span <= 0:
            y_span = 1.0

        path = QPainterPath()
        for index, (x_value, y_value) in enumerate(zip(self.series.x_values, self.series.y_values)):
            x = plot.left() + plot.width() * x_value / axis_maximum
            clamped_y = min(self.y_maximum, max(self.y_minimum, y_value))
            y_ratio = (clamped_y - self.y_minimum) / y_span
            y = plot.bottom() - plot.height() * y_ratio
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


__all__ = ["LinePlot", "PlotSeries"]
