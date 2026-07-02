from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout

class ProgressOverlay(QFrame):
    def __init__(self, parent: QWidget, show_log: bool = False):
        super().__init__(parent)
        self.show_log = show_log
        self.setObjectName("progressOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel = QFrame()
        self.panel.setProperty("role", "progress-panel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(36, 28, 36, 28)
        self.label = QLabel("Processing your request. Please wait...")
        self.label.setObjectName("progressTitle")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedWidth(320)


        panel_layout.addWidget(self.label)
        panel_layout.addSpacing(12)
        if self.show_log:
            self.log_area = QTextEdit()
            self.log_area.setReadOnly(True)
            self.log_area.setFixedHeight(150)
            panel_layout.addWidget(self.log_area)
            panel_layout.addSpacing(12)
        panel_layout.addWidget(self.progress)
        
        # Add close button
        button_layout = QHBoxLayout()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.hide)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        panel_layout.addLayout(button_layout)

        layout.addWidget(self.panel)
        self.hide()

    def add_log_message(self, message: str, role: str = "info"):
        """Appends a message to the log area with a specific style."""
        if not self.show_log:
            return

        color = None
        if role == "error":
            color = "#FFB6C2"
        elif role == "warning":
            color = "#F6C177"

        if color:
            self.log_area.append(f'<font color="{color}">{message}</font>')
        else:
            self.log_area.append(message)

    def start_process(self, text: str) -> None:
        self.label.setText(text)
        self.progress.setValue(0)
        if self.show_log:
            self.log_area.clear()
        self.close_button.hide()
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()

    def finish_process(self, summary: str | None = None) -> None:
        self.label.setText('Process finished')
        if self.show_log:
            self.add_log_message('----------- SUMMARY -----------')
            self.add_log_message(summary)
        self.close_button.show()

    def resizeEvent(self, event):
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        super().resizeEvent(event)