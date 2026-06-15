from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from medusa_analyzer.backend.dashboard.registry import get_dashboard_categories
from medusa_analyzer.backend.dashboard.registry import get_dashboard_items
from medusa_analyzer.frontend.widgets.dashboard_hero import DashboardHero
from medusa_analyzer.frontend.widgets.experiment_card import ExperimentCard
from medusa_analyzer.frontend.widgets.module_grid import ModuleGrid


class DashboardPage(QScrollArea):
    route_requested = Signal(str)

    def __init__(self):
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

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(28)

        self.layout.addWidget(DashboardHero())

        self.section_layouts: list[QVBoxLayout] = []

        package_root = Path(__file__).resolve().parents[2]

        items_by_category = defaultdict(list)
        for item in get_dashboard_items(): # (items-tarjetas)
            items_by_category[item.category_id].append(item)
            # ejemplo: items_by_category["signal_processing"].append(item_eeg)

        # Una vez tenemos el diccionario que contiene todas los items por categoría,
        # recorremos las secciones/categorías.
        for category in get_dashboard_categories():
            category_items = items_by_category.get(category.id, [])

            if not category_items:
                continue # avoid empty sections in the dashboard

            section = self._create_category_section(
                title=category.title, subtitle=category.description,
                items=category_items, package_root=package_root)
            self.layout.addWidget(section)

        self.outer.addWidget(self.container)
        self.setWidget(self.content)

    def _create_category_section(self, title: str, subtitle: str,
        items: list, package_root: Path) -> QFrame:
        section = QFrame()
        section.setObjectName("moduleSection")

        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(34, 29, 34, 34)
        section_layout.setSpacing(0)

        self.section_layouts.append(section_layout)

        section_title = QLabel(title)
        section_title.setObjectName("moduleSectionTitle")
        section_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_title.setWordWrap(True)

        section_subtitle = QLabel(subtitle)
        section_subtitle.setObjectName("moduleSectionSubtitle")
        section_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_subtitle.setWordWrap(True)

        section_layout.addWidget(section_title)
        section_layout.addSpacing(8)
        section_layout.addWidget(section_subtitle)
        section_layout.addSpacing(24)

        module_grid = ModuleGrid()

        for item in items:
            card = ExperimentCard(title=item.title, subtitle=item.subtitle,
                icon_path=package_root / item.icon_path,
                enabled=item.enabled, status=item.status,
                accent=item.accent)

            if item.enabled:
                card.clicked.connect(lambda route=item.route: self.route_requested.emit(route))

            module_grid.add_card(card)

        section_layout.addWidget(module_grid)

        return section

    def resizeEvent(self, event) -> None:
        width = event.size().width()

        horizontal_margin = 16 if width < 540 else 28 if width < 860 else 48
        vertical_margin = 18 if width < 540 else 28 if width < 860 else 34
        section_margin = 14 if width < 540 else 24 if width < 860 else 34

        self.outer.setContentsMargins(
            horizontal_margin,
            vertical_margin,
            horizontal_margin,
            vertical_margin + 14,
        )

        for section_layout in self.section_layouts:
            section_layout.setContentsMargins(
                section_margin,
                24 if width < 540 else 29,
                section_margin,
                section_margin,
            )

        self.container.setFixedWidth(
            max(0, min(1120, width - horizontal_margin * 2 - 2))
        )

        super().resizeEvent(event)