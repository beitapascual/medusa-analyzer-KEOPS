from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame

from medusa_analyzer.backend.filters.response import FilterResponse


class FilterPreviewPlot(QFrame):
    def __init__(self):
        super().__init__()
        self.setProperty("role", "plot")
        self.setMinimumHeight(205)
        self.response: FilterResponse | None = None

    def set_response(self, response: FilterResponse) -> None:
        self.response = response
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self.rect().adjusted(46, 18, -18, -34)
        painter.fillRect(plot, QColor("#FBFAF8"))
        painter.setPen(QPen(QColor("#E5DFDD"), 1))
        for index in range(5):
            y = plot.top() + plot.height() * index / 4
            painter.drawLine(plot.left(), int(y), plot.right(), int(y))
        painter.setPen(QColor("#756F77"))
        painter.drawText(QRectF(5, plot.top(), 38, 20), Qt.AlignmentFlag.AlignRight, "0 dB")
        painter.drawText(QRectF(5, plot.bottom() - 15, 38, 20), Qt.AlignmentFlag.AlignRight, "-80")
        painter.drawText(plot.left(), plot.bottom() + 8, plot.width(), 22, Qt.AlignmentFlag.AlignCenter, "Frequency (Hz)")
        if not self.response or len(self.response.frequencies) < 2:
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "Valid configuration required")
            return
        maximum = max(self.response.frequencies) or 1
        path = QPainterPath()
        for index, (frequency, magnitude) in enumerate(zip(
            self.response.frequencies, self.response.magnitude_db
        )):
            x = plot.left() + plot.width() * frequency / maximum
            y = plot.bottom() - plot.height() * min(80, max(0, magnitude + 80)) / 80
            point = QPointF(x, y)
            path.moveTo(point) if index == 0 else path.lineTo(point)
        painter.setPen(QPen(QColor("#0E7C86"), 2.4))
        painter.drawPath(path)
