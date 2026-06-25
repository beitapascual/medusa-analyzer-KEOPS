from PySide6.QtWidgets import QStackedWidget, QWidget

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
        try:
            self.stack.setCurrentWidget(self.routes[route])
        except KeyError as exc:
            raise ValueError(f"Unknown route: {route}") from exc
