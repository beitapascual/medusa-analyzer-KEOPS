import time
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from medusa_analyzer.frontend.worker import TaskRunner, Worker
from medusa_analyzer.frontend.widgets.progress_overlay import ProgressOverlay


class ConverterRunExperimentWidget(QWidget):
    """Run step for the converter experiment."""

    changed = Signal()

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        self.experiment_info = experiment_info
        self.defaults = defaults
        self.state = state
        self.runner = TaskRunner()
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

    def add_log_message(self, message: str, role: str = "info"):
        """Append a message to the shared progress overlay log."""
        self.overlay.add_log_message(message, role)

    def set_progress(self, value: int):
        """Set the shared progress overlay value."""
        self.progress_bar.setValue(value)

    def clear_logs(self):
        """Clear the shared progress overlay log."""
        self.log_area.clear()

    # TODO: REVISAR
    def _completion_state(self) -> dict[str, Any]:
        completion = self.state.setdefault("completion", {})
        completion.setdefault("requires_pipeline", True)
        completion.setdefault("status", "incompleted")
        completion.setdefault("running", False)
        completion.setdefault("error", None)
        completion.setdefault("result", None)
        return completion

    def run_pipeline(self):
        """Start the converter pipeline in a background worker."""
        completion = self._completion_state()
        if completion.get("running", False):
            return

        completion["status"] = "incompleted"
        completion["running"] = True
        completion["error"] = None
        completion["result"] = None
        self.changed.emit()

        self.overlay.start_process("Running conversion...")
        self.add_log_message("Starting conversion...")
        self.set_progress(0)

        worker = Worker(self._run_pipeline)
        worker.signals.progress.connect(self.set_progress)
        worker.signals.logging.connect(self.add_log_message)
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

    # TODO: REVISAR
    def _pipeline_completed(self, result: Any) -> None:
        completion = self._completion_state()

        if isinstance(result, dict) and result.get("valid") is False:
            errors = result.get("errors") or ["Conversion finished with errors."]
            self._mark_pipeline_failed("\n".join(str(error) for error in errors))
            return

        completion["status"] = "completed"
        completion["result"] = result
        completion["error"] = None
        self.set_progress(100)
        self.overlay.finish_process("Conversion finished successfully!")

    # TODO: REVISAR
    def _pipeline_failed(self, error: str) -> None:
        self._mark_pipeline_failed(error)

    # TODO: REVISAR
    def _mark_pipeline_failed(self, error: str) -> None:
        completion = self._completion_state()
        completion["status"] = "incompleted"
        completion["error"] = error
        completion["result"] = None
        self.overlay.add_log_message(error, "error")
        self.overlay.finish_process("Conversion failed. Fix the issue and run again.")

    # TODO: REVISAR
    def _pipeline_finished(self) -> None:
        completion = self._completion_state()
        completion["running"] = False
        self.changed.emit()

    # TODO: REVISAR
    def run_conversion_process(self):
        self.run_pipeline()
