from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QWidget

from medusa_analyzer.frontend.widgets.experiment_card import ExperimentCard


class ModuleGrid(QWidget):
    """Responsive Qt grid that keeps module cards compact and centered."""

    CARD_MIN_WIDTH = 244
    CARD_MAX_WIDTH = 304
    CARD_HEIGHT = 344
    GAP = 22

    def __init__(self):
        super().__init__()
        self.setObjectName("moduleGrid")
        self.cards: list[ExperimentCard] = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(self.GAP)
        self.grid.setVerticalSpacing(self.GAP)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

    def add_card(self, card: ExperimentCard) -> None:
        self.cards.append(card)
        self._reflow()

    def _column_count(self) -> int:
        if not self.cards:
            return 1
        available = max(1, self.width())
        possible = max(1, (available + self.GAP) // (self.CARD_MIN_WIDTH + self.GAP))
        return min(len(self.cards), possible, 4)

    def _reflow(self) -> None:
        while self.grid.count():
            self.grid.takeAt(0)
        columns = self._column_count()
        available = max(1, self.width())
        width_per_column = (available - self.GAP * (columns - 1)) // columns
        card_width = min(self.CARD_MAX_WIDTH, max(208, width_per_column))
        for index, card in enumerate(self.cards):
            card.set_card_width(card_width)
            self.grid.addWidget(card, index // columns, index % columns)
        rows = (len(self.cards) + columns - 1) // columns
        self.setMinimumHeight(rows * self.CARD_HEIGHT + max(0, rows - 1) * self.GAP)

    def resizeEvent(self, event) -> None:
        self._reflow()
        super().resizeEvent(event)
