from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class DashboardHero(QFrame):
    """Painted dashboard header with restrained biomedical color accents."""

    def __init__(self):
        super().__init__()
        self.setObjectName("dashboardHero")
        self.setMinimumHeight(224)

        root = QVBoxLayout(self)
        root.setContentsMargins(42, 32, 42, 32)
        root.setSpacing(0)

        eyebrow = QLabel("MEDUSA BCI WORKSPACE")
        eyebrow.setObjectName("dashboardEyebrow")
        title = QLabel("Medusa Analyzer")
        title.setObjectName("dashboardHeroTitle")
        title.setWordWrap(True)
        subtitle = QLabel("Biomedical signal processing workspace")
        subtitle.setObjectName("dashboardHeroSubtitle")
        subtitle.setWordWrap(True)

        root.addWidget(eyebrow)
        root.addSpacing(12)
        root.addWidget(title)
        root.addSpacing(8)
        root.addWidget(subtitle)
        root.addSpacing(22)

        self.chips = QHBoxLayout()
        self.chips.setSpacing(9)
        for text, tone in (
            ("Guided pipelines", "burgundy"),
            ("Scientific workspace", "teal"),
        ):
            chip = QLabel(text)
            chip.setObjectName("heroChip")
            chip.setProperty("tone", tone)
            self.chips.addWidget(chip)
            self.chips.addStretch()
        root.addLayout(self.chips)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(bounds, 24, 24)

        gradient = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        gradient.setColorAt(0.0, QColor("#FFFDFC"))
        gradient.setColorAt(0.52, QColor("#F8EEF1"))
        gradient.setColorAt(1.0, QColor("#EDF7F6"))
        painter.fillPath(path, gradient)
        painter.setPen(QPen(QColor("#E7D9DD"), 1))
        painter.drawPath(path)

    def resizeEvent(self, event) -> None:
        compact = self.width() < 620
        stacked_chips = self.width() < 310
        if self.property("compact") != compact:
            self.setProperty("compact", compact)
            self.style().unpolish(self)
            self.style().polish(self)
            margins = (24, 26, 24, 27) if compact else (42, 32, 42, 32)
            self.layout().setContentsMargins(*margins)
        direction = (
            QHBoxLayout.Direction.TopToBottom
            if stacked_chips
            else QHBoxLayout.Direction.LeftToRight
        )
        if self.chips.direction() != direction:
            self.chips.setDirection(direction)
            self.chips.setSpacing(7 if stacked_chips else 9)
        super().resizeEvent(event)
