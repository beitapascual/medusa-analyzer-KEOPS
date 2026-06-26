from PySide6.QtWidgets import QStackedWidget, QWidget


class Navigator:
    def __init__(self, stack: QStackedWidget):
        self.stack = stack # Recibe un stackedWidget y lo guarda

    def add_page(self, page: QWidget) -> None:
        """Añade una página/widget al stack"""
        self.stack.addWidget(page)

    def current_index(self) -> int:
        """Devuelve el índice del paso actual"""
        return self.stack.currentIndex()

    def count(self) -> int:
        """Devuelve cuántas páginas hay dentro del stack"""
        return self.stack.count()

    def current_widget(self) -> QWidget:
        """Devuelve el widget del paso actual"""
        return self.stack.currentWidget()

    def go_to(self, index: int) -> None:
        """Salta a un paso concreto"""
        if not 0 <= index < self.count(): # comprueba que el índice exista
            raise ValueError(f"Step index out of range: {index}")
        self.stack.setCurrentIndex(index) # cambia el paso visible

    def next(self) -> None:
        """Avanza al siguiente paso """
        self.go_to(self.current_index() + 1)

    def back(self) -> None:
        """Retrocede al paso anterior"""
        self.go_to(self.current_index() - 1)
