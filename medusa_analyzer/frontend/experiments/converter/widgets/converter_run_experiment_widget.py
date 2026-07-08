from typing import Any

from PySide6.QtCore import Property, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QTextEdit, QVBoxLayout, QWidget

from medusa_analyzer.frontend.worker import TaskRunner, Worker
from medusa_analyzer.backend.converter.run_conversion import run_conversion


class _ProgressLogColors(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._error_color = QColor("#FFB6C2")
        self._warning_color = QColor("#F6C177")
        self.setObjectName("progressOverlay")
        self.hide()

    def get_error_color(self) -> QColor:
        return QColor(self._error_color)

    def set_error_color(self, color: QColor) -> None:
        if color.isValid():
            self._error_color = QColor(color)

    def get_warning_color(self) -> QColor:
        return QColor(self._warning_color)

    def set_warning_color(self, color: QColor) -> None:
        if color.isValid():
            self._warning_color = QColor(color)

    errorColor = Property(QColor, get_error_color, set_error_color)
    warningColor = Property(QColor, get_warning_color, set_warning_color)


class ConverterRunExperimentWidget(QWidget):
    """Run step for the converter experiment."""

    changed = Signal()

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        self.experiment_info = experiment_info
        self.defaults = defaults
        self.state = state
        self.runner = TaskRunner()
        self.pipeline_running = False
        self.setObjectName("converterRunExperimentWidget")
        self.log_colors = _ProgressLogColors(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title_label = QLabel("Run conversion")
        title_label.setObjectName("pageTitle")
        description_label = QLabel("Convert the loaded MEDUSA data to the selected BIDS output folder.")
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addSpacing(18)

        progress_panel = QFrame()
        progress_panel.setProperty("role", "surface-panel")
        progress_layout = QVBoxLayout(progress_panel)
        progress_layout.setContentsMargins(24, 22, 24, 22)

        self.status_label = QLabel("Ready to run conversion.")
        self.status_label.setObjectName("progressTitle")
        self.status_label.setWordWrap(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("overlayProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("progressLogArea")
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(180)

        progress_layout.addWidget(self.status_label)
        progress_layout.addSpacing(14)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addSpacing(16)
        progress_layout.addWidget(self.log_area)

        layout.addWidget(progress_panel)
        layout.addStretch()

    def log_callback(self, message: str, role: str = "info"):
        """Append a message to the inline conversion log."""
        color = None
        if role == "error":
            color = self.log_colors.errorColor.name()
        elif role == "warning":
            color = self.log_colors.warningColor.name()
        if color:
            self.log_area.append(f'<font color="{color}">{message}</font>')
        else:
            self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def set_progress(self, value: int):
        """Set the inline progress value."""
        self.progress_bar.setValue(value)

    def clear_logs(self):
        """Clear the inline conversion log."""
        self.log_area.clear()

    def run_pipeline(self):
        """Start the converter pipeline in a background worker."""
        if self.pipeline_running:
            return

        self.pipeline_running = True
        self.state["completion_status"] = "incompleted"
        self.changed.emit()

        self.status_label.setText("Running conversion...")
        self.clear_logs()
        self.log_callback("Starting conversion...")
        self.set_progress(0)

        kwargs = {"input_data": self.state['input_data'],
                  "output_path": self.state['output_path'],
                  "extensions": self.defaults.get("load_data",{}).get("allowed_extensions",{}),
                  "progress_callback": self.set_progress,
                  "log_callback": self.log_callback}

        worker = Worker(run_conversion, **kwargs)
        worker.signals.progress.connect(self.set_progress)
        worker.signals.logging.connect(self.log_callback)
        worker.signals.result.connect(self._pipeline_completed)
        worker.signals.error.connect(self._pipeline_failed)
        worker.signals.finished.connect(self._pipeline_finished)
        self.runner.start(worker)

    def _pipeline_completed(self, result: Any) -> None:
        if isinstance(result, dict) and result.get("valid") is False:
            errors = result.get("errors") or ["Conversion finished with errors."]
            self._mark_pipeline_failed("\n".join(str(error) for error in errors))
            return

        self.state["completion_status"] = "completed"
        self.status_label.setText("Conversion finished successfully.")
        self.set_progress(100)

    def _pipeline_failed(self, error: str) -> None:
        self._mark_pipeline_failed(error)

    def _mark_pipeline_failed(self, error: str) -> None:
        self.state["completion_status"] = "incompleted"
        self.log_callback(error, "error")
        self.status_label.setText("Conversion failed. Fix the issue and run again.")

    def _pipeline_finished(self) -> None:
        self.pipeline_running = False
        self.changed.emit()

    def can_continue(self) -> bool:
        return not self.pipeline_running

    def run_conversion_process(self):
        self.run_pipeline()
