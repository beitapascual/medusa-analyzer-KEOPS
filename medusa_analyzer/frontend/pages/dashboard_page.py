from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

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
        self.container.setSizePolicy(
            self.container.sizePolicy().horizontalPolicy(),
            self.container.sizePolicy().verticalPolicy(),
        )
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(28)

        layout.addWidget(DashboardHero())

        modules = QFrame()
        modules.setObjectName("moduleSection")
        self.module_layout = QVBoxLayout(modules)
        self.module_layout.setContentsMargins(34, 29, 34, 34)
        self.module_layout.setSpacing(0)

        section_title = QLabel("Signal processing modules")
        section_title.setObjectName("moduleSectionTitle")
        section_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_title.setWordWrap(True)
        section_subtitle = QLabel(
            "Choose a signal type to start a guided analysis pipeline."
        )
        section_subtitle.setObjectName("moduleSectionSubtitle")
        section_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_subtitle.setWordWrap(True)
        self.module_layout.addWidget(section_title)
        self.module_layout.addSpacing(8)
        self.module_layout.addWidget(section_subtitle)
        self.module_layout.addSpacing(24)

        self.module_grid = ModuleGrid()
        package_root = Path(__file__).resolve().parents[2]
        for item in get_dashboard_items():
            card = ExperimentCard(
                title=item.title,
                subtitle=item.subtitle,
                icon_path=package_root / item.icon_path,
                enabled=item.enabled,
                status=item.status,
                accent=item.accent,
            )
            if item.enabled:
                card.clicked.connect(
                    lambda route=item.route: self.route_requested.emit(route)
                )
            self.module_grid.add_card(card)
        self.module_layout.addWidget(self.module_grid)
        layout.addWidget(modules)

        self.outer.addWidget(self.container)
        self.setWidget(self.content)

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
        self.module_layout.setContentsMargins(
            section_margin,
            24 if width < 540 else 29,
            section_margin,
            section_margin,
        )
        self.container.setFixedWidth(
            max(0, min(1120, width - horizontal_margin * 2 - 2))
        )
        super().resizeEvent(event)
