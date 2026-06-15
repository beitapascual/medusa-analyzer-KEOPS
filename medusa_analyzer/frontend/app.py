import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from medusa_analyzer.frontend.dashboard import DashboardPage, build_dashboard_catalog
from medusa_analyzer.frontend.experiments import create_experiment_page, discover_experiments
from medusa_analyzer.frontend.router import Router


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Medusa Analyzer")
        self.resize(1200, 800)
        self.setMinimumSize(1020, 700)

        stack = QStackedWidget()
        self.setCentralWidget(stack)
        self.router = Router(stack)

        self.experiments = []
        self.pages = {}
        for definition in discover_experiments():
            try:
                page = create_experiment_page(definition)
            except Exception as exc:
                print(f"Skipping experiment '{definition.id}': {exc}")
                continue
            self.experiments.append(definition)
            self.pages[definition.route] = page

        categories, items = build_dashboard_catalog(self.experiments)
        self.dashboard = DashboardPage(categories, items)
        self.dashboard.route_requested.connect(self.router.navigate)

        self.router.register("dashboard", self.dashboard)
        for route, page in self.pages.items():
            self.router.register(route, page)
            page.dashboard_requested.connect(lambda: self.router.navigate("dashboard"))

        self.router.navigate("dashboard")


def _load_stylesheet() -> str:
    path = Path(__file__).resolve().parent / "styles" / "main.qss"
    return path.read_text(encoding="utf-8")


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Medusa Analyzer")
    app.setOrganizationName("Medusa BCI")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(_load_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()
