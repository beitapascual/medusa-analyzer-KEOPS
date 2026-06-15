from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout, QWidget


class LoadingOverlay(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("loadingOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel = QFrame()
        self.panel.setProperty("role", "loading-panel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(36, 28, 36, 28)
        self.label = QLabel("Loading recordings...")
        self.label.setObjectName("loadingTitle")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedWidth(320)
        panel_layout.addWidget(self.label)
        panel_layout.addSpacing(12)
        panel_layout.addWidget(self.progress)
        layout.addWidget(self.panel)
        self.hide()

    def show_loading(self, text: str) -> None:
        self.label.setText(text)
        self.progress.setValue(0)
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()

    def hide_loading(self) -> None:
        self.hide()

    def resizeEvent(self, event):
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        super().resizeEvent(event)
