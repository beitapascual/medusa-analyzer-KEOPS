import logging

from PySide6.QtWidgets import QMessageBox, QStackedWidget, QWidget


logger = logging.getLogger(__name__)

# Controla qué página se ve dentro del QStackedWidget
class Router:
    def __init__(self, stack: QStackedWidget):
        self.stack = stack
        self.routes: dict[str, QWidget] = {}

    def register(self, route: str, page: QWidget) -> None:
        self.routes[route] = page
        self.stack.addWidget(page) # Añadimos los widgets correspondientes al experimento, o el dashboard

    def navigate(self, route: str) -> None:
        # Cambia la página visible
        page = self.routes.get(route)
        if page is None:
            logger.error("Unknown route '%s'. Available routes: %s", route, sorted(self.routes))
            QMessageBox.critical(self.stack, "Navigation error", f"Unknown route: {route}")
            return
        self.stack.setCurrentWidget(page)
