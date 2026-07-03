from PySide6.QtWidgets import QFrame, QTextEdit, QProgressBar, QVBoxLayout, QWidget, QLabel
from typing import Any

class RunExperimentWidget(QWidget):
    """
    A widget to display the progress and logs of a running experiment.
    """
    def __init__(self, title: str, description: str):
        super().__init__()
        self.setObjectName("runExperimentWidget")

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Title and Description
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        description_label = QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addSpacing(18)

        # Central panel for content
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 22, 24, 22)

        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setObjectName("logArea")
        self.log_area.setMinimumHeight(250)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setObjectName("progressBar")

        # Add widgets to the panel layout
        panel_layout.addWidget(self.log_area)
        panel_layout.addSpacing(15)
        panel_layout.addWidget(self.progress_bar)

        # Add panel to the main layout
        layout.addWidget(panel)
        layout.addStretch()

    def add_log_message(self, message: str, role: str = "info"):
        """Appends a styled message to the log area."""
        color = None
        if role == "error":
            color = "#FFB6C2" # A light red
        elif role == "warning":
            color = "#F6C177" # A light yellow/orange

        if color:
            self.log_area.append(f'<font color="{color}">{message}</font>')
        else:
            self.log_area.append(message)
        
        # Auto-scroll to the bottom
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def set_progress(self, value: int):
        """Sets the value of the progress bar (0-100)."""
        self.progress_bar.setValue(value)

    def clear_logs(self):
        """Clears all messages from the log area."""
        self.log_area.clear()
