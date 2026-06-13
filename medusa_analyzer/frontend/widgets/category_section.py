from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget


class CategorySection(QFrame):
    def __init__(self, title: str, description: str):
        super().__init__()
        self.setProperty("role", "category-section")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 8)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        detail = QLabel(description)
        detail.setObjectName("muted")
        root.addWidget(heading)
        root.addWidget(detail)
        root.addSpacing(14)
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(20)
        root.addWidget(self.content)

    def add_card(self, widget: QWidget, index: int) -> None:
        self.grid.addWidget(widget, index // 3, index % 3)
