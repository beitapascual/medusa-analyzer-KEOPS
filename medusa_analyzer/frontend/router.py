from PySide6.QtWidgets import QStackedWidget, QWidget


class Router:
    # El ruter solo actúa a nivel global, por ejemplo, entre el dashboard y el experimento X.
    # Luego, los pasos del experimento X se gestionan en su propio WorkFlowPage.

    def __init__(self, stack: QStackedWidget):
        self.stack = stack
        self.routes: dict[str, QWidget] = {}

    def register(self, route: str, page: QWidget) -> None:
        self.routes[route] = page
        self.stack.addWidget(page)

    def navigate(self, route: str) -> None:
        try:
            self.stack.setCurrentWidget(self.routes[route])
        except KeyError as exc:
            raise ValueError(f"Unknown route: {route}") from exc
