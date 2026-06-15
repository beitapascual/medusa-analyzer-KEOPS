from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class DashboardHero(QFrame):
    """Dashboard header styled entirely through the global QSS theme."""

    def __init__(self):
        super().__init__()
        self.setObjectName("dashboardHero")
        self.setMinimumHeight(224)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

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