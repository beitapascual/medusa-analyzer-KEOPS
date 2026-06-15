from PySide6.QtWidgets import QStackedWidget, QWidget


class Navigator:
    def __init__(self, stack: QStackedWidget):
        self.stack = stack

    def add_page(self, page: QWidget) -> None:
        self.stack.addWidget(page)

    def current_index(self) -> int:
        return self.stack.currentIndex()

    def count(self) -> int:
        return self.stack.count()

    def current_widget(self) -> QWidget:
        return self.stack.currentWidget()

    def go_to(self, index: int) -> None:
        if not 0 <= index < self.count():
            raise ValueError(f"Step index out of range: {index}")
        self.stack.setCurrentIndex(index)

    def next(self) -> None:
        self.go_to(self.current_index() + 1)

    def back(self) -> None:
        self.go_to(self.current_index() - 1)
