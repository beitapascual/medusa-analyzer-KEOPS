import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from medusa_analyzer.frontend.pages.dashboard_page import DashboardPage
from medusa_analyzer.frontend.pages.eeg.eeg_workflow_page import EEGWorkflowPage
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
        self.dashboard = DashboardPage()
        self.eeg = EEGWorkflowPage()
        self.router.register("dashboard", self.dashboard)
        self.router.register("eeg", self.eeg)
        self.dashboard.route_requested.connect(self.router.navigate)
        self.eeg.dashboard_requested.connect(lambda: self.router.navigate("dashboard"))
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
