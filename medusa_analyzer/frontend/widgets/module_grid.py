from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QWidget

from medusa_analyzer.frontend.widgets.experiment_card import ExperimentCard


class ModuleGrid(QWidget):
    """Widget que coloca las tarjetas del dashboard en una cuadrícula responsive. Recibe varias
    experimentCards y decide cuántas columnas caben, qué ancho debe tener cada tarjeta, en qué fila
    y columna va cada tarjeta y qué altura mínima necesita el grid."""

    # Constantes que controlan el layout
    CARD_MIN_WIDTH = 244
    CARD_MAX_WIDTH = 304
    CARD_COMPACT_WIDTH = 208
    CARD_HEIGHT = 344
    GAP = 22 # espacio vertical/horizontal entre tarjetas

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
        """ Añade una tarjeta al grid. """
        self.cards.append(card)
        self._reflow() # recalcula la distribución completa

    def _column_count(self) -> int:
        """ Calcula cuántas columnas deben usarse según el ancho disponible"""
        if not self.cards:
            return 1
        available = max(1, self.width())  # ancho actual
        # calculamos cuántas tarjetas de ancho mínimo caben
        possible = max(1, (available + self.GAP) // (self.CARD_MIN_WIDTH + self.GAP))
        return min(len(self.cards), possible, 4)

    def _reflow(self) -> None:
        """ Recalcula toda la cuadrícula. Se llama cuando añadimos una tarjeta o cambia el tamaño del grid."""
        while self.grid.count():
            self.grid.takeAt(0) # vacía el layout, pero no destruye las tarjetas (siguen en self.cards)
        columns = self._column_count()  # calcula cuántas columnas a usar
        available = max(1, self.width()) # lee ancho disponible
        width_per_column = (available - self.GAP * (columns - 1)) // columns
        card_width = min(self.CARD_MAX_WIDTH, max(self.CARD_COMPACT_WIDTH, width_per_column)) # ancho final de las tarjetas
        for index, card in enumerate(self.cards):
            card.set_card_width(card_width)  # decimos a cada tarjeta qué ancho tener (métoodo de module_grid)
            self.grid.addWidget(card, index // columns, index % columns)
        rows = (len(self.cards) + columns - 1) // columns
        self.setMinimumHeight(rows * self.CARD_HEIGHT + max(0, rows - 1) * self.GAP)

    def resizeEvent(self, event) -> None:
        self._reflow()
        super().resizeEvent(event)
