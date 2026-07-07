import time
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from medusa_analyzer.frontend.worker import TaskRunner, Worker
from medusa_analyzer.frontend.widgets.progress_overlay import ProgressOverlay
from medusa_analyzer.backend.converter.run_conversion import run_conversion


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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title_label = QLabel("Run conversion")
        title_label.setObjectName("pageTitle")
        description_label = QLabel("Convert the loaded MEDUSA data to the selected BIDS output folder.")
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch()

        self.overlay = ProgressOverlay(self)
        self.progress_bar = self.overlay.progress
        self.log_area = self.overlay.log_area

    def log_callback(self, message: str, role: str = "info"):
        """Append a message to the shared progress overlay log."""
        self.overlay.add_log_message(message, role)

    def set_progress(self, value: int):
        """Set the shared progress overlay value."""
        self.progress_bar.setValue(value)

    def clear_logs(self):
        """Clear the shared progress overlay log."""
        self.log_area.clear()

    def run_pipeline(self):
        """Start the converter pipeline in a background worker."""
        if self.pipeline_running:
            return

        self.pipeline_running = True
        self.state["completion_status"] = "incompleted"
        self.changed.emit()

        self.overlay.start_process("Running conversion...")
        self.log_callback("Starting conversion...")
        self.set_progress(0)

        kwargs = {"input_data": self.state['input_data'],
                  "output_path": self.state['output_path'],
                  "extensions": self.defaults.get("load_data",{}).get("allowed_extensions",{}),
                  "progress_callback": self.set_progress,
                  "log_callback": self.log_callback}

        worker = Worker(run_conversion, [], kwargs)
        worker.signals.progress.connect(self.set_progress)
        worker.signals.logging.connect(self.log_callback)
        worker.signals.result.connect(self._pipeline_completed)
        worker.signals.error.connect(self._pipeline_failed)
        worker.signals.finished.connect(self._pipeline_finished)
        self.runner.start(worker)

    def _run_pipeline(self, progress_callback=None, log_callback=None) -> dict[str, Any]:
        """
        Worker entry point.

        Worker injects progress_callback and log_callback as keyword arguments.
        Replace this body with the real converter pipeline when it exists.
        """
        if progress_callback is not None:
            progress_callback(0)
        if log_callback is not None:
            log_callback("Preparing converter pipeline...", "info")

        for i in range(101):
            time.sleep(0.03)
            if progress_callback is not None:
                progress_callback(i)
            if log_callback is not None and i % 20 == 0:
                log_callback(f"Conversion progress: {i}%", "info")

        return {"valid": True}

    def _pipeline_completed(self, result: Any) -> None:
        if isinstance(result, dict) and result.get("valid") is False:
            errors = result.get("errors") or ["Conversion finished with errors."]
            self._mark_pipeline_failed("\n".join(str(error) for error in errors))
            return

        self.state["completion_status"] = "completed"
        self.set_progress(100)
        self.overlay.finish_process("Conversion finished successfully!")

    def _pipeline_failed(self, error: str) -> None:
        self._mark_pipeline_failed(error)

    def _mark_pipeline_failed(self, error: str) -> None:
        self.state["completion_status"] = "incompleted"
        self.overlay.add_log_message(error, "error")
        self.overlay.finish_process("Conversion failed. Fix the issue and run again.")

    def _pipeline_finished(self) -> None:
        self.pipeline_running = False
        self.changed.emit()

    def can_continue(self) -> bool:
        return not self.pipeline_running

    def run_conversion_process(self):
        self.run_pipeline()
