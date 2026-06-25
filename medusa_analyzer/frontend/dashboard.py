from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from medusa_analyzer.frontend.experiments import ExperimentDefinition
from medusa_analyzer.frontend.widgets.dashboard_hero import DashboardHero
from medusa_analyzer.frontend.widgets.experiment_card import ExperimentCard
from medusa_analyzer.frontend.widgets.module_grid import ModuleGrid


# Información de una categoría
@dataclass(frozen=True, slots=True)
class DashboardCategory:
    id: str
    title: str
    subtitle: str | None = None
    order: int = 0


# Información para mostrar en una tarjeta
@dataclass(frozen=True, slots=True)
class DashboardItem:
    id: str
    title: str
    subtitle: str
    category_id: str
    route: str
    icon_path: str | Path | None = None
    description: str | None = None
    order: int = 0
    status: str = ""  # for example 'ready' or 'updating'
    accent: str = "burgundy"
    enabled: bool = True


def build_dashboard_catalog(experiments: list[ExperimentDefinition]) -> tuple[list[DashboardCategory], list[DashboardItem]]:
    # Función para obtener las categorías e items a pintar en el dashboard, sin crear las páginas reales de los experimentos
    # eso lo hace (create_experiment_page). build_dashboard_catalog escribe el menú con las tarjetas de los platos, y
    # create_experiment_page cocina el plato completo, es decir, crea el widget real del experimento.
    categories_by_id: dict[str, DashboardCategory] = {}
    items: list[DashboardItem] = []

    for experiment in experiments:
        category_info = experiment.info.get("category", {})
        category_id = category_info.get("id", "uncategorized")
        # setdefault sirve para decir: "si esta categoría todavía no existe en el diccionario, créala. Si existe ya,
        # déjala como está.
        categories_by_id.setdefault(category_id, DashboardCategory(id=category_id,
                title=category_info.get("title", category_id.replace("_", " ").title()),
                subtitle=category_info.get("description"), order=int(category_info.get("order", 0))))
        items.append(DashboardItem(id=experiment.info.get("id", experiment.id),
                category_id=category_id, title=experiment.info.get("title", experiment.id.upper()),
                subtitle=experiment.info.get("subtitle", ""),
                route=experiment.route, icon_path=experiment.icon_path,
                description=experiment.info.get("description"),
                order=int(experiment.info.get("order", 0)),
                status=experiment.info.get("status", "Ready"),
                accent=experiment.info.get("accent", "burgundy"),
                enabled=bool(experiment.info.get("enabled", True))))

    # Ordenamos categorías e items
    categories = sorted(categories_by_id.values(), key=lambda category: (category.order, category.title))
    category_order = {category.id: category.order for category in categories}
    items.sort(key=lambda item: (category_order.get(item.category_id, 0), item.order, item.title))
    return categories, items

# Construimos la interfaz del Dashboard
class DashboardPage(QScrollArea):
    # Crea un ScrollArea, mete un hero arriba (DashboardHero), agrupa items por categoría.
    # Después, para cada item crea un ExperimentCard y, si el item está habilitado, conecta el click a la ruta
    # del experimento.

    route_requested = Signal(str) # señal para cuando se clique en un item

    def __init__(self, categories: list[DashboardCategory], items: list[DashboardItem]):
        super().__init__()
        self.setObjectName("dashboardPage")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.content.setObjectName("dashboard")
        self.outer = QVBoxLayout(self.content)
        self.outer.setContentsMargins(48, 34, 48, 48)
        self.outer.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.container = QWidget()
        self.container.setObjectName("dashboardContainer")
        self.container.setMaximumWidth(1120)
        self.container.setSizePolicy(self.container.sizePolicy().horizontalPolicy(),
            self.container.sizePolicy().verticalPolicy())
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(28)
        layout.addWidget(DashboardHero())

        self.section_layouts: list[QVBoxLayout] = []
        items_by_category: dict[str, list[DashboardItem]] = defaultdict(list)
        for item in items:
            items_by_category[item.category_id].append(item)

        for category in categories:
            category_items = items_by_category.get(category.id, [])
            if not category_items:
                continue
            layout.addWidget(self._create_category_section(category, category_items))

        self.outer.addWidget(self.container)
        self.setWidget(self.content)

    def _create_category_section(self, category: DashboardCategory, items: list[DashboardItem]) -> QFrame:
        section = QFrame()
        section.setObjectName("moduleSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(34, 29, 34, 34)
        section_layout.setSpacing(0)
        self.section_layouts.append(section_layout)

        title = QLabel(category.title)
        title.setObjectName("moduleSectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        section_layout.addWidget(title)

        if category.subtitle:
            section_layout.addSpacing(8)
            description = QLabel(category.subtitle)
            description.setObjectName("moduleSectionSubtitle")
            description.setAlignment(Qt.AlignmentFlag.AlignCenter)
            description.setWordWrap(True)
            section_layout.addWidget(description)

        section_layout.addSpacing(24)

        grid = ModuleGrid()
        for item in items:
            # Creamos las carpetas de cada experimento
            card = ExperimentCard(title=item.title, subtitle=item.subtitle,
                icon_path=Path(item.icon_path) if item.icon_path else None,
                enabled=item.enabled, status=item.status, accent=item.accent)
            if item.enabled:
                # IMPORTANTE: cuando la clicamos emite señal con la ruta específica. Aquí detectamos que una tarjeta ha
                # emitido un click y ejecutamos la función lambda. Esta función ahce que DashboardPage emita route_requestec
                # con la ruta de esa tarjeta.

                # En MainWindow tenemos 'self.dashboard.route_requested.connect(self.router.navigate)' que llama al Router.
                card.clicked.connect(lambda route=item.route: self.route_requested.emit(route))
            grid.add_card(card)
        section_layout.addWidget(grid)
        return section

    def resizeEvent(self, event) -> None:
        # IMPORTANTE: esta función no se llama "a mano" pero sí que se ejecuta.
        width = event.size().width()
        horizontal_margin = 16 if width < 540 else 28 if width < 860 else 48
        vertical_margin = 18 if width < 540 else 28 if width < 860 else 34
        section_margin = 14 if width < 540 else 24 if width < 860 else 34
        self.outer.setContentsMargins(horizontal_margin, vertical_margin, horizontal_margin, vertical_margin + 14)
        for section_layout in self.section_layouts:
            section_layout.setContentsMargins(section_margin, 24 if width < 540 else 29, section_margin, section_margin)
        self.container.setFixedWidth(max(0, min(1120, width - horizontal_margin * 2 - 2)))
        super().resizeEvent(event)
