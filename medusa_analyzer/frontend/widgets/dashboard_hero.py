from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class DashboardHero(QFrame):
    """Cabecera grande del dashboard. El bloque superior con el nombre de la app, una frase descriptiva
    y unas "chips" o etiquetas pequeñas."""

    def __init__(self):
        super().__init__()
        self.setObjectName("dashboardHero")
        self.setMinimumHeight(224)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True) # esto es para que el fondo se pinte
        # bien a partir del QSS

        root = QVBoxLayout(self)
        root.setContentsMargins(42, 32, 42, 32)
        root.setSpacing(0)

        eyebrow = QLabel("MEDUSA BCI FRAMEWORK") # etiqueta pequeña superior
        eyebrow.setObjectName("dashboardEyebrow")

        title = QLabel("Medusa Analyzer KEOPS") # título principal
        title.setObjectName("dashboardHeroTitle")
        title.setWordWrap(True)

        subtitle = QLabel("Create reproducible analysis pipelines for biomedical signals, "
                          "from data loading to final report.") # subtítulo
        subtitle.setObjectName("dashboardHeroSubtitle")
        subtitle.setWordWrap(True)

        root.addWidget(eyebrow)
        root.addSpacing(12)
        root.addWidget(title)
        root.addSpacing(8)
        root.addWidget(subtitle)
        root.addSpacing(22)

        self.chips = QHBoxLayout() # creamos fila horizontal para las etiquetas pequeñas
        self.chips.setSpacing(9)

        # Definimos dos chips
        for text, tone in (("Guided pipelines", "burgundy"), ("BIDS compatible", "teal")):
            chip = QLabel(text)
            chip.setObjectName("heroChip")
            chip.setProperty("tone", tone)
            self.chips.addWidget(chip)

        self.chips.addStretch() # stretch para empujar las chips a la izquierda
        root.addLayout(self.chips) # metemos la fila de chips en el hero

    def resizeEvent(self, event) -> None:
        """Métoodo que se ejecuta automáticamente cuando cambia el tamaño del hero. Lo llama Qt cuando la
        ventana cambia de tamaño."""
        compact = self.width() < 620
        stacked_chips = self.width() < 310

        if self.property("compact") != compact:
            self.setProperty("compact", compact)
            self.style().unpolish(self)
            self.style().polish(self)

            margins = (24, 26, 24, 27) if compact else (42, 32, 42, 32)
            self.layout().setContentsMargins(*margins)

        direction = (QHBoxLayout.Direction.TopToBottom if stacked_chips else QHBoxLayout.Direction.LeftToRight)

        if self.chips.direction() != direction:
            self.chips.setDirection(direction)
            self.chips.setSpacing(7 if stacked_chips else 9)

        super().resizeEvent(event)