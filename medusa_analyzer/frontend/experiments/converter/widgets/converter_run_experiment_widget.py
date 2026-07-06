import time

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from medusa_analyzer.frontend.widgets.progress_overlay import ProgressOverlay


class ConverterRunExperimentWidget(QWidget):
    """Run step for the converter experiment."""

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        self.experiment_info = experiment_info
        self.defaults = defaults
        self.state = state
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

    def run_pipeline(self):
        """
        A placeholder method to demonstrate how you might run a process
        and update the UI.
        """
        self.overlay.start_process("Running conversion...")
        self.add_log_message("Starting conversion...")
        self.set_progress(0)

        # Simulate a process using the state data if needed
        # For example: files_to_process = self.state.get("files", [])
        for i in range(101):
            time.sleep(0.05)  # Simulate work
            self.set_progress(i)
            if i % 10 == 0:
                self.add_log_message(f"Processing step {i // 10}...")
            QApplication.processEvents()

        self.overlay.finish_process("Conversion finished successfully!")
